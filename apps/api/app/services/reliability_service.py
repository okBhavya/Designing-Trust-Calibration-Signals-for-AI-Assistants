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
