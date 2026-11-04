# CalibrAI Phase 2A.2 Integration Report

Date: 2026-11-04

## Scope

This phase verified the existing API-mode boundary and local authenticated
workflow. The backend continues to use `MockSignalProvider`; no real AI
reliability engine was added.

## Implemented

- Extracted the background worker's API request boundary into
  `src/core/backendSignal.ts` without changing the runtime flow.
- Preserved mock mode as the default and independent local provider.
- Kept API configuration in extension storage:
  - runtime mode
  - API base URL
  - participant ID
  - short-lived session token
- Preserved background-only network access, bearer authentication, timeout,
  HTTPS enforcement outside localhost, response validation, and safe error
  handling.
- Added worker-boundary tests for authenticated requests, missing
  configuration, HTTPS enforcement, malformed responses, and backend errors.
- Added a backend lifecycle integration test covering enrollment, consent,
  authenticated capture, provider execution, response shape, duplicate
  prevention, consent withdrawal, deletion, and session invalidation.
- Added realistic streaming fixtures for ChatGPT, Claude, and Gemini.
- Added overlay compatibility coverage proving a validated high-confidence
  response renders the corresponding overlay state.
- Fixed configuration parsing so the comma-separated
  `CALIBRAI_API_ORIGINS` value in `.env.example` is accepted by Pydantic
  Settings.
- Updated local setup instructions to require database migration before
  starting Uvicorn.

## Automated tests passed

### Backend

```powershell
$env:PYTHONPATH = 'apps\api'
python -m pytest apps\api\tests -q
```

Result:

```text
15 passed, 2 warnings in 0.64s
```

Warnings were upstream deprecations from Starlette/httpx and
`pytest-asyncio` on Python 3.14.

The integration-specific test also passed independently:

```powershell
$env:PYTHONPATH = 'apps\api'
python -m pytest apps\api\tests\test_integration.py -q
```

Result:

```text
2 passed, 2 warnings in 0.12s
```

Compilation passed:

```powershell
python -m compileall -q apps\api\app apps\api\alembic apps\api\tests
```

### Extension

```powershell
corepack pnpm test
corepack pnpm typecheck
corepack pnpm build
```

Results:

- 5 Vitest files passed
- 19 Vitest tests passed
- TypeScript typecheck passed
- WXT production build passed
- Production output: `.output\chrome-mv3`

The focused adapter/overlay run passed 11 tests, including streaming fixtures
for all three platforms and rendering of the backend-compatible high signal.

## Local HTTP verification

An actual Uvicorn process was started against a migrated SQLite database. The
following lifecycle was exercised over HTTP:

1. `GET /health`
2. `POST /v1/session`
3. `POST /v1/consent` with granted consent
4. `POST /v1/signal` with a ChatGPT capture
5. `POST /v1/consent` with withdrawn consent
6. A second signal request after withdrawal

Observed result:

```text
health=ok; consent=granted; signal=signal; confidence=high; model=mock-v1
withdrawn_signal=403
```

The temporary SQLite database was removed after the smoke test.

## Manually verified

- Local FastAPI HTTP lifecycle against Uvicorn.
- Mock provider response (`mock-v1`, high confidence, score `0.85`).
- Consent withdrawal blocking subsequent capture.
- Production extension build output.
- Configuration parsing for comma-separated API origins.

## Not verified

- Live authenticated ChatGPT, Claude, or Gemini browser conversations.
- Extension injection and content-script-to-background messaging in a real
  authenticated Chrome session.
- PostgreSQL/Supabase migration execution.
- PostgreSQL Row-Level Security behavior.
- Production extension identity binding.
- Public deployment authentication and shared rate limiting.

The available browser pages did not provide authenticated conversations for
all three providers, so adapter fixtures and automated tests are not reported
as live browser verification.

## Security and privacy evidence

- Requests without a session token are rejected.
- Invalid token signatures are rejected.
- Expired and revoked sessions are rejected by the existing tests.
- Missing, withdrawn, and outdated consent reject signal processing.
- Duplicate answer hashes do not create duplicate signals.
- Participant deletion invalidates the participant's session and subsequent
  authenticated access.
- The integration test confirms prompt and answer text do not appear in
  captured application logs.
- The extension worker does not log prompt or answer content.
- API failures return generic safe errors to the extension and do not include
  backend response bodies.

The extension still sends prompt/answer fields only in API mode after the
client has been configured with a session token; the backend remains the
authoritative consent check.

## Known limitations

- The local integration test uses FastAPI's in-process `TestClient` for the
  automated lifecycle and a separate real Uvicorn HTTP smoke flow. It does not
  launch Chrome or the packaged extension.
- SQLite does not emulate PostgreSQL RLS.
- The current enrollment-secret session bootstrap is for controlled
  development/study setup only.
- The signal remains deterministic mock output and must not be interpreted as
  factuality or reliability assessment.

## Recommended next step

Before Phase 2B, run a controlled Chrome test with an authenticated account on
each supported platform and a real local API-mode extension configuration.
Separately provision an isolated PostgreSQL/Supabase test database and verify
the migration and RLS policies there.
