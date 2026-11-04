# CalibrAI

CalibrAI is a Chrome extension foundation for displaying measured, research-oriented
trust calibration signals below AI assistant answers. The current milestone
supports ChatGPT, Claude, and Gemini through independent platform adapters and
a clearly labelled local mock signal.

## Status

Completed:

- WXT + Vite + React 18 + strict TypeScript Manifest V3 extension.
- Background service worker, content script, popup, and options page.
- Independent ChatGPT, Claude, and Gemini adapters implementing one shared
  capture interface with prompt/answer extraction, streaming detection, stable
  completion tracking, platform metadata, and duplicate prevention.
- Typed platform-neutral capture flow from content script through the
  background service worker to the shared mock signal provider.
- Shadow DOM overlay with checking, high/medium/low, expanded, error, and
  not-applicable states.
- Unit tests for hashing, completion, duplicate prevention, response validation,
  and independent DOM extraction for all three adapters.

The backend foundation and authenticated API boundary are implemented under
`apps/api`. The API currently returns a deterministic mock signal and requires
participant consent. Not yet implemented: real reliability assessment,
claim-level explanations, study platform, and research analysis.

## Development

Prerequisites: Node.js 20+ and Corepack. This repository pins pnpm 9 in
`package.json`.

```powershell
corepack pnpm install
corepack pnpm dev
corepack pnpm test
corepack pnpm typecheck
corepack pnpm build
```

For Chrome Developer Mode, run `corepack pnpm build`, open
`chrome://extensions`, enable Developer mode, choose **Load unpacked**, and
select `.output\chrome-mv3`. Open any supported site (`chatgpt.com`,
`claude.ai`, or `gemini.google.com`), send an answer, and wait for the signal
below a completed assistant response.

All extension network requests are reserved for the background worker. Mock
mode makes no network requests; API mode requires a configured short-lived
session token and consent and sends the captured answer only through the
background worker.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Implementation plan](docs/IMPLEMENTATION_PLAN.md)
- [Decisions](docs/DECISIONS.md)
- [Implementation report](docs/IMPLEMENTATION_REPORT.md)
- [API contract](docs/API.md)
- [Database schema](docs/DATABASE.md)
- [Security and privacy](docs/SECURITY.md)

## API development

The backend lives in [`apps/api`](apps/api/README.md). It uses FastAPI,
Pydantic, SQLAlchemy, and Alembic. The current provider is explicitly a
deterministic mock and does not perform real reliability assessment.

```powershell
Set-Location apps\api
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
$env:CALIBRAI_DATABASE_URL = 'sqlite:///./calibrai.db'
alembic upgrade head
uvicorn app.main:app --reload
```

Run backend integration tests from the repository root with:

```powershell
$env:PYTHONPATH = 'apps\api'
python -m pytest apps\api\tests -q
```

See [the Phase 2A.2 integration report](docs/PHASE_2A_2_INTEGRATION_REPORT.md)
for actual verification results and remaining limitations.