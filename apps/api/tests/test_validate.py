"""Offline tests for scripts/validate.py: no network and no LLM calls."""

import asyncio
import importlib.util
import json
import random
import sys
from pathlib import Path

import pytest

from app.config import Settings
from app.services.llm_client import LLMResult, LLMUnavailableError
from app.services.selfconsistency_service import EXTRACT_SYSTEM, JUDGE_SYSTEM, SAMPLE_SYSTEM

_spec = importlib.util.spec_from_file_location("validate", Path(__file__).resolve().parents[1] / "scripts" / "validate.py")
validate = importlib.util.module_from_spec(_spec)
sys.modules["validate"] = validate  # dataclasses resolve their module through sys.modules
_spec.loader.exec_module(validate)


def row(i, label, score, level=None, source="nq_open"):
    level = level or (None if score is None else validate.level_for(score, 0.8, 0.6))
    return {
        "id": f"q-{i:03d}", "source": source, "domain": "general knowledge", "question": f"question {i}",
        "gold_answers": ["gold"], "answer": f"answer {i}", "label": label, "label_source": "exact",
        "level": level, "score": score, "explanation": "reason", "claimAssessments": [],
        "sentenceFlags": [{"sentenceIndex": 0, "label": "low_agreement"}] if level == "low" else [],
        "model_version": "selfconsistency-v1:fake", "latency_ms": 1000 + i,
        "cost_usd": {"signal": 0.001, "total": 0.0012},
    }


# --- labelling ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer,gold,expected",
    [
        ("The capital of France is Paris.", ["paris"], True),
        ("About 1,000 people attended.", ["1000"], True),
        ("It was written by Bob Russell and Bobby Scott.", ["Bobby Scott", "Bob Russell"], True),
        ("He was a Parisian painter.", ["Paris"], False),  # whole words only
        ("It opened in 1902.", ["1889"], False),
        ("Anything.", [""], False),
    ],
)
def test_exact_match_uses_normalized_whole_words(answer, gold, expected):
    assert validate.exact_match(answer, gold) is expected


# --- split, exclusions, tuning ----------------------------------------------------------------------


def test_split_is_seeded_and_reports_exclusions():
    results = [row(i, "correct", 0.9) for i in range(10)] + [
        row(10, "not_attempted", 0.5),
        row(11, "incorrect", None, level="insufficient_evidence"),
        row(12, "correct", None, level="unavailable"),
    ]
    a1, b1, excluded = validate.split_eligible(results)
    a2, b2, _ = validate.split_eligible(list(reversed(results)))
    assert [r["id"] for r in a1] == [r["id"] for r in a2] and len(a1) + len(b1) == 10
    assert excluded == {
        "answer not_attempted (no committed answer to grade)": 1,
        "no score: signal was insufficient_evidence": 1,
        "no score: signal was unavailable": 1,
    }


def test_thresholds_are_tuned_on_half_a():
    rows = [row(i, "correct", 1.0) for i in range(6)] + [row(10 + i, "correct", 0.6) for i in range(4)]
    rows += [row(20 + i, "incorrect", 0.2) for i in range(6)] + [row(30 + i, "incorrect", 0.6) for i in range(2)]
    high, medium, note = validate.tune_thresholds(rows)
    assert medium == pytest.approx(0.6)  # best balanced accuracy: (10/10 + 6/8) / 2
    assert high == pytest.approx(0.8)  # 0.6 gives 10/12 precision; 0.8 is the first to reach 90%
    assert "tuned" in note

    one_class = [row(i, "correct", 0.9) for i in range(4)]
    assert validate.tune_thresholds(one_class)[:2] == (0.80, 0.60)


def test_analysis_on_synthetic_results_uses_wilson_and_reports_half_b():
    rng = random.Random(1)
    results = [row(i, "correct", rng.choice([0.8, 1.0])) for i in range(40)]
    results += [row(100 + i, "incorrect", rng.choice([0.0, 0.25, 0.6])) for i in range(20)]
    analysis = validate.analyze(results)
    assert analysis["half_a"] + analysis["half_b"] == 60
    assert analysis["auroc"][0] > 0.9
    assert 0 <= analysis["ece"] <= 1 and 0 <= analysis["brier"] <= 1
    assert all(row["ci"] is None or 0 <= row["ci"][0] <= row["ci"][1] <= 1 for row in analysis["half_b_table"])
    assert analysis["latency_p50"] == pytest.approx(1029.5)  # median of 1000-1039 and 1100-1119


def test_reliability_diagram_is_written(tmp_path):
    results = [row(i, "correct", 1.0) for i in range(6)] + [row(10 + i, "incorrect", 0.2) for i in range(6)]
    path = tmp_path / "diagram.png"
    assert validate.reliability_diagram(validate.analyze(results), path)
    assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


