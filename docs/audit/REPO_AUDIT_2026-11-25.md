# CalibrAI Repository Audit

- **Date:** 2026-11-25
- **Commit audited:** `main` @ `c38cad4` (54 commits, 2026-10-27 → 2026-11-07)
- **Method:** I read all source files, ran every test suite, the typecheck and the
  build, upgraded a throwaway database with Alembic and diffed it against the models,
  and probed the adapters directly. Each finding below is marked as either
  **verified** (I ran it) or **traced** (I followed the code path but didn't run it
  in a browser).

---

## 1. Bottom line

The engineering foundation is solid. The code builds cleanly and every test passes.
It is a working pipeline that has no real reliability engine and no data behind it
yet:

- Every signal a user would see today comes from one of two places:
  - the **mock provider**, or
  - the **fixture provider**. This one returns "insufficient evidence" for every
    answer, because no evidence fixtures are committed.
- There is no real LLM, retrieval or entailment-checking (NLI) provider, no
  approved dataset, no human annotations, no participants and no ethics approval.
- The existing project docs say all of this honestly.
- Several real bugs block the participant study path (Section 5). Neither the
  Phase 2 reports nor the earlier `docs/audit/` draft mention them.

| Readiness category | Status |
|---|---|
| Development-ready (mock and fixture) | Yes |
| Usable by a real participant in API mode | **No** (see bugs 1, 3, 4, 6) |
| Research-evaluation-ready | No: no approved data or annotations |
| Scientifically validated | No |
| Study-ready | No: no ethics approval, recruitment or event logging |
| Production-ready | No: no live provider, migration drift, in-memory rate limiting |

---

## 2. Verification results

| Check | Command | Result |
|---|---|---|
| Extension unit tests | `npx vitest run` | **19/19 pass** (5 files) |
| Backend tests | `python -m pytest -q --basetemp <dir>` | **41/41 pass**. The 2 errors on the first run came from a Windows temp-folder permission problem, not from the code; both tests pass with a writable `--basetemp`. |
| TypeScript typecheck | `npx tsc --noEmit` | Clean |
| Production build | `npx wxt build` | OK: Chrome MV3, 300.53 kB |
| Migration consistency | `alembic upgrade head` on a throwaway SQLite DB, then `compare_metadata` | **6 differences** (timestamp nullability on `participants.created_at`, `participants.updated_at`, `questionnaires.submitted_at`, `signal_events.occurred_at`, `live_signals.created_at`, `session_tokens.created_at`) |
| Gemini adapter on realistic DOM | Temporary Vitest probe (deleted afterwards) | **2 detections for 1 answer** (bug 2) |

Backend test distribution: `test_api.py` 13, `test_provider.py` 9,
`test_dataset.py` 8, `test_evaluation.py` 8, `test_integration.py` 3.

Extension test distribution: adapters 7, backendSignal 5, core 4, chatgpt 2, hash 1.
**No test imports `entrypoints/content.ts`.**

---

## 3. Commit history (what was done, in order)

| Phase | Commits | Content |
|---|---|---|
| Phase 1: extension foundation (2026-11-04) | `c8c86b4` → `222cedf` | pnpm/WXT/Vitest setup, shared contracts, hashing and duplicate guards, DOM helpers, ChatGPT/Claude/Gemini adapters, Shadow DOM overlay, mock provider, content pipeline, background worker, popup, options page, extension tests |
| Phase 2A: backend (2026-11-04) | `d8a10fc` → `0808b35` | FastAPI shell and settings, DB models, schemas, mock signal service, security controls, authenticated routes, Alembic migration, backend tests, integration docs |
| Phase 2B: reliability pipeline (2026-11-07) | `2e3eefb` → `7d60b09` | Reliability settings and deployment guards, pluggable provider, assessment-state model, normalization, claim extraction, fixture retriever, verification, aggregation fix, unavailable-state handling, metadata and storage privacy fixes |
| Phase 2C: data and evaluation (2026-11-07) | `341e995` → `c38cad4` | Annotation and dataset schemas, leakage detection, metrics (classification, AUROC, ECE/Brier, risk-coverage, isotonic, bootstrap, CI), tests, extension assessment-state rendering, Phase 2B/2C docs |

