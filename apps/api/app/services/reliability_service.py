from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Protocol

from app.config import get_settings
from app.schemas.signal import (
    ClaimAssessment,
    SentenceFlag,
    SignalRequest,
    SignalResponse,
)

MAX_CLAIMS = 8
MATERIALITY_WEIGHTS = {"high": 3, "medium": 2, "low": 1}
FACTUAL_TYPES = {"factual", "quantitative", "temporal", "causal", "attribution", "definition"}


class ProviderUnavailableError(RuntimeError):
    pass


def resolve_fixture_path(path: str | None, fixture_dir: str) -> Path | None:
    if path is None:
        return None
    root = Path(fixture_dir).expanduser().resolve()
    candidate = (root / path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ProviderUnavailableError("Evidence fixture path is outside the configured fixture directory")
    return candidate


@dataclass(frozen=True)
class Sentence:
    index: int
    text: str
    is_code: bool = False


@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    sentence_index: int
    claim_type: str
    materiality: str
    time_sensitive: bool


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    url: str
    title: str
    publisher: str
    domain: str
    retrieved_at: str
    published_at: str | None
    snippet: str
    relevance_score: float
    quality: float
    independence_group: str


@dataclass(frozen=True)
class Verification:
    claim: Claim
    outcome: str
    evidence_strength: str
    uncertainty: float
    supporting: tuple[EvidenceSource, ...]
    contradicting: tuple[EvidenceSource, ...]
    explanation: str


class EvidenceRetriever(Protocol):
    def retrieve(self, claim: Claim) -> tuple[EvidenceSource, ...]:
        ...


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def normalize_answer(answer: str) -> tuple[Sentence, ...]:
    text = answer.replace("\r\n", "\n").replace("\r", "\n").strip()
    sentences: list[Sentence] = []
    in_code = False
    buffer: list[str] = []
    index = 0
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            if buffer:
                sentences.append(Sentence(index, " ".join(buffer).strip(), in_code))
                index += 1
                buffer = []
            in_code = not in_code
            continue
        if not line.strip() and buffer and not in_code:
            sentences.append(Sentence(index, " ".join(buffer).strip()))
            index += 1
            buffer = []
            continue
        if in_code:
            buffer.append(line)
            continue
        buffer.append(re.sub(r"^\s*(?:[-*+]|\d+[.)])\s+", "", line).strip())
    if buffer:
        sentences.append(Sentence(index, " ".join(buffer).strip(), in_code))

    split: list[Sentence] = []
    for sentence in sentences:
        if sentence.is_code:
            split.append(sentence)
            continue
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])", sentence.text)
        for part in parts:
            if part.strip() and not part.lstrip().startswith("#"):
                split.append(Sentence(len(split), part.strip()))
    return tuple(split)


def extract_claims(sentences: tuple[Sentence, ...]) -> tuple[Claim, ...]:
    candidates: list[Claim] = []
    for sentence in sentences:
        if sentence.is_code or not sentence.text or sentence.text.startswith(("#", ">")):
            continue
        lowered = sentence.text.lower()
        if any(marker in lowered for marker in ("i think", "in my opinion", "you should", "might ", "could ")):
            continue
        claim_type = "quantitative" if re.search(r"\b\d+(?:\.\d+)?%?\b", sentence.text) else "factual"
        materiality = "high" if len(sentence.text) >= 140 else "medium" if len(sentence.text) >= 60 else "low"
        time_sensitive = bool(re.search(r"\b(today|currently|now|latest|as of|recent)\b", lowered))
        digest = hashlib.sha256(_normalize(sentence.text).encode()).hexdigest()[:12]
        candidates.append(
            Claim(f"clm_{digest}", sentence.text, sentence.index, claim_type, materiality, time_sensitive)
        )
    candidates.sort(key=lambda claim: ({"high": 0, "medium": 1, "low": 2}[claim.materiality], claim.sentence_index))
    return tuple(candidates[:MAX_CLAIMS])