# --- study items ------------------------------------------------------------------------------------


def _pool():
    correct = [row(i, "correct", 1.0) for i in range(30)] + [row(30 + i, "correct", 0.6) for i in range(10)]
    incorrect = [row(100 + i, "incorrect", 0.0) for i in range(9)] + [row(120 + i, "incorrect", 1.0) for i in range(6)]
    return correct + incorrect


def test_study_set_has_21_correct_and_9_incorrect_with_the_measured_mix():
    items, info = validate.select_study_items(_pool())
    assert len(items) == 30
    assert sum(item["ai_is_correct"] for item in items) == 21
    levels_correct = sorted(item["signal"]["level"] for item in items if item["ai_is_correct"])
    assert levels_correct.count("high") == 16 and levels_correct.count("medium") == 5  # 30:10 of 21, rounded
    levels_incorrect = [item["signal"]["level"] for item in items if not item["ai_is_correct"]]
    assert levels_incorrect.count("high") == 4  # 6 of 15 incorrect answers were scored high
    # Not a perfect signal: its hit rate on the 30 matches what was measured.
    assert info["study_hit_rate"] == pytest.approx(info["expected_hit_rate_at_21_9"], abs=0.05)
    assert set(items[0]) == {"id", "domain", "prompt", "ai_answer", "ground_truth", "ai_is_correct", "signal", "difficulty"}
    assert set(items[0]["signal"]) == {
        "level", "score", "flagged_sentence_indices", "reason", "sentence_flags", "claim_assessments", "model_version",
    }


def test_study_set_is_not_built_without_nine_real_wrong_answers():
    pool = [row(i, "correct", 1.0) for i in range(30)] + [row(100 + i, "incorrect", 0.0) for i in range(8)]
    items, info = validate.select_study_items(pool)
    assert items is None and info["available"] == {"correct": 30, "incorrect": 8}


# --- resumable run with a fake LLM -------------------------------------------------------------------


class FakeInner:
    model = "fake-model"

    def __init__(self, fail_on=None, rate_limit_once=False):
        self.calls = []
        self.fail_on = fail_on
        self.rate_limit_once = rate_limit_once

    async def complete(self, *, system, prompt, json_schema=None, temperature=None, model=None):
        self.calls.append(system[:20])
        if self.rate_limit_once and system == validate.ANSWER_SYSTEM:
            self.rate_limit_once = False
            raise LLMUnavailableError("RateLimitError")
        if system == validate.ANSWER_SYSTEM:
            if self.fail_on and self.fail_on in prompt:
                raise LLMUnavailableError("AuthenticationError")
            return LLMResult("The Eiffel Tower is in Paris.", 10, 20)
        if system == validate.LABEL_SYSTEM:
            return LLMResult(json.dumps({"verdict": "incorrect", "reason": "different city"}), 30, 5)
        if system.startswith(EXTRACT_SYSTEM):
            claims = [{"claim": "The Eiffel Tower is in Paris.", "sentence_indices": [0], "materiality": "high"}]
            return LLMResult(json.dumps({"answer_type": "factual", "claims": claims}), 50, 20)
        if system == JUDGE_SYSTEM:
            return LLMResult(json.dumps({"claims": [{"claim_index": 0, "verdicts": ["supported"] * 5}]}), 80, 20)
        assert system == SAMPLE_SYSTEM
        return LLMResult("It is in Paris.", 5, 10)

    async def aclose(self):
        pass


def test_run_is_incremental_and_resumable(tmp_path, monkeypatch):
    real_sleep = asyncio.sleep
    monkeypatch.setattr(validate.asyncio, "sleep", lambda *_: real_sleep(0))  # no real backoff waits
    monkeypatch.setitem(validate.PRICES, "fake-model", (1.0, 2.0))
    questions = [
        {"id": "q1", "question": "Where is the Eiffel Tower?", "gold_answers": ["Paris"], "source": "nq_open"},
        {"id": "q2", "question": "Which city has the Eiffel Tower?", "gold_answers": ["Lyon"], "source": "simpleqa"},
        {"id": "q3", "question": "FAIL where is it?", "gold_answers": ["Paris"], "source": "nq_open"},
    ]
    results = tmp_path / "results.jsonl"
    settings = Settings()
    inner = FakeInner(fail_on="FAIL", rate_limit_once=True)
    failures = asyncio.run(validate.run_questions(questions, results, inner, settings, concurrency=2))
    rows = {r["id"]: r for r in validate.load_jsonl(results)}
    assert failures == 1 and set(rows) == {"q1", "q2"}  # the failed item is not recorded, so it is retried later
    assert (rows["q1"]["label"], rows["q1"]["label_source"]) == ("correct", "exact")
    assert (rows["q2"]["label"], rows["q2"]["label_source"]) == ("incorrect", "judge")
    assert rows["q1"]["level"] == "high" and rows["q1"]["score"] == 1.0
    assert rows["q1"]["tokens"]["signal"]["input"] > 0 and rows["q1"]["cost_usd"]["signal"] > 0

    calls_before = len(inner.calls)
    inner.fail_on = None
    assert asyncio.run(validate.run_questions(questions, results, inner, settings, concurrency=2)) == 0
    assert {r["id"] for r in validate.load_jsonl(results)} == {"q1", "q2", "q3"}
    assert len(inner.calls) - calls_before == 8  # only q3 ran: answer + 7 signal calls (exact-match label)


