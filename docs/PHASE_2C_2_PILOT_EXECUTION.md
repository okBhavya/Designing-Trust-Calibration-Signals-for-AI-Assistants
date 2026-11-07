# CalibrAI Phase 2C.2 Pilot Execution

## Current status: blocked

The repository does not contain approved real examples, approved evidence
bundles, source-ownership records, or reviewer assignments. No pilot packets
were created, no source was marked approved, and no human annotation was
collected. Synthetic unit-test fixtures are not pilot data.

The execution plan below is ready to run after source approval. It must not be
used to manufacture substitute examples.

## Target batch

Prepare approximately 30 real examples in the development partition only.
Exclude their item IDs, prompt/answer hashes, source passages, and
near-duplicate fingerprints from calibration and held-out partitions. The
pilot must not be used for final calibration or held-out scientific estimates.

Before packet creation, complete
[the source approval checklist](./PHASE_2C_2_SOURCE_APPROVAL.md) for every
source and freeze the evidence bundle with a content digest.

## Packet requirements

Every packet must contain:

- frozen prompt and AI answer;
- answer timestamp with timezone;
- sentence indices and exact claim spans;
- claim type, materiality, and time-sensitivity fields;
- frozen evidence passages and URLs;
- publisher, independence group, publication timestamp, and retrieval
  timestamp;
- dataset version, development partition, item ID, and provenance.

Packets must not contain CalibrAI confidence, score, model version, predicted
assessment, generated explanation, or any other engine output.

## Independent review sequence

1. Assign two trained reviewers using pseudonymous `reviewer-...` IDs.
2. Deliver byte-identical frozen packets to both reviewers.
3. Keep reviewer submissions isolated until both are complete.
4. Validate and save each original annotation as a separate immutable record.
5. Preserve disagreements; do not calculate agreement before both submissions
   are complete.
6. Request adjudication only after independent submission.
7. Store adjudication in a separate history record with a decision and reason.
8. Export the validated development bundle and manifest.

An answer with zero externally verifiable claims is `indeterminate`, has no
materiality denominator, and is excluded from binary threshold fitting. A
technical evidence outage must be recorded as unavailable in the workflow and
must not be converted into Low reliability.

## Completion record

When the blocker is resolved, record:

- approved source IDs and approval decisions;
- packet count and item IDs;
- reviewer pseudonyms and assignment isolation;
- annotation submission timestamps and versions;
- adjudication count and unresolved count;
- validation errors and exclusions with reasons;
- exported bundle and manifest content digest.

Do not report inter-annotator agreement until both reviewers have independently
completed the relevant examples. Do not report accuracy, calibration, ECE,
Brier, or risk-coverage results from this pilot.