class FixtureEvidenceRetriever:
    """Loads only explicitly configured evidence; it never invents citations."""

    def __init__(
        self,
        path: str | None = None,
        records: list[dict] | None = None,
        fixture_dir: str | None = None,
    ):
        if records is not None:
            self.records = records
        elif path:
            path = str(resolve_fixture_path(path, fixture_dir or get_settings().evidence_fixture_dir))
            try:
                self.records = json.loads(Path(path).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise ProviderUnavailableError("Evidence fixture is unavailable") from error
        else:
            self.records = []

    def retrieve(self, claim: Claim) -> tuple[EvidenceSource, ...]:
        target = _normalize(claim.text)
        results: list[EvidenceSource] = []
        for record in self.records:
            if _normalize(str(record.get("claim", ""))) != target:
                continue
            url = str(record.get("url", ""))
            if not url.startswith(("https://", "http://")):
                continue
            results.append(
                EvidenceSource(
                    source_id=str(record["sourceId"]),
                    url=url,
                    title=str(record.get("title", "")),
                    publisher=str(record.get("publisher", "")),
                    domain=str(record.get("domain", "")),
                    retrieved_at=str(record.get("retrievedAt") or datetime.now(timezone.utc).isoformat()),
                    published_at=record.get("publishedAt"),
                    snippet=str(record.get("snippet", "")),
                    relevance_score=float(record.get("relevanceScore", 0)),
                    quality=float(record.get("quality", 0)),
                    independence_group=str(record.get("independenceGroup") or record.get("domain", "")),
                )
            )
        unique: dict[tuple[str, str], EvidenceSource] = {}
        for source in results:
            unique[(source.independence_group, source.url)] = source
        return tuple(unique.values())


def verify_claim(claim: Claim, sources: tuple[EvidenceSource, ...]) -> Verification:
    supporting = tuple(source for source in sources if source.relevance_score > 0 and source.quality >= 0.6)
    contradicting = tuple(source for source in sources if source.relevance_score < 0 and source.quality >= 0.6)
    if supporting and contradicting:
        return Verification(claim, "insufficient_evidence", "moderate", 0.7, supporting, contradicting, "Evidence conflicts.")
    if supporting:
        strength = "strong" if len({source.independence_group for source in supporting}) >= 2 else "moderate"
        return Verification(claim, "supported", strength, 0.15, supporting, (), "Independent evidence supports this claim.")
    if contradicting:
        return Verification(claim, "contradicted", "strong", 0.2, (), contradicting, "Evidence contradicts this claim.")
    return Verification(claim, "insufficient_evidence", "none", 1.0, (), (), "No sufficient evidence was available.")


def aggregate(verifications: tuple[Verification, ...]) -> tuple[str, str, float]:
    if not verifications:
        return "abstained", "No independently verifiable claims were extracted.", 0.0
    if all(item.outcome == "insufficient_evidence" for item in verifications):
        return "insufficient_evidence", "Available evidence cannot establish these claims.", 0.0
    denominator = sum(MATERIALITY_WEIGHTS[item.claim.materiality] for item in verifications)
    supported = sum(
        MATERIALITY_WEIGHTS[item.claim.materiality] for item in verifications if item.outcome == "supported"
    )
    score = supported / denominator
    if any(item.outcome == "contradicted" and item.claim.materiality == "high" for item in verifications):
        return "low", "A high-materiality claim is contradicted by evidence.", score
    if any(item.outcome == "insufficient_evidence" and item.claim.materiality == "high" for item in verifications):
        return "medium", "A high-materiality claim lacks sufficient evidence.", score
    if score >= 0.8:
        return "high", "Evidence supports the material claims in this answer.", score
    if score >= 0.6:
        return "medium", "Evidence supports some claims, but uncertainty remains.", score
    return "low", "Evidence indicates that important claims are not reliable.", score


class ReliabilityFixtureProvider:
    def __init__(self, retriever: EvidenceRetriever | None = None):
        settings = get_settings()
        self.retriever = retriever or FixtureEvidenceRetriever(
            settings.evidence_fixture_path,
            fixture_dir=settings.evidence_fixture_dir,
        )

    def evaluate(self, request: SignalRequest) -> SignalResponse:
        started = perf_counter()
        if not request.answer:
            return SignalResponse(
                confidence=None, assessmentState="unavailable", score=0,
                explanation="An answer was not available for evaluation.",
                modelVersion="reliability-fixture-v1",
                processingLatencyMs=0,
            )
        claims = extract_claims(normalize_answer(request.answer))
        verifications = tuple(verify_claim(claim, self.retriever.retrieve(claim)) for claim in claims)
        state, explanation, score = aggregate(verifications)
        confidence = state if state in {"high", "medium", "low"} else None
        flags = [
            SentenceFlag(
                sentence_index=item.claim.sentence_index,
                label=item.outcome,
                explanation=item.explanation,
                claim_ids=[item.claim.claim_id],
            )
            for item in verifications
        ]
        assessments = [
            ClaimAssessment(
                claim_id=item.claim.claim_id,
                claim=item.claim.text,
                assessment=item.outcome,
                confidence="high" if item.uncertainty < 0.3 else "medium" if item.uncertainty < 0.7 else "low",
                evidence_strength=item.evidence_strength,
                uncertainty=item.uncertainty,
                supporting_source_ids=[source.source_id for source in item.supporting],
                contradicting_source_ids=[source.source_id for source in item.contradicting],
            )
            for item in verifications
        ]
        return SignalResponse(
            confidence=confidence,
            assessmentState=state,
            score=score,
            sentenceFlags=flags,
            claimAssessments=assessments,
            explanation=explanation,
            modelVersion="reliability-fixture-v1",
            processingLatencyMs=max(0, round((perf_counter() - started) * 1000)),
        )