def test_results_from_another_engine_version_are_re_run(tmp_path, monkeypatch):
    real_sleep = asyncio.sleep
    monkeypatch.setattr(validate.asyncio, "sleep", lambda *_: real_sleep(0))
    questions = [
        {"id": "q1", "question": "Where is the Eiffel Tower?", "gold_answers": ["Paris"], "source": "nq_open"},
        {"id": "q2", "question": "Which city has the Eiffel Tower?", "gold_answers": ["Paris"], "source": "nq_open"},
    ]
    results = tmp_path / "results.jsonl"
    current = "selfconsistency-v2:fake-model"
    old = {**row(1, "correct", 1.0), "id": "q1", "model_version": "selfconsistency-v1:fake-model"}
    kept = {**row(2, "correct", 1.0), "id": "q2", "model_version": current}
    results.write_text(json.dumps(old) + "\n" + json.dumps(kept) + "\n", encoding="utf-8")

    inner = FakeInner()
    assert asyncio.run(validate.run_questions(questions, results, inner, Settings(), 2, engine_version=current)) == 0
    rows = validate.load_jsonl(results)
    assert sorted(r["id"] for r in rows) == ["q1", "q2"]
    assert {r["model_version"] for r in rows} == {current}
    assert len(inner.calls) == 8  # only q1 was re-run


def test_items_needing_label_review_stay_out_of_the_study_set(tmp_path, monkeypatch):
    pool = _pool()
    flagged = pool[0]["id"]  # a correct item that would otherwise be eligible
    review = {flagged: "possible gold-label error, needs human check"}
    items, info = validate.select_study_items(pool, exclude=review)
    assert flagged not in {item["id"] for item in items}
    assert info["excluded_for_review"] == [flagged]

    monkeypatch.setattr(validate, "REPORT", tmp_path / "report.md")
    analysis = validate.analyze(pool)
    text = validate.write_report(analysis, info, True, len(pool), False, review, pool)
    assert "## Labels needing human review" in text
    assert f"| `{flagged}` | correct (exact) | high, 1.00 | possible gold-label error, needs human check |" in text
    assert f"Kept out for human review: `{flagged}`" in text


def test_review_items_are_dropped_from_the_same_split_and_levels_keep_the_configured_thresholds(tmp_path, monkeypatch):
    rng = random.Random(1)
    results = [row(i, "correct", rng.choice([0.8, 1.0])) for i in range(40)]
    results += [row(100 + i, "incorrect", rng.choice([0.0, 0.25, 1.0])) for i in range(20)]
    results += [row(200, "not_attempted", None, level="abstained"), row(201, "not_attempted", 0.5)]
    review = {"q-100": "possible gold-label error, needs human check", "q-101": "same"}

    full = validate.analyze(results)
    reviewed = validate.analyze(results, exclude=review)
    _, b_full, _ = validate.split_eligible(results)
    assert reviewed["half_a"] + reviewed["half_b"] == full["n_eligible"] - 2
    assert reviewed["excluded"]["label needs human review"] == 2
    # dropped after the split, not reshuffled
    kept_b = [r["id"] for r in b_full if r["id"] not in review]
    assert reviewed["half_b"] == len(kept_b)
    assert full["thresholds"] == reviewed["thresholds"] == (0.80, 0.60)
    assert sum(r["n"] for r in reviewed["production_table"]) == len(results) - 2
    assert full["abstained_labels"] == {"not_attempted": 1}
    assert full["unattempted_but_scored"] == ["q-201"]

    monkeypatch.setattr(validate, "REPORT", tmp_path / "report.md")
    text = validate.write_report(full, {"available": {"correct": 0, "incorrect": 0}}, False, len(results), False,
                                 review, results, reviewed)
    assert text.index("## Key findings") < text.index("## Run")
    assert "ranks answers well but is poorly calibrated" in text
    assert "so it is not applied" in text
    assert "Refusals are abstained, not scored." in text and "`q-201`" in text
    assert "reported but not applied" in text
    assert "## All items vs. review items excluded" in text
    assert "configured thresholds (0.80 / 0.60)" in text
