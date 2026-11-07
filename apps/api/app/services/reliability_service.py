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
