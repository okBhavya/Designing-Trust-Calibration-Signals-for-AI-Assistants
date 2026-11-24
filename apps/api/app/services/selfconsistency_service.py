"""Self-consistency reliability provider.

An LLM extracts the answer's checkable claims, the same prompt is answered k more times
independently, and one judge call records whether each independent answer supports,
contradicts or omits each claim. A claim's support rate is supported / k; the answer's
score is the support rate of its weakest high-materiality claim.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings, get_settings
from app.schemas.signal import ClaimAssessment, SentenceFlag, SignalRequest, SignalResponse
from app.services.llm_client import AnthropicLLMClient, LLMClient, LLMUnavailableError
from app.services.reliability_service import Sentence, _normalize, normalize_answer
from app.services.signal_service import SignalProvider

logger = logging.getLogger("calibrai.selfconsistency")

MODEL_VERSION_PREFIX = "selfconsistency-v1"
MAX_CLAIMS = 8
MATERIALITY_ORDER = {"high": 0, "medium": 1, "low": 2}
Materiality = Literal["high", "medium", "low"]
Verdict = Literal["supported", "contradicted", "not_mentioned"]


class MalformedOutputError(ValueError):
    """The model's JSON could not be parsed or validated, even after a retry."""


# --- LLM output models -----------------------------------------------------------------


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim: str = Field(min_length=1, max_length=2_000)
    sentence_indices: list[int] = Field(min_length=1)
    materiality: Materiality


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_type: Literal["factual", "code_only", "creative", "small_talk"]
    claims: list[ExtractedClaim]


class JudgedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_index: int = Field(ge=0)
    verdicts: list[Verdict]


class Judgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claims: list[JudgedClaim]


EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer_type": {"type": "string", "enum": ["factual", "code_only", "creative", "small_talk"]},
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "sentence_indices": {"type": "array", "items": {"type": "integer"}},
                    "materiality": {"type": "string", "enum": ["high", "medium", "low"]},
                },
                "required": ["claim", "sentence_indices", "materiality"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["answer_type", "claims"],
    "additionalProperties": False,
}

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_index": {"type": "integer"},
                    "verdicts": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["supported", "contradicted", "not_mentioned"]},
                    },
                },
                "required": ["claim_index", "verdicts"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["claims"],
    "additionalProperties": False,
}

EXTRACT_SYSTEM = """You identify the checkable factual claims in an AI assistant's answer. You receive the user's question and the answer split into numbered sentences.

First classify the answer:
- "factual": it states facts that could be checked against the world.
- "code_only": it is essentially code or commands, with no factual claims beyond the code itself.
- "creative": fiction, poetry, brainstorming or other invented content.
- "small_talk": greetings, thanks or other chit-chat.

For a factual answer, list up to 8 distinct claims a careful reader could verify: names, numbers, dates, causes, definitions, attributions. Skip opinions, advice, hedged speculation and restatements of the question. Write each claim as one short self-contained sentence and cite the indices of the sentences it comes from. Rate materiality by how much the answer depends on the claim: "high" if the answer is wrong or misleading when the claim is wrong, "medium" if it matters but is secondary, "low" for incidental detail.

For any other answer type, return an empty claims list."""

SAMPLE_SYSTEM = "You are a helpful assistant. Answer the user's question."

JUDGE_SYSTEM = """You compare claims against independent answers to the same question.

For each claim and each answer, choose one verdict:
- "supported": the answer states or clearly implies the claim.
- "contradicted": the answer states something incompatible with the claim.
- "not_mentioned": the answer does not address the claim.

Judge each answer only by what it says; do not use your own knowledge to decide whether a claim is true. Return one row per claim, using its claim_index, with exactly one verdict per answer in answer order."""


# --- Scoring (pure, unit-tested) ----------------------------------------------------------


@dataclass(frozen=True)
class ClaimConsistency:
    claim_id: str
    text: str
    sentence_indices: tuple[int, ...]
    materiality: Materiality
    verdicts: tuple[Verdict, ...]

    @property
    def supported(self) -> int:
        return sum(verdict == "supported" for verdict in self.verdicts)

    @property
    def support_rate(self) -> float:
        return self.supported / len(self.verdicts)


