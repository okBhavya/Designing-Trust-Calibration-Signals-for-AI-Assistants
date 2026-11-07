# CalibrAI Phase 2 Reference

Date: 2026-11-07

This is the consolidated reference for Phase 2 engineering status, dataset
source decisions, annotation readiness, and unresolved research gates. It
replaces the superseded Phase 2C landscape, audit, comparison, and
implementation-report chain. The authoritative protocol and operational
documents remain separate and are linked below.

## Authoritative documents

- [Reliability architecture](./PHASE_2B_1_ARCHITECTURE.md)
- [Provider comparison](./PHASE_2B_1_PROVIDER_COMPARISON.md)h
- [Validation plan](./PHASE_2B_1_VALIDATION_PLAN.md)
- [Annotation handbook](./PHASE_2C_ANNOTATION_HANDBOOK.md)
- [Source approval checklist](./PHASE_2C_2_SOURCE_APPROVAL.md)
- [Pilot execution protocol](./PHASE_2C_2_PILOT_EXECUTION.md)
- [Phase 2 implementation report](./PHASE_2_MASTER_IMPLEMENTATION_REPORT.md)

The validation plan controls answer labels, materiality weights, partitions,
metrics, temporal cutoffs, and adjudication. This reference does not change
those rules.

## Current implementation status

Implemented and tested:

- Consent-aware authenticated FastAPI signal flow.
- Participant isolation, duplicate prevention, revocation, and deletion.
- Mock provider as the default and deterministic fixture provider behind
  explicit configuration.
- Deterministic answer normalization, sentence mapping, claim extraction
  capped at eight claims, evidence fixture retrieval, verification, and
  weighted aggregation.
- Distinct `high`, `medium`, `low`, `insufficient_evidence`, `unavailable`,
  and `abstained` states.
- Raw conversation disabled by default, fail-closed participant/study
  safeguards, metadata privacy validation, and redacted persisted signal JSON.
- Versioned dataset records, immutable original annotations, separate
  adjudication history, evidence provenance validation, partition checks,
  duplicate detection, import/export, and manifest generation.
- Evaluation helpers for classification metrics, AUROC, ECE, Brier,
  risk-coverage, isotonic calibration, bootstrap intervals, and proportion
  intervals.
- ChatGPT, Claude, and Gemini extension adapters with backend response
  validation and overlay compatibility.

Latest verified commands:

```powershell
$env:PYTHONPATH='apps\api'
python -m pytest apps\api\tests -q --basetemp .pytest-tmp-final
corepack pnpm typecheck
corepack pnpm test -- --run
corepack pnpm build
git diff --check
```

The latest results were 37 backend tests passed, 19 extension tests passed,
typecheck passed, production build passed, and `git diff --check` passed.
Warnings were existing Starlette/httpx and pytest-asyncio deprecations.

## Dataset and pilot decision

No public dataset is approved for the approximately 30-example,
development-only pilot.

### FELM

Official materials establish model-generated ChatGPT answers, segment-level
factuality labels, comments, error types, and reference URLs. The dataset is
declared CC BY-NC-SA 4.0, distinct from the repository's MIT code license.

Blocked or incomplete:

- per-record upstream rights and permission to retain/show passages;
- complete prompt lineage and source transformation history;
- frozen evidence state and systematic retrieval/publication timestamps;
- source ownership, syndication, and independence groups;
- exact artifact/version identity because public counts are inconsistent;
- complete contamination, deduplication, and privacy review.

FELM remains a candidate only and must not be selected or distributed.

### FActScore

Official materials establish atomic-fact decomposition, human factual
precision annotations, long-form generated biographies, and a default
Wikipedia knowledge snapshot dated 2023-04-01.

Blocked or incomplete:

- dataset and annotation rights are not established by the repository MIT
  software license;
- the public scorer does not preserve auditable evidence URLs, passages, or
  source offsets in its result;
- per-answer, per-source, annotation, and retrieval timestamps are absent;
- source independence, privacy, and contamination controls are not
  established;
- binary atomic support does not implement CalibrAI's three claim outcomes.

FActScore is a methodological complement, not an approved source.

### RAGTruth

Official materials establish model-generated RAG responses, response/source
joins, model and temperature metadata, source contexts, and word-level
hallucination spans.

Blocked or incomplete:

- the repository MIT license does not establish rights for upstream MARCO,
  Yelp, or other source corpora;
- source URLs and publication/retrieval timestamps are not established;
- source independence and same-source leakage controls are incomplete;
- privacy and contamination review is not established;
- hallucination spans are not CalibrAI supported, contradicted, or
  insufficient-evidence outcomes.

RAGTruth is a grounded-generation complement, not an approved source.

## Source decision

The current decision is **neither FELM, FActScore, nor RAGTruth satisfies the
pilot approval requirements**. They must not be combined merely to reach 30
examples; each source would require a separate approval and provenance
manifest.

A controlled manually curated pilot remains a proposal only. It would require:

1. frozen questions, complete answers, generation provenance, and timestamps;
2. exact claim spans and sentence mapping;
3. permitted evidence URLs and captured passages;
4. publisher, authorship, independence, publication, retrieval, and cutoff
   metadata;
5. content digests, rights/retention approval, and privacy review;
6. two pseudonymous independent reviewers;
7. duplicate, near-duplicate, and contamination checks;
8. development-only partition assignment.

No records, annotations, permissions, participants, or scientific metrics
have been fabricated or collected.

## Scientific boundary

The project has no approved dataset, human annotations, adjudicated labels,
calibration partition, or held-out partition. Therefore it must not claim
factual accuracy, calibration, ECE, Brier score, AUROC, inter-annotator
agreement, or risk-coverage performance.

The evaluation code is infrastructure only. It becomes scientifically
meaningful only after independent annotations, adjudication, frozen
partitions, and the validation plan's leakage controls exist.

## Remaining gates

- Study-owner/legal approval for a legitimate data pathway.
- Frozen evidence bundles with rights and temporal provenance.
- Two independent reviewer assignments and completed annotations.
- Calibration and held-out partition population without leakage.
- Real provider contract, credentials, rate limits, retention terms, and
  permitted evidence-capture policy.
- PostgreSQL/Supabase/RLS, deployment monitoring, and authenticated browser
  verification in appropriate environments.
- Ethics/institutional approval before participant recruitment.

Until these gates pass, release status is development-ready for deterministic
engineering only; it is not research-evaluation-ready, scientifically
validated, study-ready, or production-ready.
