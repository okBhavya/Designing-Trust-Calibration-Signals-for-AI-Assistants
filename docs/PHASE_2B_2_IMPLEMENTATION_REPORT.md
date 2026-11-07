# CalibrAI Phase 2B.2 Implementation Report

Date: 2026-11-07

## Status

Implemented the first evidence-grounded reliability pipeline behind an explicit
server-side feature flag. The deterministic mock provider remains available
and is still the default. This phase does **not** establish scientific
validity, calibrated factual reliability, or real-provider performance.

## Implemented

- Added immutable annotation audit-trail fields to the finalized validation
  protocol. Original reviewer annotations are separate from adjudicated
  records and are never overwritten.
- Added server configuration:
  - `CALIBRAI_SIGNAL_PROVIDER=mock` (default)
  - `CALIBRAI_SIGNAL_PROVIDER=reliability_fixture`
  - optional `CALIBRAI_EVIDENCE_FIXTURE_PATH`
  - `CALIBRAI_STORE_RAW_CONVERSATION=false` (default)
- Added deterministic answer normalization:
  whitespace normalization, list-marker handling, sentence indices, headings,
  quoted/structural text exclusion, and code-fence exclusion.
- Added structured claim extraction capped at eight claims per answer.
  Claims include stable IDs, source sentence index, type, materiality, and
  time-sensitivity.
- Added fixture-backed evidence retrieval with URL validation, explicit source
  metadata, configured evidence only, and duplicate URL/source handling.
- Added evidence-grounded claim verification with `supported`,
  `contradicted`, and `insufficient_evidence`.
- Added deterministic aggregation using the finalized materiality weights:
  high=3, medium=2, low=1. The denominator includes all externally verifiable
  claims; insufficient evidence contributes zero rather than disappearing.
  Opinions and non-claims are excluded.
- Added distinct externally represented states:
  `high`, `medium`, `low`, `insufficient_evidence`, `unavailable`, and
  `abstained`.
- Non-judgment states use `confidence: null`; they are not encoded as Low.
- Extended sentence flags and claim assessments with claim IDs, uncertainty,
  evidence strength, and source IDs while preserving existing fields.
- Disabled raw prompt/answer persistence by default. The existing database
  columns remain for compatibility, but are populated only when the explicit
  `CALIBRAI_STORE_RAW_CONVERSATION=true` setting is enabled.
- Updated the overlay to show distinct real-engine non-judgment states while
  preserving the existing mock signal presentation.
- No platform adapter changes were required.

## Unit tested

`apps/api/tests/test_provider.py` covers:

- mock-provider compatibility;
- sentence-index preservation and claim extraction;
- insufficient-evidence denominator behavior;
- unavailable input behavior.

## Integration tested

`apps/api/tests/test_integration.py` covers:

- feature-flag selection of the reliability fixture provider;
- insufficient-evidence response state;
- default non-persistence of raw prompt/answer fields;
- existing authenticated consent, duplicate, deletion, and session behavior.

## Commands and actual results

Backend focused tests:

```powershell
$env:PYTHONPATH = 'apps\api'
python -m pytest apps\api\tests\test_provider.py -q
```

Result: `5 passed, 2 warnings`.

Backend integration tests:

```powershell
$env:PYTHONPATH = 'apps\api'
python -m pytest apps\api\tests\test_integration.py -q
```

Result: `3 passed, 2 warnings`.

Complete backend suite:

```powershell
$env:PYTHONPATH = 'apps\api'
python -m pytest apps\api\tests -q
```

Result: `20 passed, 2 warnings`.

Extension tests:

```powershell
corepack pnpm test
```

Result: `5 test files passed; 19 tests passed`.

Type checking:

```powershell
corepack pnpm typecheck
```

Result: passed.

Production build:

```powershell
corepack pnpm build
```

Result: WXT production build passed; output written to `.output\chrome-mv3`.

Warnings were existing upstream/deprecation warnings from the test tooling.

## Database migration details

No migration was required in this phase. `LiveSignal` already has nullable
`prompt` and `answer` columns, so the privacy change is enforced by runtime
configuration without changing the existing schema or deletion cascade.

Before any real participant-facing provider is enabled, a follow-up migration
should remove, encrypt, or separately retain these columns according to the
approved study retention protocol. The current opt-in raw-storage switch is
for controlled development only.

## Provider configuration

The only implemented non-mock provider is
`ReliabilityFixtureProvider`. It reads explicitly configured JSON fixture
records and never fabricates citations or performs live web/model calls. A
record may include `sourceId`, `url`, `title`, `publisher`, `domain`,
`retrievedAt`, `publishedAt`, `snippet`, `relevanceScore`, `quality`, and
`independenceGroup`.

No API keys were added. No live search, source-fetch, or language-model
provider was tested.

## Mocked or simulated

- Evidence retrieval is fixture-backed.
- Source quality, relevance, contradiction, and independence are represented
  by fixture metadata.
- Claim extraction is deterministic heuristic extraction.
- Verification is deterministic over fixture metadata.
- Cost tracking is not yet a provider billing integration; latency remains in
  `processingLatencyMs`.

## Real-provider tested

None. No live external AI or search provider was enabled or called.

## Not tested

- Live web retrieval, robots/access failures, dynamic pages, or source content
  fetching.
- Real model claim extraction or verification.
- Provider pricing, quotas, regional data handling, or production latency.
- Scientific annotation quality, held-out accuracy, calibration, ECE, Brier
  score, reliability diagrams, or risk-coverage curves.
- PostgreSQL RLS behavior in a live deployment.
- Chrome end-to-end rendering of all six assessment states against live
  provider conversations.

## Blocked

Real-provider evaluation is blocked until provider selection, current
contracts/retention terms, evidence-domain policy, source-fetch policy, and
the manually adjudicated dataset are approved. Enabling a live provider
without those controls would violate the finalized validation protocol.

## Deferred to Phase 2C

- Independent annotation and adjudication collection.
- Development/calibration/held-out test evaluation.
- Probability calibration and threshold selection.
- Evidence retrieval recall/precision measurement.
- Claim verification accuracy and explanation-faithfulness measurement.
- Risk-coverage evaluation and scientific release decision.

## Remaining Phase 2B.2 work

1. Add a real retrieval port implementation only after provider approval.
2. Add controlled source fetching, content sanitization, and independence
   grouping from provider metadata.
3. Add a real verifier behind the same interface, with timeout and quota
   failure states.
4. Add operational request/cost counters without raw-content logging.
5. Add asynchronous continuation for workloads that cannot meet the existing
   eight-second extension timeout.
6. Add a schema migration or encrypted retention store before participant
   traffic requiring raw evidence processing.

The project must not claim factual reliability measurement until Phase 2C
completes independent annotation, held-out testing, calibration diagnostics,
and risk-coverage evaluation.
