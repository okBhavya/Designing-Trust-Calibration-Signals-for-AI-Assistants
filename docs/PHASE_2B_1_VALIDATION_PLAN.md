# CalibrAI Phase 2B.1: Validation and Scientific Evaluation Plan

## Goal

Evaluate the engine as separate measurable components. Do not use model
self-consistency, agreement between AI models, or a fluent explanation as proof
of factual correctness.

## Dataset design

Create a manually verified factual QA dataset representative of supported
platform answers:

- prompts spanning stable facts, current facts, quantitative claims, causal
  claims, attributions, definitions, recommendations, and ambiguous wording;
- answers containing markdown, lists, code, quotations, multi-claim sentences,
  unsupported claims, and deliberately conflicting claims;
- claim-level labels for span, sentence index, type, materiality,
  time-sensitivity, and whether external evidence is required;
- adjudicated evidence with URL, publisher, dates, relevant passage, and
  independent-source grouping;
- claim outcomes: supported, contradicted, or insufficient_evidence;
- answer-level reliability label derived from a published adjudication rule,
  not from the engine's output.

For the initial study, an answer is `reliable` only when every
high-materiality claim is `supported`, no high-materiality claim is
`contradicted`, and at least 80% of total materiality weight is supported. An
answer is `unreliable` when any high-materiality claim is contradicted or less
than 60% of materiality weight is supported. Cases between those rules,
including unresolved high-materiality conflicts, are `indeterminate` and are
excluded from binary threshold fitting but retained for three-class analysis.
Freeze and version this rule before annotation.

Use participant or source separation to prevent leakage. Partition before
development:

| Partition | Purpose |
|---|---|
| Training/development | Prompt and parser development; no threshold fitting |
| Calibration | Choose score-to-label thresholds and assess calibration |
| Held-out test | One-time final report after all design choices are locked |

Do not let the same prompt template, answer, source passage, or near-duplicate
appear across partitions. Keep a versioned manifest and record exclusion
reasons.

The initial target is at least 600 answers: 360 development, 120 calibration,
and 120 held-out test. Each partition should contain at least 30 answers for
each planned answer-level class where feasible, with coverage of platform,
claim type, materiality, time-sensitivity, and source availability. Confirm
the final sample size with a power and confidence-interval analysis before
collection.

For time-sensitive claims, record the answer timestamp and define an evidence
cutoff. Evidence published after the answer timestamp is excluded from
real-time correctness evaluation unless the task explicitly asks for a later
update. Store retrieval timestamp, publication timestamp, and evaluation
cutoff independently.

Adjudicate independent-source groups using publisher ownership, authorship,
cited origin, and text-similarity rules. Syndicated or copied content shares
one independence group even when hosted at multiple URLs.

Each annotation record should contain, at minimum:

```text
datasetVersion, itemId, partition, promptHash, answerHash,
answerTimestamp, sentenceIndex, claimSpan, normalizedClaim,
claimType, materiality, timeSensitive, requiresExternalEvidence,
sourceId, sourceUrl, publisher, independenceGroup, publishedAt,
retrievedAt, evidencePassage, claimOutcome, adjudicationStatus,
annotationId, reviewerId, annotationVersion, reviewedAt,
adjudicationDecision, adjudicationReason, supersedesAnnotationId,
exclusionReason
```

Keep hashes and research identifiers separate from the protected source text.
Use stable item IDs in metrics and reports, and retain an audit trail whenever
an annotation, source, partition, or exclusion decision changes.
Store each reviewer's original annotation as an immutable record. Adjudication
creates a separate final-label record containing `adjudicationDecision` and
`adjudicationReason`; it must never overwrite an original reviewer annotation.
`supersedesAnnotationId` links a correction or adjudication record to the
record it replaces, and `exclusionReason` is required whenever an item or
annotation is excluded from a metric or partition.

## Component metrics

### Claim extraction

Compare extracted spans and sentence mappings with adjudicated annotations:

- precision, recall, and F1 for claim span detection;
- precision, recall, and F1 for claim type;
- exact and tolerance-based sentence-index mapping accuracy;
- materiality and time-sensitivity macro-F1;
- truncation rate and claims-per-answer distribution;
- false-positive rate for opinions, hypotheticals, quoted text, headings, and
  code blocks.

Report micro and macro averages because answers vary in claim count.

### Evidence retrieval

At claim level, measure:

- recall@k for at least one adjudicated supporting or contradicting source;
- precision@k for relevant sources;
- source authority and independence classification accuracy;
- publication/retrieval timestamp completeness;
- freshness pass rate for time-sensitive claims;
- fetch success, blocked-source, empty-content, and timeout rates;
- citation entailment: whether the retrieved passage actually bears on the
  claim, not merely shares keywords.

Search snippets count as discovery results, not conclusive evidence.
Evaluate source independence separately from relevance: duplicate reporting
must not increase the independent-source count.

### Claim verification

For the three outcomes (`supported`, `contradicted`,
`insufficient_evidence`), report per-class precision, recall, and F1,
macro-F1, confusion matrix, and abstention/insufficient rate. Separately
report conflict detection precision and recall and the rate of irrelevant
evidence being accepted.

Treat `insufficient_evidence` as a first-class outcome, not as an error or as
negative evidence. Report both the unconditional three-class metrics and
selective metrics conditioned on non-abstention, including coverage and risk
at each abstention threshold.

Use AUROC only for a defined binary question, such as detecting
`contradicted` versus not contradicted. For three-class outcomes, use
one-vs-rest AUROC with explicit class definitions and also report
precision-recall curves where prevalence is low.

### Overall reliability and calibration

Define the answer-level label from the adjudication protocol before evaluating
the engine. Report:

- answer-level precision, recall, and F1 for a reliability decision;
- AUROC for a pre-declared binary reliable/unreliable task;
- Expected Calibration Error with fixed, documented bins;
- Brier score for any output interpreted as a probability;
- reliability diagrams with sample counts per bin;
- high-materiality contradiction miss rate;
- false High rate and false Low rate;
- performance by platform, claim type, materiality, time-sensitivity, and
  source availability.
- explanation faithfulness: whether each cited source and rationale actually
  entails the explanation's stated support, contradiction, or uncertainty.

If a probability-like output is needed, fit one calibration mapping (initially
isotonic regression; Platt scaling is a fallback for small calibration sets)
using only the calibration partition. Do not fit thresholds or calibration
parameters on the held-out test partition. The provisional score is not a
probability until this mapping and held-out evaluation support that
interpretation.

Use fixed, pre-registered ECE bins and also report adaptive-bin ECE with
per-bin counts. Identify bins with very small samples rather than silently
merging them. Report bootstrap confidence intervals for ECE, Brier score, F1,
and AUROC where sample size permits. Pre-register binary AUROC tasks and
positive classes, including `unreliable` versus `reliable` after excluding
`indeterminate`, and high-materiality contradiction versus all other claim
outcomes.

### Operational metrics

Measure p50, p95, and timeout rate for normalization, extraction, retrieval,
verification, aggregation, and end-to-end response. Record cost per answer and
cost per claim using provider billing data or an explicitly documented
estimate. Normalize reported cost to USD and record provider, model/version,
region, token counts, request counts, cache state, and retry counts. Include
cache hit rate, duplicate coalescing, rate-limit failures, and asynchronous
completion rate.

Report paired comparisons when changing a provider, prompt, threshold, or
aggregation policy. Use the same frozen inputs and evidence bundles for both
systems. Do not compare results from different retrieval dates without
labeling the comparison as time-confounded.

## Human adjudication protocol

