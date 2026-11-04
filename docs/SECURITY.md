# CalibrAI API security and privacy

## Current controls

- Pydantic rejects unknown fields, unsupported platforms, malformed UUIDs, and
  non-SHA-256 answer hashes.
- Signal capture requires a participant record with the configured consent
  version and `granted` status.
- Request bodies are bounded by `CALIBRAI_MAX_REQUEST_BYTES`.
- An in-memory IP limiter protects the development API. Production deployment
  must use a shared limiter at the gateway or Redis-backed service.
- CORS is allowlisted through `CALIBRAI_API_ORIGINS`; no wildcard is used.
- Prompts and answers are not logged.
- Participant deletion cascades to participant-owned records.
- PostgreSQL RLS is enabled in the initial migration.
- Protected routes require short-lived HMAC-SHA256 session tokens with the
  intended audience, expiry, participant subject, and revocable JTI.

## Authentication boundary

A participant UUID is an identifier only. It is not authentication and must
not be treated as proof of identity. Session issuance currently uses a
server-only enrollment secret for controlled development/study setup; that
secret is never shipped to the extension. The extension stores only the
short-lived issued token and sends it through the background worker. Before
public distribution, replace bootstrap enrollment with authenticated study
enrollment, validate extension identity, bind authorization to that identity,
and put rate limiting at the edge. Supabase service-role credentials and
database URLs belong only in the backend environment.

## Retention

Raw prompt/answer fields are accepted only for consent-authorized signal
processing and should be disabled or minimized when the production provider no
longer requires them. The current schema supports deletion by participant; a
production retention job and explicit study retention schedule are still
required.
