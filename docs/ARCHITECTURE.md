# CalibrAI Architecture

## Scope

The first milestone is a Chrome Manifest V3 extension that observes completed
answers from ChatGPT, Claude, and Gemini and renders the same non-invasive,
mock reliability signal below each answer. The extension is provider-neutral:
each platform is an interchangeable source of normalized captures.

## Repository layout

```text
apps/
  extension/          WXT browser extension (first milestone)
  study/              reserved for the research participant application
  api/                FastAPI signal, consent, event, and participant API
packages/
  core/               shared domain contracts and deterministic utilities
  ui/                 shared UI components for extension and study app
  data/               reserved data access and schemas
data/
  questions.json      future study question bank
validation/           future signal validation scripts
analysis/             future Python analysis project
docs/                 architecture, decisions, plans, and reports
```

The initial implementation keeps the runnable extension at the repository root
(`entrypoints/`, `src/`) so WXT can be loaded without a second package boundary.
It is the `apps/extension` conceptual package and can be moved there without
changing domain boundaries once the study and API packages are introduced.

## Runtime components

### Adapter registry and content script

The content script runs on the three declared origins and selects an adapter
from `src/adapters/index.ts` using the current hostname. It owns observation
but not selectors or platform assumptions. A `MutationObserver` discovers
dynamically rendered messages; the selected adapter extracts prompt/answer
text, sentence-capable text nodes, streaming state, and the mount target. A
`WeakMap` plus answer hash prevents repeat processing.

### Site adapters

`ChatGPTAdapter`, `ClaudeAdapter`, and `GeminiAdapter` are isolated modules.
Each implements `SiteAdapter`: page matching, assistant detection, prompt and
answer extraction, streaming detection, completion-compatible output, text
nodes, and an overlay mount target. Selectors are not used by shared capture,
signal, or UI code. Adding a platform means adding an adapter and its tests.

### Overlay

Each signal is mounted in a dedicated host element immediately after the answer
container. React renders inside an isolated Shadow DOM through
`src/overlay/mountOverlay.tsx`, isolating styles and preventing changes to the
host site's DOM content. The UI supports checking, high/medium/low confidence,
expanded explanation, error/timeout, and not-applicable states. The first
milestone uses a clearly marked deterministic mock signal provider.

### Background service worker and capture boundary

The service worker is the only network boundary. Content scripts send a typed
`CaptureRequest` containing `platform`, prompt, answer, and answer hash. In
mock mode the worker uses the local provider. In API mode it reads a
short-lived session token from extension storage, validates the HTTPS endpoint
configuration, applies an eight-second timeout, and sends the request to the
FastAPI service. The worker validates the platform-independent
`CaptureResponse`; consent is enforced by the API before raw conversation
fields are persisted or processed.

### Popup and options

The popup reports extension status and consent state. Options provides an
explicit consent toggle and a local-only data deletion action. No conversation
text is persisted by this milestone.

## Data flow

1. A supported platform renders an assistant message.
2. The content script selects the platform adapter and schedules a scan.
3. The adapter ignores non-assistant, incomplete, and still-streaming messages.
4. The normalized capture is hashed and sent to the background worker.
5. The worker validates the capture and invokes the shared mock/API signal
   provider.
6. The shared response returns to the content script.
7. The same overlay mounts below the adapter-provided target.

## Backend API

The backend is FastAPI with Pydantic, SQLAlchemy, Alembic, and
Supabase/PostgreSQL with row-level security. It accepts validated answer hashes
and consent-bound requests, rate limits requests, and returns a versioned
signal response. `SignalProvider` is the replacement boundary for the current
`MockSignalProvider`; real claim extraction and judging are Phase 2B work. The
study app and Python analysis packages consume the same versioned contract.

## Security and privacy boundaries

- Host permissions are limited to the three supported AI sites.
- No history, tabs, or unrestricted host permissions are required.
- Network access is reserved for the background worker.
- Secrets remain server-side.
- Participant identifiers are random UUIDs and are not trusted as
  authorization.
- Signals are cacheable by answer hash; raw text is not persisted by default.
- Consent is required before future conversation data transmission.
- Deletion and retention policy surfaces belong in the options/API milestones.

## Adapter limitations

The three adapters intentionally use semantic attributes and stable structural
markers where available, but all provider DOMs are undocumented and can change.
ChatGPT has the strongest verified coverage in this repository. Claude support
targets `data-testid` message markers and streaming attributes. Gemini support
targets its model-response custom elements/classes and busy/streaming markers.
Provider-specific browser regression fixtures should be added whenever markup
changes; the shared processing and overlay layers do not need to change.
