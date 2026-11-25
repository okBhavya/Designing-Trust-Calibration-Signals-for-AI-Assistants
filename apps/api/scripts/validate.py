"""Validate the selfconsistency signal against labelled short factual questions.

Steps (each run does 2-5; step 1 only with --build-questions):
  1. Build data/validation/questions.jsonl from NQ-open (CC BY-SA 3.0) and SimpleQA (MIT).
  2. Ask the LLM each question (2-4 sentences) and label the answer correct / incorrect /
     not_attempted: normalized string match against the gold answers, else an LLM judge.
  3. Run the selfconsistency provider on each answer (concurrency 4, backoff on rate limits),
     appending to data/validation/results.jsonl as each item finishes. Resumable.
  4. Analyse with app/evaluation.py on a seeded 50/50 split (thresholds tuned on half A,
     metrics reported on half B); write report.md and reliability_diagram.png.
  5. Build data/questions.json (30 study items: 21 correct, 9 incorrect) from real results.

Usage (from anywhere; reads apps/api/.env for LLM_API_KEY and CALIBRAI_LLM_MODEL):
  python apps/api/scripts/validate.py --build-questions     # once; downloads the sources
  python apps/api/scripts/validate.py --limit 10            # first 10 questions only
  python apps/api/scripts/validate.py --resume              # continue; skips finished ids
  python apps/api/scripts/validate.py --report-only         # re-analyse existing results
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import csv
import hashlib
import io
import json
import math
import os
import random
import re
import string
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

API_DIR = Path(__file__).resolve().parents[1]
REPO = API_DIR.parents[1]
sys.path.insert(0, str(API_DIR))

DATA = REPO / "data"
VALIDATION = DATA / "validation"
QUESTIONS = VALIDATION / "questions.jsonl"
BUILD_INFO = VALIDATION / "build_info.json"
RESULTS = VALIDATION / "results.jsonl"
REPORT = VALIDATION / "report.md"
DIAGRAM = VALIDATION / "reliability_diagram.png"
STUDY = DATA / "questions.json"
LABEL_REVIEW = VALIDATION / "label_review.json"  # {id: note}: kept in metrics, kept out of the study set

SEED = 20261125
N_NQ, N_SIMPLEQA = 60, 40
STUDY_CORRECT, STUDY_INCORRECT = 21, 9
STUDY_LEVELS = ("high", "medium", "low", "insufficient_evidence")
NQ_INFO = "https://huggingface.co/api/datasets/google-research-datasets/nq_open"
NQ_ROWS = (
    "https://datasets-server.huggingface.co/rows?dataset=google-research-datasets%2Fnq_open"
    "&config=nq_open&split=validation&offset={offset}&length={length}"
)
SIMPLEQA_CSV = "https://openaipublic.blob.core.windows.net/simple-evals/simple_qa_test_set.csv"
TIME_SENSITIVE = re.compile(
    r"\b(current|currently|latest|now|this year|recent|recently|today|newest|as of|so far)\b", re.I
)
# First-party API prices, $ per million tokens (input, output). Haiku's rate is for prompts <= 100K tokens.
PRICES = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-opus-5-5": (4.00, 20.00),
}
TRANSIENT = {"RateLimitError", "OverloadedError", "InternalServerError", "ServiceUnavailableError",
             "APIConnectionError", "APITimeoutError", "DeadlineExceededError"}

ANSWER_SYSTEM = "You are a helpful assistant. Answer the question in 2-4 fluent sentences."
LABEL_SYSTEM = """You grade an AI assistant's answer to a short factual question against reference answers.

- "correct": the answer's main answer means the same as at least one reference (aliases, paraphrases, equivalent formats or units count).
- "incorrect": it commits to a different answer, or contradicts the references.
- "not_attempted": it declines, says it does not know, or does not commit to an answer.

