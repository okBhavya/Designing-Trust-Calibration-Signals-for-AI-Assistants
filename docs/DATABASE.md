# CalibrAI database schema

Production uses PostgreSQL through Supabase. The initial Alembic migration
creates:

- `participants`: consent status, consent version, and assigned condition.
- `trials`: participant experiment units with a unique participant/trial key.
- `signal_events`: signal interaction telemetry.
- `questionnaires`: versioned research instrument responses.
- `live_signals`: provider-neutral answer hash and versioned signal response.

Participant foreign keys use `ON DELETE CASCADE` for participant-owned records;
trial references on events use `ON DELETE SET NULL`. `live_signals` has a unique
participant/answer-hash constraint to prevent duplicate persisted signals.
Indexes cover participant event timelines and platform signal timelines.

PostgreSQL row-level security is enabled by the migration. Policies expect the
server-side request transaction to set `app.participant_id`; the browser never
sets this value and Supabase service-role credentials must remain server-side.
The SQLite database used by tests is only an isolated test substitute and does
not emulate PostgreSQL RLS.
