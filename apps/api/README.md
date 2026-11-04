# CalibrAI API

FastAPI foundation for consent-aware, provider-neutral trust-calibration
signals. The current provider is deterministic `MockSignalProvider`; no real
AI reliability assessment is implemented.

## Local setup

From `apps/api`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

The default `.env.example` points to PostgreSQL. For an isolated local
development server, use SQLite and migrate it before starting Uvicorn:

```powershell
$env:CALIBRAI_DATABASE_URL = 'sqlite:///./calibrai.db'
alembic upgrade head
uvicorn app.main:app --reload
```

`CALIBRAI_API_ORIGINS` accepts a comma-separated list, including the
`chrome-extension://<extension-id>` origin used by a loaded unpacked
extension. For isolated local tests, set `CALIBRAI_DATABASE_URL=sqlite://` or
`sqlite:///./calibrai.db`.

## API boundary

`POST /v1/session` issues a short-lived signed token only when the server-only
enrollment secret is supplied. The enrollment secret is never shipped to the
extension. `POST /v1/consent` creates or updates a participant's consent record
using that token. `POST /v1/signal` requires the configured consent version and validates the
platform, SHA-256 answer hash, request size, and participant existence.
Conversation fields are accepted only in a consent-authorized request and are
never logged by the API. `POST /v1/events` records only validated interaction
metadata. `GET /v1/config` returns configuration for the requested participant.
`DELETE /v1/participant/{participant_id}` cascades deletion of participant data.

Participant UUIDs are identifiers, not authentication. Tokens use HMAC-SHA256,
an intended audience, expiry, and a revocable server-side JTI. The unpacked
development extension stores only an issued token and is appropriate only for
controlled testing. Before public distribution, replace bootstrap enrollment
with authenticated study enrollment and bind it to an extension/session
identity.

## Tests

```powershell
pytest
```

Tests use an isolated SQLite database and never use production credentials.
