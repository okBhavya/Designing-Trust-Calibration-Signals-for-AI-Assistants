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
