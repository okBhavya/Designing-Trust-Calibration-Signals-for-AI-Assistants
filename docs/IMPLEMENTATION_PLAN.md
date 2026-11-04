# CalibrAI Implementation Plan

## Phase 1 — Multi-platform foundation (completed in this milestone)

- Establish pnpm workspace metadata and strict TypeScript configuration.
- Configure WXT for Manifest V3 and React.
- Add background worker, content script, popup, and options entrypoints.
- Limit extension matches and permissions to supported sites.
- Add shared domain contracts, platform identifiers, typed capture messages, and
  deterministic answer hashing.

## Phase 2 — Independent platform adapters (completed in this milestone)

- Define the adapter contract and adapter registry.
- Implement independent ChatGPT, Claude, and Gemini DOM adapters.
- Extract prompts, answers, text nodes, and platform metadata through one format.
- Detect streaming and wait for a stable completion window on every platform.
- Prevent duplicate processing by container identity and answer hash.
- Mount signals below adapter-provided targets without replacing answers.

## Phase 3 — Overlay foundation (completed in this milestone)

- Render a reusable React overlay inside Shadow DOM.
- Support all initial visual states and expanded explanations.
- Add keyboard accessibility, reduced-motion support, light/dark themes, and
  compact native-looking styling.
- Keep the signal provider mock and production provider boundary explicit.

## Phase 4 — Verification (completed in this milestone)

- Add unit tests for hashing, completion detection, duplicate prevention, and
  signal response validation.
- Run tests, type checking, and a production build.
- Document installation, commands, limitations, and actual verification results.

## Subsequent milestones

1. Replace the mock provider with a consent-aware background/API integration.
2. Add sentence-level claim mapping and uncertainty explanations.
3. Add live browser regression fixtures for provider DOM changes.
4. Build FastAPI + Supabase signal and retention services.
5. Build the controlled study platform and consent/participant workflows.
6. Add Python validation and statistical analysis with preregistered metrics.

## Phase 2A — Backend foundation (completed)

- Add FastAPI routes for health, consent, signals, events, configuration, and
  participant deletion.
- Add strict Pydantic contracts matching the extension capture/response shape.
- Add SQLAlchemy models and an Alembic PostgreSQL migration with indexes,
  foreign keys, uniqueness, cascades, and RLS policies.
- Add a replaceable `SignalProvider` interface with `MockSignalProvider`.
- Add consent verification, request-size limits, CORS allowlisting, safe
  diagnostics, and development rate limiting.
- Add isolated SQLite API tests; no production credentials or data are used.

## Phase 2A.1 — Secure integration boundary (completed)

- Add short-lived signed session tokens with audience, expiry, participant
  binding, persisted JTI revocation, and server-only bootstrap enrollment.
- Require authenticated participant matching on consent, signal, event,
  configuration, and deletion routes.
- Add explicit extension mock/API runtime modes with background-only API fetch,
  timeout handling, response validation, and retry-safe duplicate handling.
- Verify consent withdrawal/version changes block subsequent signal capture.
