"""Self-consistency reliability provider.

An LLM extracts the answer's checkable claims, the same prompt is answered k more times
independently, and one judge call records whether each independent answer supports,
contradicts or omits each claim.

A claim mentioned (supported or contradicted) by fewer than MIN_MENTIONS samples is
"not_addressed": it is reported but neither flagged nor scored. Otherwise its support is
supported / mentions. The answer's score is the support of its weakest addressed
high-materiality claim (else the weakest addressed claim); with no addressed claim the
answer is insufficient_evidence.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
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
MIN_MENTIONS = 2
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

# Appended to EXTRACT_SYSTEM for the one retry after a claim fails the grounding check.
STRICT_EXTRACT_SUFFIX = """

Restate only what each sentence says. Do not add any name, number or date that the cited sentences or the question do not contain, and keep the answer's own figures even if you believe they are wrong."""

SAMPLE_SYSTEM = "You are a helpful assistant. Answer the user's question."

JUDGE_SYSTEM = """You compare claims against independent answers to the same question.

For each claim and each answer, choose one verdict:
- "supported": the answer states or clearly implies the claim.
- "contradicted": the answer states something incompatible with the claim.
- "not_mentioned": the answer does not address the claim.

Judge each answer only by what it says; do not use your own knowledge to decide whether a claim is true. Return one row per claim, using its claim_index, with exactly one verdict per answer in answer order."""


# --- Claim grounding (no LLM call) ----------------------------------------------------------

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_WORD = re.compile(r"\w[\w'\u2019-]*")
# Capitalized words that are not proper nouns (sentence starts, pronouns, determiners).
_NOT_PROPER = frozenset(
    """a an the it its this that these those he she his her him they their them we our you your i
    in on at for of and or but as by with from to into onto after before during when while where which
    who whom whose what why how there here some many most all both each every no not one if so than
    then also however according approximately about around nearly over under yes""".split()
)


def _numbers(text: str) -> set[str]:
    return {match.group().replace(",", "") for match in _NUMBER.finditer(text)}


def _proper_nouns(text: str) -> list[str]:
    nouns = []
    for match in _WORD.finditer(text):
        word = re.sub(r"['\u2019]s$", "", match.group()).strip("'\u2019-")
        if len(word) > 1 and word[0].isupper() and not word[0].isdigit() and word.lower() not in _NOT_PROPER:
            nouns.append(word)
    return nouns


def ungrounded_terms(claim: str, source_sentences: str, question: str, answer: str) -> list[str]:
    """Numbers and proper nouns in `claim` that the answer did not state.

    Numbers (including years) must appear in the claim's own source sentences or the question.
    Proper nouns may also come from elsewhere in the answer, so a claim can name what "it" refers to.
    """
    allowed_numbers = _numbers(source_sentences) | _numbers(question)
    missing = [number for number in sorted(_numbers(claim)) if number not in allowed_numbers]
    context = f"{answer}\n{question}"
    for noun in _proper_nouns(claim):
        if not re.search(rf"(?<!\w){re.escape(noun)}(?!\w)", context, re.IGNORECASE) and noun not in missing:
            missing.append(noun)
    return missing


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
    def contradicted(self) -> int:
        return sum(verdict == "contradicted" for verdict in self.verdicts)

    @property
    def mentions(self) -> int:
        return self.supported + self.contradicted

    @property
    def addressed(self) -> bool:
        return self.mentions >= MIN_MENTIONS

    @property
    def support_rate(self) -> float | None:
        """supported / mentions; None when no sample mentions the claim."""
        return self.supported / self.mentions if self.mentions else None


def state_for(score: float, high_threshold: float, medium_threshold: float) -> Literal["high", "medium", "low"]:
    if score >= high_threshold:
        return "high"
    if score >= medium_threshold:
        return "medium"
    return "low"


def weakest_claim(claims: list[ClaimConsistency]) -> ClaimConsistency | None:
    """Weakest addressed high-materiality claim, else the weakest addressed claim (first on ties).

    None when no claim is addressed.
    """
    addressed = [claim for claim in claims if claim.addressed]
    pool = [claim for claim in addressed if claim.materiality == "high"] or addressed
    return min(pool, key=lambda claim: claim.support_rate) if pool else None