---

## 4. What's built, component by component

### 4.1 Browser extension

| Component | Files | Status | Notes |
|---|---|---|---|
| MV3 shell (WXT + React 18 + strict TS) | `wxt.config.ts`, `package.json`, `tsconfig.json` | ✅ Done | Only the `storage` permission is requested; content scripts run on chatgpt.com, claude.ai and gemini.google.com |
| Content capture pipeline | `entrypoints/content.ts` | ✅ Works, ⚠️ untested | MutationObserver with a 250 ms debounce. An answer is captured only after two identical non-streaming samples, then hashed with SHA-256 and checked by the duplicate guard. |
| ChatGPT / Claude / Gemini adapters | `src/adapters/*.ts` | ⚠️ Built | Tested only on hand-written HTML snippets. **Never verified on the live sites.** The Gemini adapter has a confirmed double-detection bug (bug 2). |
| Completion, duplicate guard, hashing | `src/core/completion.ts`, `duplicateGuard.ts`, `hash.ts` | ✅ Done | The duplicate guard is a `WeakMap` held in memory, so it resets on every page reload |
| Background routing (mock / API) | `entrypoints/background.ts`, `src/core/backendSignal.ts` | ✅ Done | 8 s timeout. HTTPS is required except on localhost. The backend response is validated. |
| Overlay | `src/overlay/*` | ✅ Partial | Shows checking, high/medium/low, insufficient-evidence, unavailable, abstained and error states, a version tag, dark mode, and one explanation string behind "Why?" |
| Claim / sentence detail UI | — | ❌ Missing | `claimAssessments` and `sentenceFlags` are in the contract and sent by the backend, but never displayed |
| Options page | `entrypoints/options/main.tsx` | ✅ Basic | Mode toggle, API URL, participant ID and token fields, "delete local data" button. No consent or enrollment flow. |
| Popup | `entrypoints/popup/main.tsx` | ⚠️ Placeholder | Hardcoded text: "Active on ChatGPT" |
| Event logging | — | ❌ Missing | Nothing sends `signal_shown` or `explanation_opened` |

### 4.2 Backend (`apps/api`)

| Component | Files | Status | Notes |
|---|---|---|---|
| App shell, CORS, request size limit, error handler | `app/main.py` | ✅ | The size limit checks only the `Content-Length` header, so chunked uploads bypass it |
| Settings and deployment guards | `app/config.py` | ✅ | Production rejects the default secrets, rejects the fixture provider, and rejects raw-conversation storage in participant environments |
| Session tokens | `app/core/auth.py`, `routes/session.py` | ✅ | JWT-shaped HMAC-SHA256 tokens with audience and expiry checks; each token's ID is stored in the DB so it can be revoked; 900 s lifetime; enrollment uses a shared secret |
| Consent | `routes/consent.py`, `services/consent_service.py` | ✅ | Consent is versioned. A signal requires `granted` status and the current version. |
| Participant isolation and deletion | `routes/participants.py`, `models.py` | ✅ | The session's participant must match the request. Deleting a participant cascades to all their data. |
| Signal endpoint | `routes/signal.py` | ✅ | Switches between mock and fixture providers and falls back to `unavailable` if the provider fails. Raw prompt/answer are not stored by default, claim text is removed from the stored copy, and a repeat of the same participant + answer hash returns 409. |
| Events endpoint | `routes/events.py`, `schemas/events.py` | ✅ Built, unused | Rejects metadata keys such as prompt, answer and token. Does **not** check consent. |
| Config endpoint | `routes/config.py` | ✅ | `feature_flags` is hardcoded to `{"mock_signal": True}` |
| Rate limiting | `app/core/rate_limit.py` | ⚠️ | In-memory, per process, keyed by IP address |
| Trials and questionnaires | `models.py` | ⚠️ | Tables only, no endpoints |
| Migration | `alembic/versions/0001_initial.py` | ⚠️ | Doesn't match the models (6 nullability diffs, Section 2) |

### 4.3 Reliability pipeline (`app/services/reliability_service.py`)

