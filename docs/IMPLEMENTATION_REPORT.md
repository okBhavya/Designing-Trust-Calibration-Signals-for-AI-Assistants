# CalibrAI Initial Milestone Report

## Files created

- `wxt.config.ts`, `package.json`, `pnpm-workspace.yaml`, `tsconfig.json`,
  `vitest.config.ts`
- `entrypoints/background.ts`, `entrypoints/content.ts`
- Popup and options HTML, React, and CSS entrypoints
- `src/core/` contracts, hashing, completion tracking, and duplicate guard
- `src/adapters/` shared DOM helpers, registry, and independent ChatGPT,
  Claude, and Gemini adapters
- `src/overlay/` Shadow DOM React overlay and styles
- `src/signals/` mock provider and response validation
- Focused tests under `tests/`
- `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_PLAN.md`,
  `docs/DECISIONS.md`

## Files modified

- `README.md` now contains installation, development, verification, status, and
  limitation information.

## Technologies introduced

WXT 0.20, Vite, React 18, TypeScript 5.9, Vitest, and jsdom. No backend,
database, or analysis dependencies were added because those are explicitly
outside this milestone.

## Completed behavior

The extension is restricted to the three planned host origins and selects an
independent adapter for the current page. ChatGPT, Claude, and Gemini adapters
all detect assistant turns, extract the preceding user prompt and answer,
return text nodes, detect streaming, and provide an overlay target through the
same `DetectedAnswer` contract. The content script waits for two identical
non-streaming samples, hashes the answer, prevents duplicate processing, and
sends a typed platform-neutral capture through the background service worker.
The same Shadow DOM signal mounts below each adapter's answer. The original
answer DOM is not replaced.

## Verification results

Executed successfully on 2026-11-04:

- `corepack pnpm test`: 4 test files, 12 tests passed.
- `corepack pnpm typecheck`: passed with no errors.
- `corepack pnpm build`: passed; generated `.output\chrome-mv3`.

The final verification run after adding overlay isolation and theme-environment
coverage passed 4 test files and 12 tests.

## Browser verification

The production output was inspected at `.output\chrome-mv3`; its manifest
contains the expected three content-script matches and only the `storage`
permission. The exact manual installation flow is:

```powershell
Set-Location 'C:\Users\soumy\Designing-Trust-Calibration-Signals-for-AI-Assistants'
corepack pnpm install
corepack pnpm build
Get-ChildItem .output\chrome-mv3
```

In Chrome, open `chrome://extensions`, enable **Developer mode**, select
**Load unpacked**, and choose:

```text
C:\Users\soumy\Designing-Trust-Calibration-Signals-for-AI-Assistants\.output\chrome-mv3
```

Live browser automation reached Gemini's unauthenticated landing page and
confirmed the page shell, dark theme, and prompt textbox. It did not have an
authenticated conversation, so no assistant response or extension-injected
overlay could be verified there. ChatGPT and Claude navigation failed in the
available browser environment. Consequently, live response, streaming,
navigation, and overlay behavior remain unverified rather than being reported
as successful.

## Limitations

All three providers' DOM markup can change, so selectors are isolated and
semantic-first but still require authenticated live browser regression checks.
Claude and Gemini selectors are best-verified heuristics for their current
semantic markers, not public API contracts. Development diagnostics are gated
by `import.meta.env.DEV` and report platform, adapter selection, counts,
streaming state, capture status, signal status, and duplicate prevention
without logging prompt or answer text. The confidence values are deterministic
mock states and must not be interpreted as factuality judgments.

## Phase 2A backend update

The backend foundation is now implemented under `apps/api/`. It includes
FastAPI routes for health, consent, signal requests, events, participant
configuration, and participant deletion; strict Pydantic schemas; SQLAlchemy
models; an Alembic migration; a replaceable `SignalProvider` interface; and
isolated SQLite tests. `MockSignalProvider` is the only provider and does not
perform real AI reliability assessment.

Verification:

- `python -m pytest apps\api\tests -q`: 10 passed, with only upstream
  deprecation warnings from Starlette/httpx and Python 3.14.
- `python -m compileall -q apps\api\app apps\api\alembic apps\api\tests`:
  passed.
- `python -m alembic upgrade head` with `CALIBRAI_DATABASE_URL=sqlite://`:
  passed.
- `corepack pnpm test`: 12 extension tests passed.
- `corepack pnpm typecheck`: passed.
- `corepack pnpm build`: passed; generated `.output\chrome-mv3`.

## Phase 2A.1 secure integration update

Implemented:

- Short-lived HMAC-SHA256 session tokens with `sub`, `aud`, `iat`, `exp`, and
  revocable `jti` claims.
- Server-side session issuance protected by an enrollment secret. The secret
  is never included in the extension.
- Authenticated participant matching on consent, signal, events, config, and
  deletion routes.
- Session revocation and expiry checks.
- Explicit extension `mock` and `api` runtime modes.
- Background-only API requests with bearer token storage, HTTPS enforcement
  outside localhost, eight-second timeout, error handling, response validation,
  and retry-safe duplicate handling.
- Options-page configuration for API base URL, participant ID, and session
  token.
- Error/timeout overlay text: “Could not check this answer”.
- API-mode consent enforcement remains server-side; withdrawn or outdated
  consent prevents signal capture.
- Session-token migration, indexes, cascade deletion, and PostgreSQL RLS
  policy for session records.

Final verification:

- `python -m pytest apps\api\tests -q`: 12 passed.
- `python -m compileall -q apps\api\app apps\api\alembic apps\api\tests`:
  passed.
- `python -m alembic upgrade head` with `CALIBRAI_DATABASE_URL=sqlite://`:
  passed.
- `corepack pnpm typecheck`: passed.
- `corepack pnpm test`: 4 files, 12 tests passed.
- `corepack pnpm build`: passed; generated `.output\chrome-mv3`.
- Pylance workspace diagnostics: no diagnostics.

The local SQLite flow was verified. No PostgreSQL server or configured
`CALIBRAI_DATABASE_URL` was available in this environment, so PostgreSQL
execution and live Supabase RLS behavior remain explicitly unverified.

## Recommended next milestone

Replace bootstrap enrollment with authenticated study enrollment and extension
identity verification, then add an end-to-end test that runs the real
background API mode against a local FastAPI server. Only after that boundary
is deployed and measured should Phase 2B claim extraction, answer sampling, and
consistency components begin.
