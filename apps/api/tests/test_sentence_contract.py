"""Backend half of the sentence-splitting contract with the study harness.

Sentence flags refer to sentences by index, so the harness (apps/study/src/sentences.ts) must split an
answer exactly as normalize_answer does. This test checks contracts/sentence_splits.json against the
backend; apps/study/src/sentences.test.ts checks the harness against the same file.

Regenerate after an intentional change:  UPDATE_CONTRACT=1 python -m pytest tests/test_sentence_contract.py
"""

import json
import os
from pathlib import Path

from app.services.reliability_service import normalize_answer

REPO = Path(__file__).resolve().parents[3]
CONTRACT = REPO / "contracts" / "sentence_splits.json"
PRACTICE_IDS = ("nq-153", "nq-1232")  # apps/study/src/practice.ts

EDGE_CASES = [
    "Dr. Smith arrived at 3.5 p.m. on Jan. 4. He left early.",
    "It was built in 1889! Was it the tallest? \"Yes,\" they said. 'Maybe' others said.",
    "First paragraph ends here.\n\nSecond paragraph starts. It has two sentences.",
    "- First bullet point.\n- Second bullet. With more text.\n1. Numbered item.\n2) Another item.",
    "# Heading line\nBody sentence follows. Another one.",
    "Before code.\n```python\nprint('a. B')\n```\nAfter code. Done.",
    "lowercase start. continues here. Then Capital.",
    "Windows line endings.\r\nSecond line. Third.\r\n\r\nNew paragraph.",
    "Ends without punctuation",
    "Trailing spaces.   Many   spaces. ",
]


def _answers() -> list[str]:
    items = json.loads((REPO / "data" / "questions.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (REPO / "data" / "validation" / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    practice = [row["answer"] for row in rows if row["id"] in PRACTICE_IDS]
    return [item["ai_answer"] for item in items] + practice + EDGE_CASES


def _cases() -> list[dict]:
    return [
        {"answer": answer, "sentences": [{"index": s.index, "text": s.text, "isCode": s.is_code} for s in normalize_answer(answer)]}
        for answer in _answers()
    ]


def test_sentence_split_contract_matches_the_backend():
    cases = _cases()
    if os.environ.get("UPDATE_CONTRACT"):
        CONTRACT.write_text(json.dumps(cases, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert json.loads(CONTRACT.read_text(encoding="utf-8")) == cases


def test_study_flags_point_at_real_sentences():
    items = json.loads((REPO / "data" / "questions.json").read_text(encoding="utf-8"))
    for item in items:
        count = len(normalize_answer(item["ai_answer"]))
        assert all(0 <= index < count for index in item["signal"]["flagged_sentence_indices"]), item["id"]
