# Architecture Decisions

## ADR-001: WXT + Vite + React + TypeScript

WXT provides a maintained Manifest V3 entrypoint model and browser-extension
development workflow while Vite supplies fast TypeScript/React bundling. React
is used only for isolated extension surfaces and the Shadow DOM overlay.

## ADR-002: FastAPI for the future API

FastAPI is selected over Cloudflare Workers + Hono because the project already
requires Python, pandas, scikit-learn, matplotlib, and statsmodels for research
analysis. A typed Python API keeps validation and future signal/analysis
prototypes close while preserving a simple HTTPS boundary for the extension.
This API is intentionally not implemented in the first milestone.

## ADR-003: Adapter boundary before multi-site support

Site-specific selectors are kept behind `SiteAdapter`. ChatGPT, Claude, and
Gemini each have independent implementations; shared capture, signal, and
overlay code only consumes the normalized contract.

## ADR-004: Shadow DOM overlay

The signal is rendered in a dedicated Shadow DOM host below the answer. This
prevents CSS collisions and ensures the extension never edits, replaces, or
deletes the original answer.

## ADR-005: No raw answer persistence

The first milestone stores no conversation text. Answer hashes are deterministic
and suitable for future cache keys. Any future transmission requires explicit
consent and must be routed through the service worker.

## ADR-006: Mock provider is explicit

The initial provider returns deterministic mock signals and is named as such in
code and UI. It is not presented as a production reliability assessment.