def state_for(score: float, high_threshold: float, medium_threshold: float) -> Literal["high", "medium", "low"]:
    if score >= high_threshold:
        return "high"
    if score >= medium_threshold:
        return "medium"
    return "low"


def weakest_claim(claims: list[ClaimConsistency]) -> ClaimConsistency:
    """Weakest high-materiality claim, else the weakest claim of any materiality (first on ties)."""
    if not claims:
        raise ValueError("At least one claim is required")
    pool = [claim for claim in claims if claim.materiality == "high"] or claims
    return min(pool, key=lambda claim: claim.support_rate)


def short_claim(text: str, limit: int = 60) -> str:
    text = " ".join(text.split()).rstrip(".")
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0] or text[:limit]
    return f"{cut}…"


def agreement_reason(claim: ClaimConsistency, subject: str) -> str:
    samples = len(claim.verdicts)
    if claim.supported == samples:
        return f"All {samples} independent attempts agreed on {subject}."
    return f"Only {claim.supported} of {samples} independent attempts agreed on {subject}."


def claim_id_for(text: str) -> str:
    return f"clm_{hashlib.sha256(_normalize(text).encode()).hexdigest()[:12]}"


# --- Provider -------------------------------------------------------------------------------


@dataclass
class _Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, result) -> None:
        self.calls += 1
        self.input_tokens += result.input_tokens
        self.output_tokens += result.output_tokens


@dataclass(frozen=True)
class _Abstain:
    explanation: str


def default_client_factory(settings: Settings) -> LLMClient:
    if settings.llm_api_key is None or not settings.llm_api_key.get_secret_value():
        raise LLMUnavailableError("LLM_API_KEY is not configured")
    return AnthropicLLMClient(
        api_key=settings.llm_api_key.get_secret_value(),
        model=settings.llm_model,
        timeout_seconds=settings.selfconsistency_timeout_seconds,
        effort=settings.llm_effort,
    )