Judge only against the references; do not use your own knowledge of the facts."""
LABEL_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["correct", "incorrect", "not_attempted"]},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
    "additionalProperties": False,
}


# --- 1. questions --------------------------------------------------------------------------------


def _get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "calibrai-validation/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def build_questions() -> None:
    rng = random.Random(SEED)
    retrieved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    nq_info = json.loads(_get(NQ_INFO))
    nq_rows, offset, total = [], 0, None
    while total is None or offset < total:
        page = json.loads(_get(NQ_ROWS.format(offset=offset, length=100)))
        total = page["num_rows_total"]
        nq_rows.extend(page["rows"])
        offset += 100
    nq_pool = [
        row for row in nq_rows
        if row["row"]["answer"] and not TIME_SENSITIVE.search(row["row"]["question"])
    ]
    nq = [
        {"id": f"nq-{row['row_idx']}", "question": row["row"]["question"], "gold_answers": row["row"]["answer"],
         "source": "nq_open", "domain": "general knowledge"}
        for row in rng.sample(nq_pool, N_NQ)
    ]

    csv_bytes = _get(SIMPLEQA_CSV)
    simple_rows = list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8"))))
    simple = []
    for index in sorted(rng.sample(range(len(simple_rows)), N_SIMPLEQA)):
        row = simple_rows[index]
        metadata = ast.literal_eval(row["metadata"])  # a Python-literal dict in the CSV; literal_eval never runs code
        simple.append({"id": f"simpleqa-{index}", "question": row["problem"], "gold_answers": [row["answer"]],
                       "source": "simpleqa", "domain": str(metadata.get("topic") or "unknown")})

    questions = nq + simple
    rng.shuffle(questions)  # so a --limit prefix mixes both sources
    VALIDATION.mkdir(parents=True, exist_ok=True)
    QUESTIONS.write_text("".join(json.dumps(q, ensure_ascii=False) + "\n" for q in questions), encoding="utf-8")
    BUILD_INFO.write_text(json.dumps({
        "seed": SEED,
        "retrieved_at": retrieved_at,
        "nq_open": {"url": NQ_ROWS.split("&offset")[0], "split": "validation", "hf_revision": nq_info.get("sha"),
                    "rows": total, "after_time_sensitive_filter": len(nq_pool), "sampled": N_NQ,
                    "license": "CC BY-SA 3.0"},
        "simpleqa": {"url": SIMPLEQA_CSV, "sha256": hashlib.sha256(csv_bytes).hexdigest(),
                     "rows": len(simple_rows), "sampled": N_SIMPLEQA, "license": "MIT"},
        "time_sensitive_filter": TIME_SENSITIVE.pattern,
        "questions_sha256": hashlib.sha256(QUESTIONS.read_bytes()).hexdigest(),
    }, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(questions)} questions to {QUESTIONS.relative_to(REPO)}")


def load_label_review(path: Path = LABEL_REVIEW) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# --- 2. labelling ---------------------------------------------------------------------------------

_PUNCT = re.compile(f"[{re.escape(string.punctuation)}‘’“”–—]")


def normalize(text: str) -> str:
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text.lower())  # 1,000 -> 1000
    text = _PUNCT.sub(" ", text)
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    return " ".join(text.split())


def exact_match(answer: str, gold_answers: list[str]) -> bool:
    """True when a normalized gold answer appears as whole words in the normalized answer."""
    haystack = f" {normalize(answer)} "
    return any(f" {gold} " in haystack for gold in map(normalize, gold_answers) if gold)


# --- 3. running -----------------------------------------------------------------------------------


@dataclass
class Meter:
    """Counts tokens per model and transient API failures for one phase of one question."""

    tokens: dict[str, list[int]] = field(default_factory=lambda: defaultdict(lambda: [0, 0]))
    transient_errors: int = 0

    def cost(self) -> float | None:
        total = 0.0
        for model, (tokens_in, tokens_out) in self.tokens.items():
            if model not in PRICES:
                return None
            price_in, price_out = PRICES[model]
            total += tokens_in / 1e6 * price_in + tokens_out / 1e6 * price_out
        return round(total, 6)

    def totals(self) -> dict[str, int]:
        return {"input": sum(t[0] for t in self.tokens.values()), "output": sum(t[1] for t in self.tokens.values())}


class MeteredClient:
    """LLMClient wrapper that records usage; aclose is a no-op so the shared client stays open."""

    def __init__(self, inner, meter: Meter):
        self.inner, self.meter, self.model = inner, meter, inner.model

    async def complete(self, *, system, prompt, json_schema=None, temperature=None, model=None):
        from app.services.llm_client import LLMUnavailableError

        try:
            result = await self.inner.complete(
                system=system, prompt=prompt, json_schema=json_schema, temperature=temperature, model=model
            )
        except LLMUnavailableError as error:
            if str(error) in TRANSIENT:
                self.meter.transient_errors += 1
            raise
        counts = self.meter.tokens[model or self.inner.model]
        counts[0] += result.input_tokens
        counts[1] += result.output_tokens
        return result

    async def aclose(self):
        pass


async def with_backoff(call, attempts: int = 6):
    """Retry a call on rate-limit / overload / transient errors with exponential backoff."""
    from app.services.llm_client import LLMUnavailableError

    for attempt in range(attempts):
        try:
            return await call()
        except LLMUnavailableError as error:
            if str(error) not in TRANSIENT or attempt == attempts - 1:
                raise
            await asyncio.sleep(min(60.0, 2.0 * 2**attempt) + random.random())


async def label_answer(client, question: dict, answer: str) -> tuple[str, str, str | None]:
    if exact_match(answer, question["gold_answers"]):
        return "correct", "exact", None
    prompt = (
        f"Question: {question['question']}\n\nReference answers: {json.dumps(question['gold_answers'], ensure_ascii=False)}"
        f"\n\nAssistant's answer:\n<answer>\n{answer}\n</answer>"
    )
    result = await with_backoff(lambda: client.complete(system=LABEL_SYSTEM, prompt=prompt, json_schema=LABEL_SCHEMA))
    verdict = json.loads(result.text)
    if verdict.get("verdict") not in {"correct", "incorrect", "not_attempted"}:
        raise ValueError("label judge returned an invalid verdict")
    return verdict["verdict"], "judge", str(verdict.get("reason", ""))[:500]


async def evaluate_question(question: dict, inner_client, settings, signal_attempts: int = 5) -> dict:
    from app.schemas.signal import SignalRequest
    from app.services.selfconsistency_service import SelfConsistencyProvider

    answer_meter, label_meter = Meter(), Meter()
    started = time.perf_counter()
    answer_result = await with_backoff(
        lambda: MeteredClient(inner_client, answer_meter).complete(system=ANSWER_SYSTEM, prompt=question["question"])
    )
    answer = answer_result.text.strip()
    answer_ms = round((time.perf_counter() - started) * 1000)
    label, label_source, label_reason = await label_answer(MeteredClient(inner_client, label_meter), question, answer)

    request = SignalRequest(
        participant_id=uuid4(), platform="claude", prompt=question["question"], answer=answer,
        answer_hash=hashlib.sha256(answer.encode("utf-8")).hexdigest(),
    )
    signal_meter = Meter()
    for attempt in range(1, signal_attempts + 1):
        attempt_meter = Meter()
        provider = SelfConsistencyProvider(
            client_factory=lambda: MeteredClient(inner_client, attempt_meter), settings=settings
        )
        signal = await provider.aevaluate(request)
        for model, (tokens_in, tokens_out) in attempt_meter.tokens.items():
            signal_meter.tokens[model][0] += tokens_in
            signal_meter.tokens[model][1] += tokens_out
        rate_limited = attempt_meter.transient_errors > 0
        if signal.assessment_state != "unavailable" or not rate_limited or attempt == signal_attempts:
            break
        await asyncio.sleep(min(60.0, 2.0 * 2**attempt) + random.random())

    body = signal.model_dump(by_alias=True)
    total_meter = Meter()
    for meter in (answer_meter, label_meter, signal_meter):
        for model, (tokens_in, tokens_out) in meter.tokens.items():
            total_meter.tokens[model][0] += tokens_in
            total_meter.tokens[model][1] += tokens_out
    return {
        "id": question["id"],
        "source": question["source"],
        "domain": question.get("domain"),
        "question": question["question"],
        "gold_answers": question["gold_answers"],
        "answer_model": inner_client.model,
        "answer": answer,
        "answer_latency_ms": answer_ms,
        "label": label,
        "label_source": label_source,
        "label_reason": label_reason,
        "level": body["assessmentState"],
        "confidence": body["confidence"],
        "score": body["score"],
        "explanation": body["explanation"],
        "claimAssessments": body["claimAssessments"],
        "sentenceFlags": body["sentenceFlags"],
        "model_version": body["modelVersion"],
        "latency_ms": body["processingLatencyMs"],
        "signal_attempts": attempt,
        "tokens": {"answer": answer_meter.totals(), "label": label_meter.totals(), "signal": signal_meter.totals()},
        "cost_usd": {"signal": signal_meter.cost(), "total": total_meter.cost()},
        "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


async def run_questions(
    questions: list[dict],
    results_path: Path,
    inner_client,
    settings,
    concurrency: int,
    engine_version: str | None = None,
) -> int:
    """Evaluate questions not yet in results_path, appending each result as soon as it is done.

    With engine_version, rows produced by any other signal engine version are dropped and re-run,
    so every result in the file comes from the same engine.
    """
    existing = load_jsonl(results_path)
    if engine_version is not None:
        stale = [row for row in existing if row.get("model_version") != engine_version]
        if stale:
            versions = ", ".join(sorted({str(row.get("model_version")) for row in stale}))
            print(f"{len(stale)} result(s) from another engine version ({versions}) will be re-run with {engine_version}")
            existing = [row for row in existing if row.get("model_version") == engine_version]
            temporary = results_path.with_suffix(".jsonl.tmp")
            temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in existing), encoding="utf-8")
            temporary.replace(results_path)
    done = {row["id"] for row in existing}
    todo = [q for q in questions if q["id"] not in done]
    semaphore, lock = asyncio.Semaphore(concurrency), asyncio.Lock()
    failures = 0
    finished = 0
    results_path.parent.mkdir(parents=True, exist_ok=True)

    async def one(question: dict) -> None:
        nonlocal failures, finished
        async with semaphore:
            try:
                row = await evaluate_question(question, inner_client, settings)
            except Exception as error:  # recorded nowhere, so --resume retries it
                failures += 1
                print(f"  ! {question['id']}: {type(error).__name__}: {error}", flush=True)
                return
        async with lock:
            with results_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            finished += 1
            score = "-" if row["score"] is None else f"{row['score']:.2f}"
            print(f"  [{finished}/{len(todo)}] {row['id']:<16} {row['label']:<13} level={row['level']:<21}"
                  f" score={score} {row['latency_ms'] / 1000:.1f}s", flush=True)

    print(f"{len(done)} already done, {len(todo)} to run (concurrency {concurrency})")
    await asyncio.gather(*(one(q) for q in todo))
    return failures


# --- 4. analysis ----------------------------------------------------------------------------------


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * q
    low, high = math.floor(rank), math.ceil(rank)
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def level_for(score: float, high: float, medium: float) -> str:
    return "high" if score >= high else "medium" if score >= medium else "low"


def split_eligible(results: list[dict], seed: int = SEED) -> tuple[list[dict], list[dict], Counter]:
    """Rows usable for binary metrics, split 50/50 with a fixed seed; plus excluded counts by reason."""
    excluded: Counter = Counter()
    eligible = []
    for row in results:
        if row["label"] not in ("correct", "incorrect"):
            excluded[f"answer {row['label']} (no committed answer to grade)"] += 1
        elif row["score"] is None:
            excluded[f"no score: signal was {row['level']}"] += 1
        else:
            eligible.append(row)
    ordered = sorted(eligible, key=lambda row: row["id"])
    random.Random(seed).shuffle(ordered)
    half = (len(ordered) + 1) // 2
    return ordered[:half], ordered[half:], excluded


def tune_thresholds(rows: list[dict], precision_target: float = 0.9) -> tuple[float, float, str]:
    """Medium = threshold with the best balanced accuracy; high = lowest threshold >= medium whose
    precision for 'correct' reaches the target. Falls back to the 0.80 / 0.60 defaults."""
    labels = [row["label"] == "correct" for row in rows]
    if len(set(labels)) < 2:
        return 0.80, 0.60, "not tuned: half A needs both correct and incorrect answers; defaults kept"
    scores = [row["score"] for row in rows]
    candidates = sorted(set(scores) | {0.6, 0.8})
    positives, negatives = sum(labels), len(labels) - sum(labels)

    def balanced_accuracy(threshold: float) -> float:
        tpr = sum(s >= threshold and y for s, y in zip(scores, labels)) / positives
        tnr = sum(s < threshold and not y for s, y in zip(scores, labels)) / negatives
        return (tpr + tnr) / 2

    medium = max(candidates, key=lambda t: (balanced_accuracy(t), -abs(t - 0.6)))
    high = None
    for threshold in candidates:
        chosen = [y for s, y in zip(scores, labels) if s >= threshold]
        if threshold >= medium and chosen and sum(chosen) / len(chosen) >= precision_target:
            high = threshold
            break
    note = f"tuned on half A (n={len(rows)})"
    if high is None:
        high = max(medium, 0.80)
        note += f"; no threshold reached {precision_target:.0%} precision, so high = max(medium, 0.80)"
    return high, medium, note


def level_table(rows: list[dict], levels: list[str]) -> list[dict]:
    from app.evaluation import proportion_confidence_interval

    table = []
    for level, group in ((lvl, [r for r, l in zip(rows, levels) if l == lvl]) for lvl in dict.fromkeys(levels)):
        correct = sum(row["label"] == "correct" for row in group)
        graded = sum(row["label"] in ("correct", "incorrect") for row in group)
        ci = proportion_confidence_interval(correct, graded) if graded else None
        table.append({"level": level, "n": len(group), "correct": correct, "incorrect": graded - correct,
                      "other": len(group) - graded, "accuracy": correct / graded if graded else None, "ci": ci})
    order = {name: i for i, name in enumerate(["high", "medium", "low", "insufficient_evidence", "abstained", "unavailable"])}
    return sorted(table, key=lambda row: order.get(row["level"], 99))


def auroc_with_ci(labels: list[int], scores: list[float], resamples: int = 2000) -> tuple[float, float, float] | None:
    from app.evaluation import binary_auroc

    if len(set(labels)) < 2:
        return None
    estimate = binary_auroc(labels, scores)
    rng, samples = random.Random(SEED), []
    pairs = list(zip(labels, scores))
    for _ in range(resamples):
        draw = [pairs[rng.randrange(len(pairs))] for _ in pairs]
        if len({label for label, _ in draw}) == 2:  # one-class resamples have no AUROC; skip them
            samples.append(binary_auroc([l for l, _ in draw], [s for _, s in draw]))
    samples.sort()
    if not samples:
        return estimate, float("nan"), float("nan")
    return estimate, samples[int(0.025 * (len(samples) - 1))], samples[int(0.975 * (len(samples) - 1))]


CONFIGURED_THRESHOLDS = (0.80, 0.60)  # the provider's defaults (selfconsistency_high/medium_threshold)


def analyze(
    results: list[dict], exclude: dict[str, str] | None = None, thresholds: tuple[float, float] = CONFIGURED_THRESHOLDS
) -> dict:
    """Metrics on the seeded split. Items in `exclude` are dropped from both halves after the split,
    so a with/without comparison differs only by those items, not by a reshuffle. Levels use the
    configured thresholds; the thresholds tuned on half A are reported but never applied."""
    from app.evaluation import calibration_metrics, fit_isotonic, risk_coverage

    exclude = exclude or {}
    half_a, half_b, excluded = split_eligible(results)
    dropped = sum(row["id"] in exclude for row in half_a + half_b)
    if dropped:
        excluded["label needs human review"] = dropped
        half_a = [row for row in half_a if row["id"] not in exclude]
        half_b = [row for row in half_b if row["id"] not in exclude]
    kept = [row for row in results if row["id"] not in exclude]
    high, medium = thresholds
    tuned_high, tuned_medium, tuning_note = tune_thresholds(half_a)
    analysis: dict[str, Any] = {
        "n_results": len(results), "n_eligible": len(half_a) + len(half_b), "excluded": excluded,
        "n_review_excluded": len(results) - len(kept),
        "half_a": len(half_a), "half_b": len(half_b), "thresholds": (high, medium),
        "tuned_thresholds": (tuned_high, tuned_medium), "tuning_note": tuning_note,
        "labels": Counter(row["label"] for row in results),
        "label_sources": Counter(row["label_source"] for row in results),
        "by_source": Counter((row["source"], row["label"]) for row in results),
        "production_table": level_table(kept, [row["level"] for row in kept]),
        "abstained_labels": Counter(row["label"] for row in kept if row["level"] == "abstained"),
        "unattempted_but_scored": sorted(
            row["id"] for row in kept if row["label"] == "not_attempted" and row["score"] is not None
        ),
        "latency_p50": percentile([row["latency_ms"] for row in results], 0.5),
        "latency_p95": percentile([row["latency_ms"] for row in results], 0.95),
        "signal_cost_mean": _mean([row["cost_usd"]["signal"] for row in results]),
        "total_cost": sum(row["cost_usd"]["total"] or 0 for row in results),
        "models": Counter(row["model_version"] for row in results),
    }
    if not half_b:
        return analysis
    labels_b = [int(row["label"] == "correct") for row in half_b]
    scores_b = [row["score"] for row in half_b]
    analysis["auroc"] = auroc_with_ci(labels_b, scores_b)
    calibration = calibration_metrics(labels_b, scores_b, bins=10)
    analysis["ece"], analysis["brier"], analysis["bin_counts"] = calibration.ece, calibration.brier, calibration.bin_counts
    analysis["bins"] = _bins(labels_b, scores_b)
    if half_a:
        isotonic = fit_isotonic([int(row["label"] == "correct") for row in half_a], [row["score"] for row in half_a])
        calibrated = calibration_metrics(labels_b, isotonic.predict(scores_b), bins=10)
        analysis["isotonic_ece"], analysis["isotonic_brier"] = calibrated.ece, calibrated.brier
    points = risk_coverage([bool(label) for label in labels_b], scores_b)
    analysis["risk_coverage"] = _risk_coverage_summary(points)
    analysis["aurc"] = sum(point.risk for point in points) / len(points)
    analysis["half_b_table"] = level_table(half_b, [level_for(s, high, medium) for s in scores_b])
    analysis["accuracy_b"] = sum(labels_b) / len(labels_b)
    top = [label for label, score in zip(labels_b, scores_b) if score >= 1.0]
    analysis["top_score"] = {"n": len(top), "correct": sum(top)}
    return analysis


def _mean(values: list[float | None]) -> float | None:
    known = [value for value in values if value is not None]
    return sum(known) / len(known) if known else None


def _bins(labels: list[int], scores: list[float], bins: int = 10) -> list[dict]:
    grouped: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for label, score in zip(labels, scores):
        grouped[min(bins - 1, int(score * bins))].append((label, score))
    return [
        {"low": index / bins, "high": (index + 1) / bins, "n": len(items),
         "mean_score": sum(s for _, s in items) / len(items), "accuracy": sum(l for l, _ in items) / len(items)}
        for index, items in sorted(grouped.items())
    ]


def _risk_coverage_summary(points) -> list[dict]:
    """The operating points at each distinct confidence threshold (last point per threshold)."""
    by_threshold: dict[float, Any] = {}
    for point in points:
        by_threshold[point.threshold] = point
    return [{"threshold": p.threshold, "coverage": p.coverage, "risk": p.risk}
            for p in sorted(by_threshold.values(), key=lambda p: -p.threshold)]


def reliability_diagram(analysis: dict, path: Path) -> bool:
    if not analysis.get("bins"):
        return False
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    surface, ink, ink_secondary, grid, series = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df", "#2a78d6"
    bins = analysis["bins"]
    fig, (top, bottom) = plt.subplots(
        2, 1, figsize=(6.4, 6.0), dpi=150, sharex=True, gridspec_kw={"height_ratios": [3, 1], "hspace": 0.08}
    )
    fig.patch.set_facecolor(surface)
    for ax in (top, bottom):
        ax.set_facecolor(surface)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(grid)
        ax.tick_params(colors=ink_secondary, labelsize=8, length=0)
        ax.grid(axis="y", color=grid, linewidth=0.8)
        ax.set_axisbelow(True)

    top.plot([0, 1], [0, 1], linestyle=(0, (4, 3)), color=ink_secondary, linewidth=1.2)
    # Above the plot area, so no data point can collide with it.
    top.text(0, 1.015, "Each point is one score bin; dashed line = perfect calibration", transform=top.transAxes,
             color=ink_secondary, fontsize=8, ha="left", va="bottom")
    xs, ys = [b["mean_score"] for b in bins], [b["accuracy"] for b in bins]
    top.plot(xs, ys, color=series, linewidth=2, solid_capstyle="round", zorder=3)
    top.scatter(xs, ys, s=64, color=series, edgecolors=surface, linewidths=2, zorder=4)
    top.set_ylim(-0.02, 1.05)
    top.set_ylabel("Observed accuracy", color=ink_secondary, fontsize=9)
    top.set_title(
        f"Reliability of the self-consistency score (half B, n={analysis['half_b']})",
        color=ink, fontsize=11, loc="left", pad=22,
    )

    width = 0.1 * 0.6
    bottom.bar([(b["low"] + b["high"]) / 2 for b in bins], [b["n"] for b in bins], width=width, color=series,
               edgecolor=surface, linewidth=2)
    bottom.set_ylabel("Answers", color=ink_secondary, fontsize=9)
    bottom.set_xlabel("Score (support of the weakest checked claim)", color=ink_secondary, fontsize=9)
    bottom.set_xlim(0, 1)
    bottom.yaxis.get_major_locator().set_params(integer=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=surface, bbox_inches="tight")
    plt.close(fig)
    return True


# --- 5. study items -------------------------------------------------------------------------------


def _largest_remainder(total: int, weights: dict[str, int]) -> dict[str, int]:
    weight_sum = sum(weights.values())
    raw = {key: total * value / weight_sum for key, value in weights.items()}
    counts = {key: math.floor(value) for key, value in raw.items()}
    for key in sorted(raw, key=lambda k: raw[k] - counts[k], reverse=True)[: total - sum(counts.values())]:
        counts[key] += 1
    return counts


def trust(row: dict) -> bool:
    return row["level"] == "high"


def hit_rate(rows: list[dict]) -> float | None:
    if not rows:
        return None
    return sum(trust(row) == (row["label"] == "correct") for row in rows) / len(rows)


def select_study_items(
    results: list[dict], seed: int = SEED, exclude: dict[str, str] | None = None
) -> tuple[list[dict] | None, dict]:
    """21 correct + 9 incorrect real items whose (level | correctness) mix mirrors the measured one.

    Items in `exclude` (labels needing human review) are never chosen.
    """
    exclude = exclude or {}
    pool = [
        row for row in results
        if row["label"] in ("correct", "incorrect") and row["level"] in STUDY_LEVELS and row["id"] not in exclude
    ]
    by_label = {label: [row for row in pool if row["label"] == label] for label in ("correct", "incorrect")}
    needed = {"correct": STUDY_CORRECT, "incorrect": STUDY_INCORRECT}
    info: dict[str, Any] = {"available": {label: len(rows) for label, rows in by_label.items()}, "needed": needed,
                            "excluded_for_review": sorted(i for i in exclude if any(r["id"] == i for r in results))}
    positives, negatives = by_label["correct"], by_label["incorrect"]
    if positives and negatives:
        tpr = sum(trust(row) for row in positives) / len(positives)
        tnr = sum(not trust(row) for row in negatives) / len(negatives)
        info["measured_hit_rate"] = hit_rate(pool)
        info["expected_hit_rate_at_21_9"] = (STUDY_CORRECT * tpr + STUDY_INCORRECT * tnr) / (STUDY_CORRECT + STUDY_INCORRECT)
    if any(len(by_label[label]) < needed[label] for label in needed):
        return None, info

    rng = random.Random(seed)
    chosen = []
    for label, count in needed.items():
        rows = sorted(by_label[label], key=lambda row: row["id"])
        cells = defaultdict(list)
        for row in rows:
            cells[row["level"]].append(row)
        targets = _largest_remainder(count, {level: len(items) for level, items in cells.items()})
        picked = []
        for level, target in targets.items():
            picked.extend(rng.sample(cells[level], target))
        chosen.extend(picked)
    rng.shuffle(chosen)
    info["study_hit_rate"] = hit_rate(chosen)
    items = [
        {
            "id": row["id"],
            "domain": row.get("domain") or "unknown",
            "prompt": row["question"],
            "ai_answer": row["answer"],
            "ground_truth": row["gold_answers"][0],
            "ai_is_correct": row["label"] == "correct",
            "signal": {
                "level": row["level"],
                "score": row["score"],
                "flagged_sentence_indices": sorted({flag["sentenceIndex"] for flag in row["sentenceFlags"]}),
                "reason": row["explanation"],
                # The real per-claim results and sentence flags, so the study harness can show the
                # same overlay (pill counts, claim list, flag reasons) the extension would.
                "sentence_flags": row["sentenceFlags"],
                "claim_assessments": row["claimAssessments"],
                "model_version": row["model_version"],
            },
            "difficulty": "hard" if row["source"] == "simpleqa" else "standard",
        }
        for row in chosen
    ]
    return items, info


# --- report -------------------------------------------------------------------------------------


def _fmt(value, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float) and math.isnan(value):
        return "n/a"
    return f"{value:.{digits}f}"


def _review_section(label_review: dict[str, str], results: list[dict]) -> list[str]:
    rows = {row["id"]: row for row in results}
    present = [item for item in label_review if item in rows]
    if not present:
        return []
    lines = [
        "## Labels needing human review",
        "",
        "Their automatic labels are kept (not relabelled). They are kept out of the study set, and the "
        "metrics below are shown both with them and without them.",
        "",
        "| Item | Auto label | Signal | Note |",
        "|---|---|---|---|",
    ]
    for item in present:
        row = rows[item]
        score = "n/a" if row["score"] is None else f"{row['score']:.2f}"
        lines.append(f"| `{item}` | {row['label']} ({row['label_source']}) | {row['level']}, {score} | {label_review[item]} |")
    return lines + [""]


def _auroc_text(analysis: dict) -> str:
    auroc = analysis.get("auroc")
    return "n/a" if auroc is None else f"{_fmt(auroc[0], 2)} (95% CI {_fmt(auroc[1], 2)}-{_fmt(auroc[2], 2)})"


def _level_accuracy(analysis: dict, level: str) -> str:
    row = next((r for r in analysis["production_table"] if r["level"] == level), None)
    return "n/a" if row is None or row["accuracy"] is None else f"{row['accuracy']:.2f} ({row['correct']}/{row['correct'] + row['incorrect']})"


def _key_findings(analysis: dict, reviewed: dict | None) -> list[str]:
    if not analysis.get("half_b") or analysis.get("auroc") is None:
        return []
    review_note = ""
    if reviewed and reviewed.get("auroc") is not None:
        review_note = (f" Without the {reviewed['n_review_excluded']} review items: AUROC {_auroc_text(reviewed)}, "
                       f"ECE {_fmt(reviewed['ece'], 2)}.")
    top = analysis["top_score"]
    top_note = (f" {top['n']} of {analysis['half_b']} held-out answers scored 1.00, but only {top['correct']} of "
                f"them ({top['correct'] / top['n']:.0%}) were correct." if top["n"] else "")
    lines = [
        "## Key findings",
        "",
        f"1. **The score ranks answers well but is poorly calibrated.** On half B, AUROC is {_auroc_text(analysis)}, "
        f"but ECE is {_fmt(analysis['ece'], 2)}. The score is overconfident:{top_note} An answer the model gives "
        "the same way every time looks consistent even when it is wrong; this is a known limitation of "
        f"self-consistency.{review_note}",
    ]
    iso_ece, iso_brier = analysis.get("isotonic_ece"), analysis.get("isotonic_brier")
    if iso_ece is not None:
        brier_change = ("does not improve Brier" if iso_brier >= analysis["brier"] else "also lowers Brier")
        lines.append(
            f"2. **Isotonic calibration lowers ECE ({_fmt(analysis['ece'], 2)} to {_fmt(iso_ece, 2)}) but "
            f"{brier_change} ({_fmt(analysis['brier'], 2)} to {_fmt(iso_brier, 2)}), so it is not applied.** "
            f"The fit uses only {analysis['half_a']} answers from half A."
        )
    abstained = analysis["abstained_labels"]
    committed = abstained.get("correct", 0) + abstained.get("incorrect", 0)
    missed = analysis["unattempted_but_scored"]
    lines.append(
        f"3. **Refusals are abstained, not scored.** {sum(abstained.values())} answers abstained with no score; "
        f"{committed} of them were committed answers that should have been scored."
        + (f" {len(missed)} declined answer(s) still got a score: {', '.join(f'`{i}`' for i in missed)}." if missed else "")
    )
    tuned_high, tuned_medium = analysis["tuned_thresholds"]
    high, medium = analysis["thresholds"]
    collapsed = " The tuned high and medium thresholds are equal, so tuning leaves no medium band." if tuned_high == tuned_medium else ""
    lines += [
        f"4. **Threshold tuning on half A is reported but not applied.** It gives high >= {tuned_high:.2f}, "
        f"medium >= {tuned_medium:.2f} ({analysis['tuning_note']}).{collapsed} Every level in this report uses "
        f"the configured thresholds, high >= {high:.2f} and medium >= {medium:.2f}.",
        "",
    ]
    return lines


def _comparison_section(analysis: dict, reviewed: dict | None) -> list[str]:
    if not reviewed:
        return []
    rows = [
        ("Usable answers (half A / half B)", lambda a: f"{a['n_eligible']} ({a['half_a']} / {a['half_b']})"),
        ("AUROC, 95% bootstrap CI (half B)", _auroc_text),
        ("ECE, 10 bins (half B)", lambda a: _fmt(a.get("ece"))),
        ("Brier (half B)", lambda a: _fmt(a.get("brier"))),
        ("ECE / Brier after isotonic fit", lambda a: f"{_fmt(a.get('isotonic_ece'))} / {_fmt(a.get('isotonic_brier'))}"),
        ("Area under risk-coverage curve", lambda a: _fmt(a.get("aurc"))),
        ("Tuned thresholds (not applied)", lambda a: f"{a['tuned_thresholds'][0]:.2f} / {a['tuned_thresholds'][1]:.2f}"),
        ("High accuracy, all evaluated answers", lambda a: _level_accuracy(a, "high")),
        ("Low accuracy, all evaluated answers", lambda a: _level_accuracy(a, "low")),
    ]
    return [
        "## All items vs. review items excluded",
        "",
        f"Same seeded split; the right column drops the {reviewed['n_review_excluded']} items listed above from both "
        "halves. The other sections use all items.",
        "",
        "| Metric | All items | Review items excluded |",
        "|---|---|---|",
        *[f"| {name} | {value(analysis)} | {value(reviewed)} |" for name, value in rows],
        "",
    ]


def _table_md(table: list[dict]) -> list[str]:
    lines = ["| Level | n | Correct | Incorrect | Not graded | Accuracy | 95% CI (Wilson) |", "|---|---|---|---|---|---|---|"]
    for row in table:
        ci = "n/a" if row["ci"] is None else f"{row['ci'][0]:.2f}-{row['ci'][1]:.2f}"
        lines.append(f"| {row['level']} | {row['n']} | {row['correct']} | {row['incorrect']} | {row['other']} | "
                     f"{_fmt(row['accuracy'], 2)} | {ci} |")
    return lines


def write_report(
    analysis: dict,
    study_info: dict,
    study_written: bool,
    total_questions: int,
    diagram: bool,
    label_review: dict[str, str] | None = None,
    results: list[dict] | None = None,
    reviewed: dict | None = None,
) -> str:
    """`reviewed` is the analysis with the label-review items excluded, shown next to `analysis`."""
    high, medium = analysis["thresholds"]
    small = analysis["n_eligible"] < 60
    lines = [
        "# Self-consistency signal: validation report",
        "",
        f"Generated {datetime.now(timezone.utc).isoformat(timespec='minutes')} by `apps/api/scripts/validate.py`.",
        "",
        *_key_findings(analysis, reviewed),
        "## Run",
        "",
        f"- Questions evaluated: **{analysis['n_results']} of {total_questions}**"
        + (" (partial run)" if analysis["n_results"] < total_questions else ""),
        f"- Signal versions: {', '.join(f'`{k}` ({v})' for k, v in analysis['models'].items())}",
        f"- Labels: {dict(analysis['labels'])}; label source: {dict(analysis['label_sources'])}",
        f"- By source: {', '.join(f'{s}/{l}: {n}' for (s, l), n in sorted(analysis['by_source'].items()))}",
        "",
    ]
    if small:
        lines += [f"> **Too few answers for reliable estimates** ({analysis['n_eligible']} usable). Treat every "
                  "number below as a smoke test of the pipeline, not as a measurement.", ""]
    lines += [
        *_review_section(label_review or {}, results or []),
        *_comparison_section(analysis, reviewed),
        "## Exclusions from score-based metrics",
        "",
        f"{sum(analysis['excluded'].values())} of {analysis['n_results']} excluded:",
        "",
        *([f"- {reason}: {count}" for reason, count in analysis["excluded"].most_common()] or ["- none"]),
        "",
        "## Held-out metrics (half B)",
        "",
        f"Seeded 50/50 split (seed {SEED}) of the {analysis['n_eligible']} usable answers: "
        f"half A = {analysis['half_a']} (threshold tuning, isotonic fit), half B = {analysis['half_b']} (reported).",
        "",
    ]
    if analysis.get("half_b"):
        auroc = analysis.get("auroc")
        lines += [
            "| Metric | Value |",
            "|---|---|",
            f"| Accuracy of the answers (half B) | {_fmt(analysis['accuracy_b'], 2)} |",
            "| AUROC (score vs. correct), 95% bootstrap CI | "
            + ("n/a (half B needs both correct and incorrect answers)" if auroc is None
               else f"{_fmt(auroc[0])} ({_fmt(auroc[1], 2)}-{_fmt(auroc[2], 2)})") + " |",
            f"| ECE, 10 bins (raw score) | {_fmt(analysis['ece'])} |",
            f"| Brier (raw score) | {_fmt(analysis['brier'])} |",
            f"| ECE / Brier after isotonic fit on half A | {_fmt(analysis.get('isotonic_ece'))} / {_fmt(analysis.get('isotonic_brier'))} |",
            f"| Area under risk-coverage curve (lower is better) | {_fmt(analysis['aurc'])} |",
            "",
            f"Levels use the configured thresholds, high >= {high:.2f} and medium >= {medium:.2f}. Tuning on half A "
            f"gives {analysis['tuned_thresholds'][0]:.2f} / {analysis['tuned_thresholds'][1]:.2f} "
            f"({analysis['tuning_note']}); that result is reported, not applied.",
            "",
            f"### Level x correctness, half B, configured thresholds ({high:.2f} / {medium:.2f})",
            "",
            *_table_md(analysis["half_b_table"]),
            "",
            "### Risk-coverage (half B)",
            "",
            "| Score threshold | Coverage | Risk (error rate among covered) |",
            "|---|---|---|",
            *[f"| >= {p['threshold']:.2f} | {p['coverage']:.2f} | {p['risk']:.2f} |" for p in analysis["risk_coverage"]],
            "",
            "### Reliability diagram (half B)",
            "",
            "![Reliability diagram](reliability_diagram.png)" if diagram else "_Not drawn: no scored answers in half B._",
            "",
            "| Score bin | Answers | Mean score | Observed accuracy |",
            "|---|---|---|---|",
            *[f"| {b['low']:.1f}-{b['high']:.1f} | {b['n']} | {b['mean_score']:.2f} | {b['accuracy']:.2f} |"
              for b in analysis["bins"]],
            "",
        ]
    else:
        lines += ["_No scored answers in half B._", ""]
    lines += [
        "## Production levels (0.80 / 0.60), all evaluated answers",
        "",
        *_table_md(analysis["production_table"]),
        "",
        "## Latency and cost",
        "",
        f"- Signal latency: p50 {_fmt((analysis['latency_p50'] or 0) / 1000, 1)} s, "
        f"p95 {_fmt((analysis['latency_p95'] or 0) / 1000, 1)} s (measured with {4} questions in flight).",
        f"- Signal cost per answer: ${_fmt(analysis['signal_cost_mean'], 4)} (mean; first-party API prices).",
        f"- Whole run including answer generation and labelling: ${analysis['total_cost']:.4f}.",
        "",
        "## Study set (`data/questions.json`)",
        "",
    ]
    available = study_info["available"]
    if study_info.get("excluded_for_review"):
        lines += [f"Kept out for human review: {', '.join(f'`{i}`' for i in study_info['excluded_for_review'])}.", ""]
    if study_written:
        lines += [
            f"Written: {STUDY_CORRECT} correct + {STUDY_INCORRECT} incorrect real answers with their real signals.",
            f"Signal hit rate (high = trust, otherwise check): study set {_fmt(study_info['study_hit_rate'], 2)}; "
            f"expected from the measured quality at a 21/9 mix {_fmt(study_info['expected_hit_rate_at_21_9'], 2)}; "
            f"measured on all {available['correct'] + available['incorrect']} candidates "
            f"{_fmt(study_info['measured_hit_rate'], 2)}.",
        ]
    else:
        lines += [
            f"**Not written.** It needs {STUDY_CORRECT} correct and {STUDY_INCORRECT} genuinely incorrect answers with "
            f"a signal; this run has {available['correct']} correct and {available['incorrect']} incorrect."
            + (" Fewer than 9 genuinely wrong answers exist, so the set cannot be built without fabricating items."
               if available["incorrect"] < STUDY_INCORRECT and analysis["n_results"] >= total_questions else ""),
        ]
    lines += [
        "",
        "## Limitations",
        "",
        "- **Labels are automatic.** Correctness comes from normalized string matching against the gold answers, "
        "with an LLM judge for the rest; neither was checked by a person. A string match can also accept an "
        "answer that mentions the gold answer while committing to something else.",
        "- **The same model family answers and checks.** The answers, the five samples, the claim extraction, "
        "the consistency judge and the label judge all come from Claude models, so shared blind spots inflate "
        "agreement: a confidently wrong fact the model always repeats looks consistent.",
        "- **Unaddressed side claims are not checked.** Claims that fewer than 2 samples mention are excluded from "
        "the score, so an answer can be scored on its main claim while its side details go unverified.",
        "- **Gold answers can be stale or incomplete** (NQ-open has known answer gaps); SimpleQA was built to be "
        "hard for frontier models, so it supplies most of the incorrect answers.",
        "- **Small sample.** With about 100 questions, every interval above is wide; the thresholds are tuned on "
        "about 50 answers.",
        "- **Source approval is pending.** See `SOURCE.md`; these questions may not enter the study or the "
        "annotation dataset until an authorized owner approves them.",
        "",
    ]
    text = "\n".join(lines)
    REPORT.write_text(text, encoding="utf-8")
    return text


# --- entry point ----------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--build-questions", action="store_true", help="download the sources and rebuild questions.jsonl")
    parser.add_argument("--limit", type=int, help="only use the first N questions")
    parser.add_argument("--resume", action="store_true", help="continue an existing results.jsonl (skip finished ids)")
    parser.add_argument("--fresh", action="store_true", help="delete results.jsonl and start over")
    parser.add_argument("--report-only", action="store_true", help="analyse existing results without calling the LLM")
    parser.add_argument("--concurrency", type=int, default=4)
    args = parser.parse_args()
    os.chdir(API_DIR)  # Settings reads apps/api/.env relative to the working directory

    if args.build_questions:
        build_questions()
        if not (args.limit or args.resume or args.fresh):
            return 0
    questions = load_jsonl(QUESTIONS)
    if not questions:
        print("No questions; run with --build-questions first.", file=sys.stderr)
        return 2
    selected = questions[: args.limit] if args.limit else questions

    if not args.report_only:
        if args.fresh and RESULTS.exists():
            RESULTS.unlink()
        if RESULTS.exists() and load_jsonl(RESULTS) and not args.resume:
            print(f"{RESULTS.relative_to(REPO)} already has results; pass --resume to continue or --fresh to restart.",
                  file=sys.stderr)
            return 2
        from app.config import get_settings
        from app.services.llm_client import AnthropicLLMClient

        settings = get_settings()
        if settings.llm_api_key is None or not settings.llm_api_key.get_secret_value():
            print("LLM_API_KEY is not set (apps/api/.env).", file=sys.stderr)
            return 2
        inner = AnthropicLLMClient(
            api_key=settings.llm_api_key.get_secret_value(), model=settings.llm_model,
            timeout_seconds=settings.selfconsistency_timeout_seconds, effort=settings.llm_effort, max_retries=3,
        )

        from app.services.selfconsistency_service import SelfConsistencyProvider

        engine_version = SelfConsistencyProvider(settings=settings)._version(settings.llm_model)

        async def go() -> int:
            try:
                return await run_questions(selected, RESULTS, inner, settings, args.concurrency, engine_version)
            finally:
                await inner.aclose()

        failures = asyncio.run(go())
        if failures:
            print(f"{failures} question(s) failed and were not recorded; rerun with --resume to retry them.")

    selected_ids = {q["id"] for q in selected}
    results = [row for row in load_jsonl(RESULTS) if row["id"] in selected_ids]
    if not results:
        print("No results to analyse.", file=sys.stderr)
        return 1
    label_review = load_label_review()
    analysis = analyze(results)
    reviewed = analyze(results, exclude=label_review) if any(row["id"] in label_review for row in results) else None
    diagram = reliability_diagram(analysis, DIAGRAM)
    items, study_info = select_study_items(results, exclude=label_review)
    if items is not None:
        STUDY.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\n" + write_report(analysis, study_info, items is not None, len(questions), diagram, label_review, results,
                              reviewed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