| Stage | Status | How it actually works |
|---|---|---|
| Answer normalization | ✅ | Splits into sentences; handles code fences, list markers and headings |
| Claim extraction | ⚠️ Heuristic | Every sentence without a hedge word ("might", "could", "I think", …) becomes a claim. Max 8 claims. **Materiality = sentence length** (≥140 chars high, ≥60 medium, otherwise low). A sentence counts as "quantitative" if it contains a number. |
| Evidence retrieval | ⚠️ Fixture only | **Exact normalized-text match** against a local JSON file. No fixture files are committed (`apps/api/data/` doesn't exist), so retrieval always comes back empty. |
| Verification | ⚠️ Rule-based | Support or contradiction is decided by the sign of the fixture's `relevanceScore`, with `quality ≥ 0.6`. Two or more independent sources make evidence "strong". |
| Aggregation | ✅ | Weighted by materiality (3/2/1). Thresholds: 0.80 for high, 0.60 for medium. Any contradicted high-materiality claim gives low. |
| Real providers (LLM extraction, web retrieval, NLI) | ❌ | None. Production config rejects the fixture provider, so **only the mock can run in production**. |

### 4.4 Evaluation library (`app/evaluation.py`)

Implemented and tested:

- per-class precision, recall and F1, plus macro-F1, accuracy and confusion matrix
- rank-based AUROC that handles ties
- fixed-bin ECE and Brier score
- risk-coverage curve
- isotonic calibration (pool-adjacent-violators, with tied scores pooled)
- seeded percentile bootstrap
- proportion confidence interval

Status: **correct, but only called by tests.** No script, pipeline or dataset uses
it, and no metric has been computed on real data.

### 4.5 Dataset governance (`app/dataset.py`)

Implemented and tested:

- Pydantic schemas for evidence, claim annotations, original annotations,
  adjudications, dataset records, manifest and bundle
- original annotations cannot be overwritten; adjudications are stored separately
  and must give a reason
- supported or contradicted claims must cite evidence
- time-sensitive evidence can't be published after the answer's timestamp
- leakage checks: the same prompt/answer hash across partitions, and
  near-duplicates (similarity ≥ 0.95)
- reviewer conflicts are reported
- manifest with a SHA-256 content digest; JSON import/export

Status: **code complete, zero records.**

### 4.6 Research and governance docs

| Doc | Content |
|---|---|
| `docs/PHASE_2B_1_ARCHITECTURE.md`, `PROVIDER_COMPARISON.md`, `VALIDATION_PLAN.md` | Target reliability architecture, provider options, frozen validation protocol |
| `docs/PHASE_2C_ANNOTATION_HANDBOOK.md`, `PHASE_2C_ANNOTATION_PACKET_TEMPLATE.json` | Reviewer guidance and packet format |
| `docs/PHASE_2C_2_SOURCE_APPROVAL.md` | Approval checklist that a source must pass before use |
| `docs/PHASE_2C_2_PILOT_EXECUTION.md` | Pilot plan, status **blocked**: no approved source |
| `docs/PHASE_2_MASTER_IMPLEMENTATION_REPORT.md` | Phase 2 summary and readiness classification |
| `docs/API.md`, `DATABASE.md`, `SECURITY.md`, `ARCHITECTURE.md`, `DECISIONS.md` | Phase 1/2A reference |

### 4.7 Not done at all

- Approved dataset, frozen evidence bundles, human annotations, adjudicated labels
- Calibration and held-out partitions with data in them
- Any accuracy or calibration result on real data
- Live LLM, retrieval or entailment-checking (NLI) provider integration
- Study platform: recruitment, trial assignment, questionnaire endpoints, event logging
- Ethics or institutional approval
- PostgreSQL row-level security (RLS), deployment, monitoring
- Testing on live ChatGPT, Claude and Gemini pages with real accounts

---

## 5. Defects found

Ordered by impact on the study path.

### Bug 1: Revisiting a conversation in API mode shows errors on every past answer (traced)

- **What happens:** on page reload the in-memory duplicate guard is empty, so the
  extension re-sends each earlier answer to the backend.
- **Why it fails:** the backend has a unique constraint on
  `(participant_id, answer_hash)` (`app/database/models.py:100`) and returns 409
  (`app/api/routes/signal.py:78`). The extension treats any non-OK response as an
  error (`src/core/backendSignal.ts:35`).
- **Effect:** every previously signalled answer shows "Could not check this answer".
- **Fix:** treat 409 as "already signalled". Either return the stored
  `response_json` from the backend, or keep a hash cache in extension storage.

### Bug 2: Gemini detects each answer twice (verified)

- **What happens:** `.model-response` and its inner `<message-content>` both match.
  `closest('.model-response, message-content')` returns each element itself
  (`src/adapters/gemini.ts:29`).
- **Effect:** two overlays and two backend requests per answer. With bug 1, the
  second request also returns 409.
- **Why the test missed it:** the existing test uses a `<div>` instead of the real
  `<message-content>` element.
- **Fix:** resolve every match to the outermost `.model-response`, and update the
  test fixture to use the real element.

### Bug 3: The extension never sends interaction events (traced)

- `/v1/events` exists and is tested, but nothing in `src/` or `entrypoints/` calls it.
- **Effect:** none of the behavioral data a trust-calibration study needs (signal
  shown, explanation opened, dismissed) is collected.

### Bug 4: No participant onboarding; tokens expire after 15 minutes (traced)

- The extension has no enrollment or consent screen.
- `/v1/consent` requires an existing session token, so consent has to be granted
  outside the extension, for example with curl.
- `session_ttl_seconds = 900` (`app/config.py:26`) and there is no refresh flow, so
  a participant would have to paste a new token every 15 minutes.

### Bug 5: Events are accepted without current consent (traced)

- `routes/events.py:23` uses `get_participant`, not `require_capture_consent`, so a
  participant who withdrew consent can still have events recorded.
- This is an ethics and governance gap.

### Bug 6: The extension can't reach a real deployed backend (traced)

- `host_permissions` contains only the placeholder `https://api.calibrai.example/*`
  (`wxt.config.ts:14`).
- The default `api_origins` doesn't include the extension's `chrome-extension://`
  origin. That origin appears only in `.env.example`.

### Bug 7: `score = 0.0` means several different things (traced)

- The score is 0.0 for `insufficient_evidence` (`reliability_service.py:215`), for
  `unavailable`, and for "every claim contradicted".
- It is a weighted fraction of supported claims, not a calibrated probability.
- If ECE or Brier is later computed directly on `score`, these states collide.
- **Fix:** exclude non-assessed states from calibration fitting, or make `score`
  nullable.

### Minor issues

- The checking and error overlays are hardcoded to `modelVersion: 'mock-v1'`
  (`entrypoints/content.ts:36,58`), so they show "CalibrAI mock-v1" in API mode.
- The popup hardcodes "Active on ChatGPT" (`entrypoints/popup/main.tsx:9`).
- "Delete local extension data" (`entrypoints/options/main.tsx:48`) clears storage
  but leaves the old values in the form, so the next Save writes them back.
- `backendSignal.ts` reports an invalid response body as "Backend returned 200",
  which is misleading.
- The proportion confidence interval uses the Wald method (`evaluation.py:239`),
  which gives a zero-width interval at 0/n and n/n. Wilson is the better choice for
  small samples.
- The request size limit checks only the `Content-Length` header.
- The rate limiter is per process, so it won't work across multiple workers.
- A capture only happens after two stable samples, which requires a further page
  change (DOM mutation) after streaming ends. If the page stops changing at exactly
  that point, the answer is never captured. There is no fallback timer.

---

## 6. Accuracy of the existing documentation

### The earlier `docs/audit/` draft (untracked, dated 2026-11-16)

Treat it as a draft, not as a source of truth:

- It says the options page shows consent status. **It doesn't.**
- It says Vitest covers the content script's observation, debounce, stability
  check and overlay mount. **No test imports `content.ts`.**
- It marks the popup and options page "COMPLETE AND VERIFIED", but the popup is a
  placeholder with hardcoded text.
- Its Gemini note guesses at a Shadow DOM problem. The confirmed problem is the
  double selector match (bug 2).
- It does not mention bugs 1–6.

### Project docs

- `docs/PHASE_2_MASTER_IMPLEMENTATION_REPORT.md:70` says the Phase 2 files are
  uncommitted. They are now committed (`2e3eefb` … `c38cad4`).
- `README.md` describes only Phase 1. It says claim-level explanations are not
  implemented: the backend now produces them, though the UI still doesn't show
  them. It doesn't link any of the Phase 2 docs.
- Otherwise, the Phase 2 reports describe what is and isn't done accurately and
  candidly, including the migration drift, which I reproduced.

---

## 7. Recommended next steps

1. **Unblock the study path:** fix bugs 1, 2 and 3, and add tests for
   `content.ts` and for a real `<message-content>` Gemini fixture.
2. **Participant onboarding:** an enrollment and consent screen in the extension,
   token refresh, a consent check on `/v1/events`, a real host permission, and CORS
   for the extension origin (bugs 4–6).
3. **Database:** a reviewed `0002` migration that fixes the 6 nullability diffs,
   then verification on PostgreSQL.
4. **Data:** get an approved source, freeze evidence bundles, run independent
   double annotation, and fill the development, calibration and held-out partitions.
5. **Provider:** choose and integrate real retrieval and verification, and make
   `score` meaningful for calibration (bug 7).
6. **UI:** show claim-level detail and sources so the "Why?" panel actually
   explains the signal.
7. **Docs:** update the README and the master report's commit status, and replace
   the earlier `docs/audit/` draft with this file.

---

## Resolved on this branch

Branch `audit-fixes-and-selfconsistency`, as of 2026-11-26. The branch history was rewritten
after this audit was written, so these hashes are the current ones (from `git log main..HEAD`).

| Finding | Resolution | Commit |
|---|---|---|
| Bug 1: revisited answers show errors | The backend returns the stored response for a known `(participant, answer hash)`, also on a race; the extension caches signals per session | `169d25f` |
| Bug 2: Gemini detects each answer twice | Every match resolves to the outermost `.model-response`; the test uses a real `<message-content>` element | `8a02385` |
| Bug 3: no interaction events | The overlay sends `signal_shown`, `explanation_opened` and `signal_dismissed` through the background worker | `7efe340` |
| Bug 5: events accepted without consent | `/v1/events` requires current consent | `e9841d3` |
| Bug 6: can't reach a deployed backend | `host_permissions` come from `WXT_API_ORIGIN` (https, validated); local ports only in development builds; the placeholder domain is gone; `docs/DEPLOY.md` explains adding `chrome-extension://<id>` to `CALIBRAI_API_ORIGINS` | `732655f` |
| Bug 7: `score = 0.0` means several things | `score` is null when no score is meaningful (insufficient evidence, unavailable, abstained) | `4305a7d` |
| Minor: `mock-v1` on API overlays, hardcoded popup site, options reset | Overlays are labelled by mode; the popup shows the active site; reset clears the form | `342f3e8` |
| Minor: Wald interval | Wilson score interval | `2017d08` |
| Minor: no fallback timer for capture | A scan scheduler re-checks answers that are still settling | `cac183f`, `c93ef64`, `712e8aa` |
| Migration drift (6 nullability differences) | Migration `0002`: NOT NULL timestamps plus the study trial columns; `compare_metadata` reports no differences on SQLite | `7457a92` |
| UI: the "Why?" panel didn't explain the signal | Overlay redesign: a collapsed pill (icon, level, reason) that expands into the checked claims with per-sample verdicts; light and dark tokens; a preview page | `a5a8307` |

**Partly resolved.** Bug 4: sessions now last 24 hours (`2ec832e`) and the study harness has its
own enrollment and consent flow (`278de3c`, `2f81c4c`), but the extension still has no onboarding
or consent screen and no token refresh.

**Still open.** `backendSignal.ts` still reports an invalid response body as "Backend returned
200"; the request size limit still checks only `Content-Length`; the rate limiter is still per
process; PostgreSQL and the row-level-security policies are unverified.

**Documentation (section 6).** The earlier `docs/audit/` draft has been deleted (it stays in git
history), the README has been rewritten (`1414b87`), and the master report now says the Phase 2
work is committed.
