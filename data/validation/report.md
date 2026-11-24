# Self-consistency signal: validation report

Generated 2026-11-24T20:56+00:00 by `apps/api/scripts/validate.py`.

- Questions evaluated: **10 of 100** (partial run)
- Signal versions: `selfconsistency-v1:claude-haiku-5-5` (10)
- Labels: {'correct': 5, 'incorrect': 3, 'not_attempted': 2}; label source: {'exact': 2, 'judge': 8}
- By source: nq_open/correct: 5, nq_open/not_attempted: 1, simpleqa/incorrect: 3, simpleqa/not_attempted: 1

> **Too few answers for reliable estimates** (7 usable). Treat every number below as a smoke test of the pipeline, not as a measurement.

## Exclusions from score-based metrics

3 of 10 excluded:

- answer not_attempted (no committed answer to grade): 2
- no score: signal was insufficient_evidence: 1

## Held-out metrics (half B)

Seeded 50/50 split (seed 20261125) of the 7 usable answers: half A = 4 (threshold tuning, isotonic fit), half B = 3 (reported).

| Metric | Value |
|---|---|
| Accuracy of the answers (half B) | 0.67 |
| AUROC (score vs. correct), 95% bootstrap CI | 1.000 (1.00-1.00) |
| ECE, 10 bins (raw score) | 0.111 |
| Brier (raw score) | 0.037 |
| ECE / Brier after isotonic fit on half A | 0.000 / 0.000 |
| Area under risk-coverage curve (lower is better) | 0.111 |

Thresholds: high >= 1.00, medium >= 1.00 (tuned on half A (n=4)).

### Level x correctness, half B, tuned thresholds

| Level | n | Correct | Incorrect | Not graded | Accuracy | 95% CI (Wilson) |
|---|---|---|---|---|---|---|
| high | 2 | 2 | 0 | 0 | 1.00 | 0.34-1.00 |
| low | 1 | 0 | 1 | 0 | 0.00 | 0.00-0.79 |

### Risk-coverage (half B)

| Score threshold | Coverage | Risk (error rate among covered) |
|---|---|---|
| >= 1.00 | 0.67 | 0.00 |
| >= 0.33 | 1.00 | 0.33 |

### Reliability diagram (half B)

![Reliability diagram](reliability_diagram.png)

| Score bin | Answers | Mean score | Observed accuracy |
|---|---|---|---|
| 0.3-0.4 | 1 | 0.33 | 0.00 |
| 0.9-1.0 | 2 | 1.00 | 1.00 |

## Production levels (0.80 / 0.60), all evaluated answers

| Level | n | Correct | Incorrect | Not graded | Accuracy | 95% CI (Wilson) |
|---|---|---|---|---|---|---|
| high | 7 | 5 | 1 | 1 | 0.83 | 0.44-0.97 |
| low | 1 | 0 | 1 | 0 | 0.00 | 0.00-0.79 |
| insufficient_evidence | 2 | 0 | 1 | 1 | 0.00 | 0.00-0.79 |

## Latency and cost

- Signal latency: p50 4.9 s, p95 6.8 s (measured with 4 questions in flight).
- Signal cost per answer: $0.0015 (mean; first-party API prices).
- Whole run including answer generation and labelling: $0.0173.

## Study set (`data/questions.json`)

**Not written.** It needs 21 correct and 9 genuinely incorrect answers with a signal; this run has 5 correct and 3 incorrect.

## Limitations

- **Labels are automatic.** Correctness comes from normalized string matching against the gold answers, with an LLM judge for the rest; neither was checked by a person. A string match can also accept an answer that mentions the gold answer while committing to something else.
- **The same model family answers and checks.** The answers, the five samples, the claim extraction, the consistency judge and the label judge all come from Claude models, so shared blind spots inflate agreement: a confidently wrong fact the model always repeats looks consistent.
- **Unaddressed side claims are not checked.** Claims that fewer than 2 samples mention are excluded from the score, so an answer can be scored on its main claim while its side details go unverified.
- **Gold answers can be stale or incomplete** (NQ-open has known answer gaps); SimpleQA was built to be hard for frontier models, so it supplies most of the incorrect answers.
- **Small sample.** With about 100 questions, every interval above is wide; the thresholds are tuned on about 50 answers.
- **Source approval is pending.** See `SOURCE.md`; these questions may not enter the study or the annotation dataset until an authorized owner approves them.
