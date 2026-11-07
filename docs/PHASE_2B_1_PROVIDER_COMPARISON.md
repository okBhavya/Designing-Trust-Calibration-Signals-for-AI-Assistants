# CalibrAI Phase 2B.1: Provider Comparison

This comparison is an architecture decision aid, not a claim that any provider
is factually reliable. Prices, quotas, model names, and terms change; Phase
2B.2 must record the date and region of any selected provider contract instead
of copying unverified values into code.

## Selection criteria

The engine needs independent evidence, structured outputs, source provenance,
bounded latency, privacy controls, and repeatable evaluation. Popularity alone
is not a selection criterion. The primary requirements are:

1. Evidence quality and retrievability.
2. Stable URL/title/publisher/timestamp metadata.
3. Separation between retrieval and verification.
4. Server-side secrets, regional/data-retention controls, and deletion support.
5. Batch and timeout controls compatible with an eight-second extension budget.
6. Testability with deterministic fakes and replayable evidence bundles.
7. Cost observability per claim and answer.

## Provider classes

| Class | Strengths | Risks/trade-offs | Recommended role |
|---|---|---|---|
| General LLM API | Strong extraction, classification, and explanation; structured output support | Can hallucinate, over-trust supplied text, vary by model/version, and add latency/cost | Claim extraction and verification only, never sole evidence |
| Search API | Broad discovery and current web coverage | Search snippets are not proof; ranking and quotas vary; provenance can be shallow | Candidate discovery, followed by source fetch |
| Direct source fetcher | Full source text and stable URL metadata | Robots/access failures, dynamic pages, copyright/retention concerns | Evidence acquisition with bounded, policy-controlled fetches |
| Curated/primary-source API | High authority and reproducibility for a domain | Narrow coverage and integration effort | Preferred source for supported domains |
| Local deterministic rules | Cheap, fast, reproducible, transparent | Limited semantic coverage and poor handling of nuanced claims | Normalization, deduplication, safety gates, test doubles |
| Self-hosted model | Data-control and predictable deployment boundary | Operations, quality, hardware, and update burden | Optional later verifier after benchmark evidence |

## Recommended composition

Use a composition rather than a single vendor:

- deterministic normalizer and policy layer;
- a replaceable claim extractor;
- one or more search/discovery adapters;
- a source fetcher that emits provenance and untrusted text;
- a replaceable verifier that sees only the claim and evidence bundle;
- a deterministic aggregator with versioned thresholds.

This explicitly prevents model agreement from being mistaken for evidence.
The extractor and verifier may initially use the same model family for
operational simplicity, but the validation design must measure whether that
creates correlated errors. Independent retrieval sources should not be selected
from the verifier's own unsupported knowledge.

## Decision matrix

Score each candidate from 1 (poor) to 5 (strong) during Phase 2B.2 using
current vendor documentation and a fixed pilot workload. These are criteria,
not pre-filled benchmark results:

| Criterion | Weight | Evidence required |
|---|---:|---|
| Provenance completeness | 5 | URL, title, publisher, retrieval/publication dates |
| Authority and independence | 5 | Domain policy and duplicate-source audit |
| Retrieval freshness | 4 | Time-sensitive claim test set |
| Structured output reliability | 3 | Schema-conformance replay tests |
| Latency and timeout behavior | 4 | p50/p95 under fixed concurrency |
| Cost observability | 3 | Per-answer token/request accounting |
| Privacy and retention controls | 5 | Contract/configuration review |
| Failure and quota behavior | 4 | Forced timeout, 429, empty, and blocked-source tests |
| Replaceability | 4 | Port implementation with no adapter changes |

No candidate should be selected until it passes provenance, privacy, and
failure-behavior gates, even if its aggregate score is high.

## Fallback behavior

Fallbacks must preserve semantics:

- Search provider failure: try a configured independent provider only within
  the budget; otherwise return insufficient evidence.
- Source fetch failure: retain the URL and failure status, but do not cite the
  snippet as conclusive.
- Verifier timeout: mark affected claims insufficient and cap the overall
  label.
- Model quota or schema failure: use a deterministic safe error/degraded path,
  never a success-shaped High result.
- Provider version change: create a new component version and rerun validation
  before using it for study data.

## Cost and latency accounting

The server should emit counters, not secrets: provider name/version,
retrieval calls, fetch calls, verification calls, input/output token counts
when available, elapsed milliseconds, cache hits, and failure category. Do not
log raw answer text, prompts, retrieved bodies, or provider payloads.

The eight-second extension timeout makes a full eight-claim fan-out unsafe as a
single unbounded request. Prefer one batched extractor, bounded parallel
retrieval, one verifier batch, and an asynchronous continuation when the
budget is exceeded.

## Recommendation

For Phase 2B.2, implement ports and deterministic fakes first, then pilot one
search/discovery adapter plus a controlled source fetcher and one structured
LLM adapter. Select the concrete vendors only after current terms, data
retention, rate limits, and a labelled pilot have been reviewed. Keep
`MockSignalProvider` as the default/test provider and make the real provider an
explicit server-side configuration choice.
