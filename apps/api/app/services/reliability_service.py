from __future__ import annotations

class ProviderUnavailableError(RuntimeError):
    pass

import re
from dataclasses import dataclass

@dataclass(frozen=True)
class Sentence:
    index: int
    text: str
    is_code: bool = False

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

import hashlib

MAX_CLAIMS = 8
MATERIALITY_WEIGHTS = {"high": 3, "medium": 2, "low": 1}
FACTUAL_TYPES = {"factual", "quantitative", "temporal", "causal", "attribution", "definition"}

@dataclass(frozen=True)
class Claim:
    claim_id: str
    text: str
    sentence_index: int
    claim_type: str
    materiality: str
    time_sensitive: bool

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

import json
from pathlib import Path
from typing import Protocol

def resolve_fixture_path(path: str | None, fixture_dir: str) -> Path | None:
    if path is None:
        return None
    root = Path(fixture_dir).expanduser().resolve()
    candidate = (root / path).resolve()
    if candidate != root and root not in candidate.parents:
        raise ProviderUnavailableError("Evidence fixture path is outside the configured fixture directory")
    return candidate

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

class EvidenceRetriever(Protocol):
    def retrieve(self, claim: Claim) -> tuple[EvidenceSource, ...]:
        ...

class FixtureEvidenceRetriever:
    def __init__(self, fixture_path: str | Path | None = None, *, fixture_dir: str = "data/evidence_fixtures", records: list[dict] | None = None):
        self.records = records if records is not None else self._load(fixture_path, fixture_dir)

    def _load(self, fixture_path: str | Path | None, fixture_dir: str) -> list[dict]:
        if not fixture_path:
            return []
        resolved = resolve_fixture_path(str(fixture_path), fixture_dir)
        if not resolved or not resolved.exists():
            raise ProviderUnavailableError(f"Evidence fixture not found: {fixture_path}")
        return json.loads(resolved.read_text(encoding="utf-8"))

    def retrieve(self, claim: Claim) -> tuple[EvidenceSource, ...]:
        claim_norm = _normalize(claim.text)
        results: list[EvidenceSource] = []
        for record in self.records:
            record_norm = _normalize(record.get("claim", ""))
            overlap = set(claim_norm.split()) & set(record_norm.split())
            if record_norm in claim_norm or claim_norm in record_norm or len(overlap) >= 3:
                results.append(
                    EvidenceSource(
                        source_id=record["sourceId"],
                        url=record["url"],
                        title=record.get("title", ""),
                        publisher=record.get("publisher", ""),
                        domain=record.get("domain", ""),
                        retrieved_at=record.get("retrievedAt", ""),
                        published_at=record.get("publishedAt"),
                        snippet=record.get("snippet", ""),
                        relevance_score=float(record.get("relevanceScore", 1.0)),
                        quality=float(record.get("quality", 1.0)),
                        independence_group=record.get("independenceGroup", record.get("domain", record["sourceId"])),
                    )
                )
        unique: dict[tuple[str, str], EvidenceSource] = {}
        for source in results:
            unique[(source.independence_group, source.url)] = source
        return tuple(unique.values())

@dataclass(frozen=True)
class Verification:
    claim: Claim
    outcome: str
    evidence_strength: str
    uncertainty: float
    supporting: tuple[EvidenceSource, ...]
    contradicting: tuple[EvidenceSource, ...]
    explanation: str

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

from time import perf_counter
from app.config import get_settings
from app.schemas.signal import ClaimAssessment, SentenceFlag, SignalRequest, SignalResponse

class ReliabilityFixtureProvider:
    def __init__(self, retriever: EvidenceRetriever | None = None):
        settings = get_settings()
        self.retriever = retriever or FixtureEvidenceRetriever(
            settings.evidence_fixture_path,
            fixture_dir=settings.evidence_fixture_dir,
        )

    def evaluate(self, request: SignalRequest) -> SignalResponse:
        started = perf_counter()
        claims = extract_claims(normalize_answer(request.answer or ""))
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