def short_claim(text: str, limit: int = 60) -> str:
    text = " ".join(text.split()).rstrip(".")
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(" ", 1)[0] or text[:limit]
    return f"{cut}…"


def agreement_reason(claim: ClaimConsistency, subject: str, not_checked: int = 0) -> str:
    attempts = "attempts" if claim.mentions == len(claim.verdicts) else "attempts that mentioned it"
    if claim.supported == claim.mentions:
        reason = f"All {claim.mentions} {attempts} agreed on {subject}"
    else:
        reason = f"{claim.supported} of {claim.mentions} {attempts} agreed on {subject}"
    if not_checked:
        plural = "s" if not_checked != 1 else ""
        reason += f"; {not_checked} side detail{plural} not checked"
    return f"{reason}."


def claim_id_for(text: str) -> str:
    return f"clm_{hashlib.sha256(_normalize(text).encode()).hexdigest()[:12]}"


# --- Provider -------------------------------------------------------------------------------


@dataclass
class _Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    grounding_retries: int = 0
    grounding_fallbacks: int = 0

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
                "selfconsistency outcome=%s model=%s latency_ms=%d llm_calls=%d input_tokens=%d output_tokens=%d"
                " grounding_retries=%d grounding_fallbacks=%d",
                outcome,
                model,
                round((perf_counter() - started) * 1000),
                usage.calls,
                usage.input_tokens,
                usage.output_tokens,
                usage.grounding_retries,
                usage.grounding_fallbacks,
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
            claims = await self._ground(client, prompt, sentences, _dedupe_and_cap(extraction.claims), usage)
            sample_results = await asyncio.gather(*sample_tasks)
        except BaseException:
            await _cancel(sample_tasks)
            raise
        for result in sample_results:
            usage.add(result)
        samples = [result.text for result in sample_results]
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

    def _ungrounded(self, claim: ExtractedClaim, prompt: str, sentences: tuple[Sentence, ...]) -> list[str]:
        return ungrounded_terms(
            claim.claim,
            _source_text(claim, sentences),
            prompt,
            " ".join(sentence.text for sentence in sentences),
        )

    async def _ground(
        self,
        client: LLMClient,
        prompt: str,
        sentences: tuple[Sentence, ...],
        claims: list[ExtractedClaim],
        usage: _Usage,
    ) -> list[ExtractedClaim]:
        """Keep claims to what the answer says: one stricter re-extraction, then the source sentence."""
        if not any(self._ungrounded(claim, prompt, sentences) for claim in claims):
            return claims
        usage.grounding_retries += 1
        try:
            retry = await self._extract(client, prompt, sentences, usage, strict=True)
            if retry.answer_type == "factual" and retry.claims:
                claims = _dedupe_and_cap(retry.claims)
        except MalformedOutputError:
            pass  # keep the first extraction; failing claims fall back to their sentences below
        grounded = []
        for claim in claims:
            if self._ungrounded(claim, prompt, sentences):
                usage.grounding_fallbacks += 1
                claim = claim.model_copy(update={"claim": _source_text(claim, sentences)[:2_000]})
            grounded.append(claim)
        return _dedupe_and_cap(grounded)

    async def _extract(
        self,
        client: LLMClient,
        prompt: str,
        sentences: tuple[Sentence, ...],
        usage: _Usage,
        strict: bool = False,
    ) -> Extraction:
        numbered = "\n".join(f"[{sentence.index}] {sentence.text}" for sentence in sentences)
        user = f"Question:\n<question>\n{prompt}\n</question>\n\nAnswer sentences:\n<answer>\n{numbered}\n</answer>"

        def parse(text: str) -> Extraction:
            extraction = Extraction.model_validate(json.loads(text))
            valid = range(len(sentences))
            if any(index not in valid for claim in extraction.claims for index in claim.sentence_indices):
                raise ValueError("sentence index out of range")
            return extraction

        system = EXTRACT_SYSTEM + STRICT_EXTRACT_SUFFIX if strict else EXTRACT_SYSTEM
        return await _call_json(
            client, system, user, EXTRACTION_SCHEMA, parse, usage, model=self.settings.llm_extraction_model
        )

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
        assessments = [self._assess(claim, high, medium) for claim in claims]
        weakest = weakest_claim(claims)
        if weakest is None:
            explanation = (
                f"None of the {len(claims)} claims was mentioned by at least {MIN_MENTIONS} of the "
                f"{self.settings.selfconsistency_samples} independent attempts, so none could be checked."
            )
            return SignalResponse(
                confidence=None,
                assessmentState="insufficient_evidence",
                score=None,
                claimAssessments=assessments,
                explanation=explanation,
                modelVersion="pending",
                processingLatencyMs=0,
            )
        score = weakest.support_rate
        state = state_for(score, high, medium)
        not_checked = sum(not claim.addressed for claim in claims)

        # Only addressed claims below the medium threshold are flagged; with at least
        # MIN_MENTIONS mentions, support below it always means some attempt contradicted it.
        flagged: dict[int, list[ClaimConsistency]] = {}
        for claim in claims:
            if claim.addressed and claim.support_rate < medium:
                for index in claim.sentence_indices:
                    flagged.setdefault(index, []).append(claim)
        flags = [
            SentenceFlag(
                sentence_index=index,
                label="low_agreement",
                explanation="; ".join(
                    f"{claim.contradicted} of {claim.mentions} attempts that mentioned a claim here contradicted it"
                    for claim in items
                ),
                claim_ids=[claim.claim_id for claim in items],
            )
            for index, items in sorted(flagged.items())
        ]
        return SignalResponse(
            confidence=state,
            assessmentState=state,
            score=score,
            sentenceFlags=flags,
            claimAssessments=assessments,
            explanation=agreement_reason(weakest, f'"{short_claim(weakest.text)}"', not_checked),
            # The stored copy must not contain claim text, so it names the claim by id instead.
            stored_explanation=agreement_reason(weakest, f"claim {weakest.claim_id}", not_checked),
            modelVersion="pending",
            processingLatencyMs=0,
        )

    def _assess(self, claim: ClaimConsistency, high: float, medium: float) -> ClaimAssessment:
        samples = len(claim.verdicts)
        supporting = [f"sample-{i + 1}" for i, v in enumerate(claim.verdicts) if v == "supported"]
        contradicting = [f"sample-{i + 1}" for i, v in enumerate(claim.verdicts) if v == "contradicted"]
        if not claim.addressed:
            return ClaimAssessment(
                claim_id=claim.claim_id,
                claim=claim.text,
                assessment="not_addressed",
                confidence="low",
                evidence_strength=f"mentioned by {claim.mentions} of {samples} samples",
                uncertainty=None,
                supporting_source_ids=supporting,
                contradicting_source_ids=contradicting,
            )
        level = state_for(claim.support_rate, high, medium)
        return ClaimAssessment(
            claim_id=claim.claim_id,
            claim=claim.text,
            assessment={"high": "consistent", "medium": "partially_consistent", "low": "inconsistent"}[level],
            confidence=level,
            evidence_strength=f"{claim.supported} of {claim.mentions} mentions supported ({samples} samples)",
            uncertainty=round(1 - claim.support_rate, 4),
            supporting_source_ids=supporting,
            contradicting_source_ids=contradicting,
        )

    def _version(self, model: str) -> str:
        extraction_model = self.settings.llm_extraction_model
        if extraction_model and extraction_model != model:
            return f"{MODEL_VERSION_PREFIX}:{model}+extract:{extraction_model}"[:100]
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


def _source_text(claim: ExtractedClaim, sentences: tuple[Sentence, ...]) -> str:
    return " ".join(sentences[index].text for index in sorted(set(claim.sentence_indices)))


async def _call_json(
    client: LLMClient,
    system: str,
    user: str,
    schema: dict[str, Any],
    parse,
    usage: _Usage,
    model: str | None = None,
):
    """One call plus one retry on unparseable or invalid JSON."""
    for _ in range(2):
        if model:
            result = await client.complete(system=system, prompt=user, json_schema=schema, model=model)
        else:
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
