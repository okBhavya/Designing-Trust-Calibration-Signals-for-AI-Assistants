# CalibrAI Phase 2 Master Implementation Report

Date: 2026-11-07

## Executive status

This integrated pass completed independent engineering work that was possible
without approved source material, provider credentials, human annotations,
participant recruitment, or production infrastructure. It did not fabricate
data or claim scientific validation.

The project is **development-ready for the deterministic backend and
extension**, and **integration-ready for the existing mock and fixture
providers**. It is not scientifically validated, study-ready, or
production-ready.

## Completion audit hardening

The final engineering audit found and corrected three implementation defects:

- missing answers now remain `unavailable` with no confidence instead of being
  mislabeled `low`;
- weighted reliability aggregation now uses the frozen 0.60 unreliable/medium
  boundary from the validation protocol; and
- evaluation rejects non-finite probabilities/confidences and pools tied
  isotonic scores before prediction.

Regression coverage now includes tied isotonic scores, invalid probability and
confidence values, non-finite AUROC scores, boolean correctness validation, the
aggregation boundary, and unavailable-answer semantics.

## Implemented

### Reliability and privacy

- Preserved the modular `SignalProvider` boundary and existing
  `MockSignalProvider`.
- Preserved deterministic normalization, claim extraction, evidence fixtures,
  verification, weighted aggregation, and distinct assessment states.
- Added validation that signal and event metadata cannot carry prompt, answer,
  conversation, response, token, or secret fields.
- Prevented raw claim text from being persisted in `LiveSignal.response_json`;
  prompt and answer columns remain disabled by default.
- Preserved consent, participant isolation, duplicate prevention, deletion, and
  extension response compatibility.

### Scientific evaluation infrastructure

Added [evaluation.py](../apps/api/app/evaluation.py), providing:

- per-class precision, recall, F1, macro-F1, accuracy, and confusion matrices;
- binary AUROC with explicit two-class validation;
- fixed-bin ECE and Brier score with empty-bin counts;
- risk-coverage points ordered by confidence;
- deterministic isotonic calibration;
- seeded bootstrap intervals;
- proportion confidence intervals.

The helpers reject empty, mismatched, invalid, or one-class inputs rather than
returning success-shaped defaults.

## Worktree reconciliation

At reconciliation time, `git diff --stat` reports the existing tracked diff as
**12 files changed, 314 insertions, and 15 deletions**. The worktree also
contains untracked Phase 2 implementation, test, and documentation files;
untracked files are not included in that Git statistic. No commit or push was
created.

Earlier Phase 2 files remain uncommitted in the worktree and were preserved.

## Verification

### Backend

Command:

```powershell
$env:PYTHONPATH='apps\api'
python -m pytest apps\api\tests -q --basetemp .pytest-tmp-master-3
```

Latest result: **41 passed, 2 warnings**. The warnings are the existing
Starlette/httpx and pytest-asyncio deprecations.

Python compilation also passed with:

```powershell
python -m compileall -q apps\api\app apps\api\tests
```

### Extension

Commands:

```powershell
corepack pnpm typecheck
corepack pnpm test -- --run
```

Results:

- TypeScript typecheck: **passed**
- Extension tests: **19 passed**

The production extension build passed against the final worktree with
`corepack pnpm build` (WXT Chrome MV3 build, 300.53 kB total output).

### Formatting

Command:

```powershell
git diff --check
```

Result: **passed**.

### Migration verification

The existing `apps\api\calibrai.db` was inspected read-only. It contains only
an empty `alembic_version` table, with no recorded revision and no application
tables. `alembic current` was empty while `alembic heads` reported
`0001_initial`; therefore the original `Target database is not up to date`
result means this local database is uninitialized/behind, not that it has a
branching migration history. It was not modified.

A disposable copy was upgraded to `0001_initial` and checked. Alembic then
reported six genuine model/migration differences: timestamp nullability for
`participants.created_at`, `participants.updated_at`,
`questionnaires.submitted_at`, `signal_events.occurred_at`,
`live_signals.created_at`, and `session_tokens.created_at`. No migration was
rewritten and no database was changed. A reviewed follow-up migration is
required before claiming migration consistency; it must be tested against a
disposable database and then applied through the normal deployment process.

### Not available

- No live external provider was configured or tested.
- No PostgreSQL/Supabase/RLS environment was available for verification.
- No authenticated live browser sessions were available for browser-level
  verification.

## Scientific status

- Approved dataset: **none**
- Human annotations: **none**
- Adjudicated labels: **none**
- Calibration partition: **not populated**
- Held-out partition: **not populated**
- Metrics calculated on real data: **none**
- Scientific factual-reliability claim: **not supported**

The evaluation helpers are implementation infrastructure only. They have not
been used to report accuracy, calibration, ECE, Brier, AUROC, or
risk-coverage results.

No runtime call site fits calibration parameters or evaluates held-out data:
`fit_isotonic` and the other evaluation helpers are currently used only by
evaluation tests. The validation plan requires any future calibration fit to
use only the calibration partition and reserves held-out data for final
evaluation; that separation remains a documented protocol requirement, not a
claim that a real evaluation has occurred.

## Provider and data blockers

The Phase 2C.4 decision remains unchanged: FELM, FActScore, and RAGTruth are
not approved. The controlled-curation route remains a proposal requiring
study-owner rights, privacy, provenance, frozen evidence, timestamps,
independence, and reviewer approvals.

Live retrieval and verification providers remain deferred until a provider
contract, server-side credentials, rate/retention terms, and permitted
evidence-capture policy are available. The fixture provider must not be
described as factual-reliability validation.

## Study and production status

Existing consent, session, event, trial, questionnaire, isolation, and
deletion foundations remain intact. No participant data was collected and no
ethics or institutional approval was claimed. Production security is not
verified from SQLite tests alone, and deployment monitoring, PostgreSQL/RLS,
provider operations, and authenticated browser verification remain blocked by
environment and governance prerequisites.

## Release classification

| Category | Status |
|---|---|
| Development-ready | Yes, for current deterministic backend/extension |
| Integration-ready | Yes, for mock and fixture providers |
| Research-evaluation-ready | No, approved data and annotations are absent |
| Scientifically validated | No |
| Study-ready | No, ethics/owner/recruitment prerequisites are absent |
| Production-ready | No, live provider, database, deployment, and security verification are incomplete |

## Required next actions

1. Obtain study-owner and legal approval for a legitimate data pathway.
2. Freeze approved evidence bundles and collect two independent annotations.
3. Populate development, calibration, and held-out partitions without leakage.
4. Configure and contract a permitted real retrieval/verifier provider.
5. Run replay, calibration, held-out, security, database, and browser
   verification in their appropriate environments.
6. Only then publish scientific or production-readiness claims.

## Final engineering reconciliation

- The deterministic implementation, tests, typecheck, production build, and
  Python compilation are complete for the available environment.
- Production configuration rejects `reliability_fixture`; missing answers
  cannot receive high confidence (the fixture path returns `unavailable`; the
  mock path returns its explicit low/abstained response), and
  provider-unavailable failures use the unavailable state.
- The frozen reliability boundaries remain 0.60 for the medium/low boundary
  and 0.80 for the high boundary.
- Migration consistency is not complete because the existing local database is
  uninitialized and the disposable upgraded schema exposes six nullability
  differences requiring a reviewed follow-up migration.