At least two independent reviewers should label claims and source entailment.
Resolve disagreements through a third reviewer or a documented adjudication
meeting. Reviewers must see the claim and candidate evidence, not the engine's
confidence label first. Measure inter-rater agreement (for example Cohen's
kappa or Krippendorff's alpha as appropriate) and report unresolved cases as
insufficient evidence rather than forcing a binary truth label. Report the
agreement statistic with confidence intervals and use a pre-defined minimum
agreement target of 0.67 for proceeding without protocol revision. Values
below 0.67 require reviewer retraining, adjudication review, and a documented
decision about whether affected labels remain usable.

For current facts, freeze the retrieval date and define an acceptable
publication window. For contested facts, preserve both sides and label the
claim insufficient unless the protocol specifies a defensible authority rule.
Reviewers should independently assign source independence groups and
explanation-faithfulness labels on a sampled subset.

Before annotation begins, preregister:

- the answer-label rule and all materiality weights;
- partition assignment and duplicate/near-duplicate exclusion rules;
- evidence cutoff and freshness policy;
- provider/model versions and prompt templates;
- score calibration method and threshold-selection objective;
- primary metrics, subgroup metrics, confidence-interval method, and stopping
  rule;
- treatment of missing, blocked, conflicting, and abstained cases.

Any post-registration change must be recorded with its rationale and applied
to the held-out test only after the change is frozen and the test evaluation
is restarted or explicitly marked exploratory.

## Test levels

1. Unit tests for normalization, markdown boundaries, sentence indices,
   eight-claim cap, hashing, source deduplication, freshness, and aggregation.
2. Contract tests for every provider port using deterministic fixtures for
   success, timeout, empty, malformed, conflicting, and unavailable results.
3. Property tests asserting no unsupported evidence can yield `supported` and
   no retrieval failure can yield High.
4. Replay tests over frozen evidence bundles so provider changes can be
   compared without live web drift.
5. Integration tests for authentication, consent, participant isolation,
   deletion, duplicate prevention, redacted logging, and response compatibility.
6. Load tests for the eight-second budget and bounded concurrency.
7. Held-out scientific evaluation with the partitioning rules above.

For missing-data tests, distinguish a provider failure from a genuine
`insufficient_evidence` result. In both cases the system must not emit a
high-confidence positive result, but reports should preserve the cause. For
selective systems, report risk-coverage curves and the fraction of answers
that complete within the eight-second budget.

## Privacy and leakage controls

Keep raw answers, prompts, and fetched bodies out of ordinary logs. Store
dataset content in access-controlled research storage, with participant
identifiers separated from evaluation identifiers. Redact or hash answer
identifiers in operational telemetry. Delete participant-linked derived data
through the same deletion workflow as live signals. Never use test answers or
retrieved passages in prompts, caches, or training data for another partition
without recording the transformation and exclusion decision.

The current API's `LiveSignal` table stores raw prompt and answer fields; a
real-engine study must explicitly choose and implement a retention policy
before collecting evaluation traffic.

## Reporting and release gates

Every evaluation report must include dataset version, partition manifest,
provider/model versions, retrieval policy, threshold version, missing-data
handling, confidence intervals where feasible, and all excluded cases.
It must also include class counts, subgroup denominators, abstention coverage,
confidence-interval methodology, annotation agreement, and whether each
analysis was preregistered or exploratory.

Do not release the real provider for participant-facing claims until:

- schema and consent migration tests pass;
- no high-confidence result is possible after retrieval/verification failure;
- held-out test results and calibration diagnostics are reviewed;
- latency and cost remain within the approved study budget;
- deletion and participant-isolation tests cover derived evidence metadata;
- limitations explicitly state that evidence coverage is not universal.

## Immediate Phase 2B.2 experiments

1. Annotate a small development set and measure extractor errors, especially
   quoted text and multi-claim sentences.
2. Build frozen evidence bundles for supported, contradicted, conflicting, and
   unavailable cases.
3. Implement the aggregation policy against those bundles and test the
   high-materiality contradiction cap.
4. Pilot candidate retrieval/source-fetch providers with provenance and
   timeout instrumentation.
5. Fit provisional thresholds only on calibration data and reserve the test
   partition.
6. Measure p95 latency and cost at one, four, and eight claims before choosing
   synchronous versus asynchronous delivery.