class SelfConsistencyProvider(SignalProvider):
    def __init__(
        self,
        client_factory: Callable[[], LLMClient] | None = None,
        settings: Settings | None = None,
    ):
        self.settings = settings or get_settings()
        self._client_factory = client_factory or (lambda: default_client_factory(self.settings))

    def evaluate(self, request: SignalRequest) -> SignalResponse:
        # The signal route is synchronous and runs in a worker thread, so a private event loop is safe.
        return asyncio.run(self.aevaluate(request))

    async def aevaluate(self, request: SignalRequest) -> SignalResponse:
        started = perf_counter()
        usage = _Usage()
        model = "unconfigured"
        outcome = "unavailable"
        try:
            if not request.answer or not request.answer.strip():
                return self._unavailable("An answer was not available for evaluation.", model, started)
            sentences = normalize_answer(request.answer)
            if not any(not sentence.is_code and sentence.text for sentence in sentences):
                outcome = "abstained"
                return self._abstained("Code-only answers are not checked for consistency.", model, started)
            if not request.prompt or not request.prompt.strip():
                return self._unavailable("The original prompt was not available for evaluation.", model, started)
            try:
                client = self._client_factory()
            except LLMUnavailableError:
                return self._unavailable("Consistency evaluation is not configured.", model, started)
            model = client.model
            try:
                result = await asyncio.wait_for(
                    self._run(client, request.prompt, sentences, usage),
                    timeout=self.settings.selfconsistency_timeout_seconds,
                )
            except TimeoutError:
                outcome = "timeout"
                return self._unavailable("Consistency evaluation timed out.", model, started)
            except (LLMUnavailableError, MalformedOutputError) as error:
                outcome = f"failed:{type(error).__name__}"
                return self._unavailable("Consistency evaluation is temporarily unavailable.", model, started)
            finally:
                await client.aclose()
            if isinstance(result, _Abstain):
                outcome = "abstained"
                return self._abstained(result.explanation, model, started)
            outcome = result.assessment_state
            return self._finish(result, model, started)
        finally:
            logger.info(
                "selfconsistency outcome=%s model=%s latency_ms=%d llm_calls=%d input_tokens=%d output_tokens=%d",
                outcome,
                model,
                round((perf_counter() - started) * 1000),
                usage.calls,
                usage.input_tokens,
                usage.output_tokens,
            )

    async def _run(
        self,
        client: LLMClient,
        prompt: str,
        sentences: tuple[Sentence, ...],
        usage: _Usage,
    ) -> SignalResponse | _Abstain:
        samples_needed = self.settings.selfconsistency_samples
        # Samples do not depend on the extraction, so they start at once to fit the latency budget;
        # they are cancelled if the extraction says there is nothing to check.
        sample_tasks = [
            asyncio.create_task(
                client.complete(
                    system=SAMPLE_SYSTEM,
                    prompt=prompt,
                    temperature=self.settings.selfconsistency_temperature,
                )
            )
            for _ in range(samples_needed)
        ]
        try:
            extraction = await self._extract(client, prompt, sentences, usage)
            if extraction.answer_type != "factual" or not extraction.claims:
                await _cancel(sample_tasks)
                kind = extraction.answer_type.replace("_", " ")
                reason = (
                    f"This looks like a {kind} answer, so it is not checked for consistency."
                    if extraction.answer_type != "factual"
                    else "No independently checkable claims were found."
                )
                return _Abstain(reason)
            sample_results = await asyncio.gather(*sample_tasks)
        except BaseException:
            await _cancel(sample_tasks)
            raise
        for result in sample_results:
            usage.add(result)
        samples = [result.text for result in sample_results]
        claims = _dedupe_and_cap(extraction.claims)
        verdicts = await self._judge(client, claims, samples, usage)
        consistency = [
            ClaimConsistency(
                claim_id=claim_id_for(claim.claim),
                text=claim.claim,
                sentence_indices=tuple(sorted(set(claim.sentence_indices))),
                materiality=claim.materiality,
                verdicts=tuple(row),
            )
            for claim, row in zip(claims, verdicts)
        ]
        return self._build(consistency)

    async def _extract(self, client: LLMClient, prompt: str, sentences: tuple[Sentence, ...], usage: _Usage) -> Extraction:
        numbered = "\n".join(f"[{sentence.index}] {sentence.text}" for sentence in sentences)
        user = f"Question:\n<question>\n{prompt}\n</question>\n\nAnswer sentences:\n<answer>\n{numbered}\n</answer>"

        def parse(text: str) -> Extraction:
            extraction = Extraction.model_validate(json.loads(text))
            valid = range(len(sentences))
            if any(index not in valid for claim in extraction.claims for index in claim.sentence_indices):
                raise ValueError("sentence index out of range")
            return extraction

        return await _call_json(client, EXTRACT_SYSTEM, user, EXTRACTION_SCHEMA, parse, usage)

    async def _judge(
        self,
        client: LLMClient,
        claims: list[ExtractedClaim],
        samples: list[str],
        usage: _Usage,
    ) -> list[list[Verdict]]:
        claim_lines = "\n".join(f"[{index}] {claim.claim}" for index, claim in enumerate(claims))
        answer_blocks = "\n\n".join(
            f'<answer id="{index + 1}">\n{sample}\n</answer>' for index, sample in enumerate(samples)
        )
        user = (
            f"Claims:\n{claim_lines}\n\n"
            f"There are {len(samples)} answers; give exactly {len(samples)} verdicts per claim.\n\n{answer_blocks}"
        )

        def parse(text: str) -> list[list[Verdict]]:
            judgement = Judgement.model_validate(json.loads(text))
            rows = {row.claim_index: row.verdicts for row in judgement.claims}
            if sorted(rows) != list(range(len(claims))) or len(judgement.claims) != len(claims):
                raise ValueError("judge matrix does not cover every claim exactly once")
            if any(len(row) != len(samples) for row in rows.values()):
                raise ValueError("judge matrix has the wrong number of verdicts")
            return [rows[index] for index in range(len(claims))]

        return await _call_json(client, JUDGE_SYSTEM, user, JUDGE_SCHEMA, parse, usage)

    def _build(self, claims: list[ClaimConsistency]) -> SignalResponse:
        high, medium = self.settings.selfconsistency_high_threshold, self.settings.selfconsistency_medium_threshold
        weakest = weakest_claim(claims)
        score = weakest.support_rate
        state = state_for(score, high, medium)

        flagged: dict[int, list[ClaimConsistency]] = {}
        for claim in claims:
            if claim.support_rate < medium:
                for index in claim.sentence_indices:
                    flagged.setdefault(index, []).append(claim)
        flags = [
            SentenceFlag(
                sentence_index=index,
                label="low_agreement",
                explanation="; ".join(
                    f"{claim.supported} of {len(claim.verdicts)} independent attempts supported a claim here"
                    for claim in items
                ),
                claim_ids=[claim.claim_id for claim in items],
            )
            for index, items in sorted(flagged.items())
        ]
        assessments = [
            ClaimAssessment(
                claim_id=claim.claim_id,
                claim=claim.text,
                assessment={"high": "consistent", "medium": "partially_consistent", "low": "inconsistent"}[
                    state_for(claim.support_rate, high, medium)
                ],
                confidence=state_for(claim.support_rate, high, medium),
                evidence_strength=f"{claim.supported}/{len(claim.verdicts)} samples",
                uncertainty=round(1 - claim.support_rate, 4),
                supporting_source_ids=[f"sample-{i + 1}" for i, v in enumerate(claim.verdicts) if v == "supported"],
                contradicting_source_ids=[
                    f"sample-{i + 1}" for i, v in enumerate(claim.verdicts) if v == "contradicted"
                ],
            )
            for claim in claims
        ]
        return SignalResponse(
            confidence=state,
            assessmentState=state,
            score=score,
            sentenceFlags=flags,
            claimAssessments=assessments,
            explanation=agreement_reason(weakest, f'"{short_claim(weakest.text)}"'),
            # The stored copy must not contain claim text, so it names the claim by id instead.
            stored_explanation=agreement_reason(weakest, f"claim {weakest.claim_id}"),
            modelVersion="pending",
            processingLatencyMs=0,
        )

    def _version(self, model: str) -> str:
        return f"{MODEL_VERSION_PREFIX}:{model}"[:100]

    def _finish(self, result: SignalResponse, model: str, started: float) -> SignalResponse:
        return result.model_copy(
            update={"model_version": self._version(model), "processing_latency_ms": _elapsed_ms(started)}
        )

    def _unavailable(self, explanation: str, model: str, started: float) -> SignalResponse:
        return SignalResponse(
            confidence=None,
            assessmentState="unavailable",
            score=None,
            explanation=explanation,
            modelVersion=self._version(model),
            processingLatencyMs=_elapsed_ms(started),
        )

    def _abstained(self, explanation: str, model: str, started: float) -> SignalResponse:
        return SignalResponse(
            confidence=None,
            assessmentState="abstained",
            score=None,
            explanation=explanation,
            modelVersion=self._version(model),
            processingLatencyMs=_elapsed_ms(started),
        )


async def _call_json(client: LLMClient, system: str, user: str, schema: dict[str, Any], parse, usage: _Usage):
    """One call plus one retry on unparseable or invalid JSON."""
    for _ in range(2):
        result = await client.complete(system=system, prompt=user, json_schema=schema)
        usage.add(result)
        try:
            return parse(result.text)
        except ValueError:  # json.JSONDecodeError and pydantic.ValidationError are ValueErrors
            continue
    raise MalformedOutputError("model output failed validation twice")


def _dedupe_and_cap(claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
    unique: dict[str, ExtractedClaim] = {}
    for claim in claims:
        unique.setdefault(claim_id_for(claim.claim), claim)
    ordered = sorted(unique.values(), key=lambda claim: MATERIALITY_ORDER[claim.materiality])
    return ordered[:MAX_CLAIMS]


async def _cancel(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
