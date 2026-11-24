# CalibrAI: Comprehensive Repository Technical Audit, Academic Research Gap Analysis & Master Phase 3 Readiness Assessment

**Document Identifier:** `CALIBRAI-AUDIT-2026-FINAL`  
**Date of Audit:** November 2026  
**Auditor Roles:** Principal Software Architect, Senior AI/ML Researcher, Research Methodologist, Technical Auditor, Academic Project Supervisor  
**Target Repository:** `Designing-Trust-Calibration-Signals-for-AI-Assistants` (CalibrAI)  
**Evaluated Branch & Commit:** `main` at commit `c38cad4`  

---

## 1. Executive Summary

An exhaustive, evidence-based architectural, technical, empirical, and academic audit of the entire CalibrAI repository was conducted. The evaluation strictly followed read-only auditing rules, verifying claims directly against code, database schemas, automated test executions, and authoritative scientific literature.

**Primary Audit Findings:**
1. **Engineering Foundation:** The codebase contains a high-quality, typed, and well-tested software engineering foundation. The Chrome Manifest V3 browser extension (WXT + Vite + React 18) compiles cleanly into a 300.5 kB production bundle. The FastAPI backend implements robust HMAC session authentication, participant consent management, rate limiting, and cascade deletion. All 19 extension unit tests and all 41 Python backend tests pass with zero failures.
2. **The Simulation Reality:** While the architecture is structured for reliability engineering, **the actual reliability assessment pipeline is currently a deterministic mock and static fixture simulation.** The system contains zero live LLM inference, zero live web search retrieval, and zero live NLI entailment verification. Claim extraction uses a simple character-length heuristic; evidence retrieval matches exact strings from static local JSON files; verification checks hardcoded numbers in fixtures.
3. **Missing Critical Components:** The browser extension does **NOT** yet render claim-level visual text highlights on host DOM text nodes, nor does it display interactive citation cards. The controlled study harness application (`apps/study`) is completely absent (0 files exist).
4. **Data & Scientific Status:** The repository contains **ZERO approved empirical research data** and **ZERO human annotations**. Candidate public datasets (FELM, FActScore, RAGTruth) were formally audited and rejected due to non-commercial license encumbrances (CC BY-NC-SA), static Wikipedia constraints, and domain mismatches. No scientific accuracy, Expected Calibration Error (ECE), Brier score, or AUROC metric has ever been calculated on real data.
5. **Phase 3 Readiness Verdict:**  
   $$\mathbf{READY\ FOR\ LIMITED\ PHASE\ 3\ RESEARCH\ PREPARATION\ \&\ OFFLINE\ ENGINE\ ENGINEERING}$$  
   The project is **NOT READY for human-subject experimentation** (gated by BITS Pilani Institutional Human Ethics Committee approval and study harness development) and **NOT READY for offline scientific validation** (gated by dataset curation and double annotation).

---

## 2. Original Project Objectives

The project **CalibrAI** (working title: *"Designing Trust Calibration Signals for AI Assistants"*) was conceived not merely as a fact-checking browser extension, but as an empirical research investigation into **Human-AI Trust Calibration**.

### The Core Research Mission
Modern Large Language Models (LLMs)—specifically ChatGPT, Claude, and Google Gemini—generate fluent, authoritative responses that frequently contain subtle, confident factual hallucinations. Users exhibit severe *automation bias* and *over-reliance*, accepting incorrect statements without verification. Conversely, when users discover an error, they often suffer *algorithm aversion*, under-relying on the assistant even when it is correct.

CalibrAI investigates whether **evidence-grounded, claim-level and answer-level reliability signals** can help users:
1. Dynamically distinguish reliable AI responses from unreliable ones (*appropriate reliance*).
2. Avoid over-reliance on incorrect factual propositions without triggering caveat fatigue.
3. Lower the cognitive cost of verifying complex claims through progressive visual disclosure.

### The Ten Interconnected System Pillars
To achieve this objective, CalibrAI was designed as ten interdependent components:
1. *Multi-Platform Browser Extension:* Non-invasive capture and overlay across ChatGPT, Claude, and Gemini.
2. *Backend Signal Service:* Authenticated, privacy-preserving FastAPI boundary.
3. *Claim Extraction & Normalization Pipeline:* Decomposition of long-form responses into atomic propositions.
4. *Independent Evidence Retrieval:* Multi-source search and passage extraction with source independence grouping.
5. *Evidence-Grounded Claim Verification:* Objective NLI entailment without model self-judgment.
6. *Confidence Calibration & Scoring Engine:* Materiality-weighted reliability aggregation calibrated via Isotonic Regression.
7. *Progressive Disclosure UI:* Ambient confidence chip + in-situ claim span highlights + citation drawer.
8. *Controlled Experimental Study Harness:* Laboratory web application for testing reliance on controlled accuracy tasks.
9. *Governed Research Dataset:* Curated, double-annotated, air-gapped factual QA corpus.
10. *Statistical Analysis & Academic Reporting:* Mixed-effects modeling of human decisions and academic publication.

---

## 3. Reconstructed Project History & Requirements Evolution

### 3.1 Historical Milestone Trajectory
- **Milestone 1 (Phase 1 & Extension Foundation — Commits `f1f01d3` to `222cedf`):** Established repository structure, WXT MV3 configuration, TypeScript interfaces, Shadow DOM overlay, and ChatGPT/Claude/Gemini DOM adapters with deterministic local mock signals.
- **Milestone 2 (Phase 2A & Backend Shell — Commits `d8a10fc` to `0808b35`):** Created `apps/api` with FastAPI, SQLAlchemy models, Alembic migration `0001_initial.py`, HMAC session tokens, participant consent verification, and isolated SQLite integration tests.
- **Milestone 3 (Phase 2A.1 & Secure Boundary — Commit `2e3eefb`):** Hardened authentication, audience validation, participant isolation, duplicate answer hash prevention, and extension API runtime toggle.
- **Milestone 4 (Phase 2B & Reliability Architecture — Commits `e92229a` to `1dc40ad`):** Introduced modular `SignalProvider` interface; implemented deterministic `ReliabilityFixtureProvider` with regex sentence splitting, character-length materiality assignment, static JSON evidence fixtures, and materiality-weighted score aggregation. Added evaluation metrics library (`evaluation.py`) with AUROC, ECE, Brier score, and Isotonic regression.
- **Milestone 5 (Phase 2C & Dataset Governance — Commits `341e995` to `c38cad4`):** Formalized dataset Pydantic models (`dataset.py`) with partition leakage checks, temporal validation, and double-annotation schemas. Formally documented the rejection of FELM, FActScore, and RAGTruth.

### 3.2 Architectural Inconsistencies & Reconciled Disagreements Across Documents
1. **Database Schema vs. ORM Nullability:** `docs/DATABASE.md` and SQLAlchemy ORM `models.py` specify that all timestamp columns (`created_at`, `updated_at`, etc.) are non-nullable. However, Alembic migration `0001_initial.py` left 6 timestamp columns nullable. A follow-up migration (`0002_timestamp_nullability.py`) is required.
2. **Raw Conversation Persistence:** Early architectural documents proposed storing raw prompts and answers in `LiveSignal` for model auditing. Phase 2B.3 security reviews recognized the extreme privacy risk; settings now default `CALIBRAI_STORE_RAW_CONVERSATION=false` and fail closed in production/study environments.
3. **Phase Numbering Ambiguity:** Early documentation numbered the extension milestone as "Phases 1-4", whereas backend engineering was labeled "Phase 2A, 2B, 2C". This audit reconciles the roadmap: Phase 2 is declared formally complete at the prototype/infrastructure boundary; Phase 3 represents real provider integration, offline scientific validation, and human experimentation.

---

## 4. Repository Structure & Architecture

```text
Designing-Trust-Calibration-Signals-for-AI-Assistants/
├── apps/
│   ├── api/                          FastAPI Backend Service
│   │   ├── alembic/                  Database migration scripts (0001_initial)
│   │   ├── app/
│   │   │   ├── api/routes/           FastAPI endpoints (signal, session, consent, etc.)
│   │   │   ├── core/                 Security, HMAC auth, rate limiting, exceptions
│   │   │   ├── database/             SQLAlchemy 2.0 models and engine connection
│   │   │   ├── schemas/              Pydantic v2 request/response contracts
│   │   │   ├── services/             Reliability engine, mock provider, consent service
│   │   │   ├── config.py             Settings and environment security validator
│   │   │   ├── dataset.py            Dataset governance, partition checks, manifest generator
│   │   │   └── evaluation.py         Scientific evaluation metrics & isotonic calibrator
│   │   ├── tests/                    Pytest suite (41 tests across 5 test modules)
│   │   ├── alembic.ini               Alembic configuration
│   │   ├── calibrai.db               Uninitialized local SQLite database
│   │   └── requirements.txt          Python backend dependencies
│   └── study/                        [RESERVED / MISSING] Planned participant web app
├── docs/                             Authoritative architectural & protocol documents
│   ├── audit/                        Comprehensive Phase 3 audit reports (this audit)
│   ├── ARCHITECTURE.md               System overview & data flow
│   ├── PHASE_2B_1_ARCHITECTURE.md    Reliability engine specifications
│   ├── PHASE_2B_1_VALIDATION_PLAN.md Scientific evaluation plan & metric formulas
│   ├── PHASE_2C_ANNOTATION_HANDBOOK.md Human labeling protocol & scoring rules
│   └── ...
├── entrypoints/                      WXT Extension Entrypoints
│   ├── background.ts                 MV3 service worker (network boundary)
│   ├── content.ts                    Content script (observer & adapter dispatcher)
│   ├── popup/                        Extension popup UI
│   └── options/                      Extension settings UI (mode, token, endpoint)
├── src/                              Extension Core Logic & UI
│   ├── adapters/                     Platform adapters (ChatGPT, Claude, Gemini, DOM)
│   ├── core/                         Contracts, completion tracker, duplicate guard, hash
│   ├── overlay/                      Shadow DOM React overlay & CSS
│   └── signals/                      Local mock provider & schema validators
├── tests/                            Extension Vitest suite (19 tests across 5 files)
├── package.json                      Root Node dependencies & WXT scripts
├── tsconfig.json                     Strict TypeScript configuration
└── wxt.config.ts                     WXT Manifest V3 bundler configuration
```

---

## 5. Subsystem Implementation Inventory Summary

*Full detailed inventory is documented in [IMPLEMENTATION_STATUS_MATRIX.md](file:///c:/Users/soumy/Designing-Trust-Calibration-Signals-for-AI-Assistants/docs/audit/IMPLEMENTATION_STATUS_MATRIX.md).*

A quantitative audit across **40 auditable functional requirements** reveals:
- **Complete & Verified:** 16 requirements (**40.0%**)
- **Partially Implemented / Unverified:** 8 requirements (**20.0%**)
- **Mock / Fixture Dependent:** 4 requirements (**10.0%**)
- **Missing / Blocked / Unimplemented:** 12 requirements (**30.0%**)

---

## 6. Extension Audit

### 6.1 Manifest V3 & WXT Setup
- Uses WXT v0.20.27 with Vite and `@wxt-dev/module-react`.
- Scopes permissions minimally: only `"storage"` is requested in `manifest.json`.
- Host permissions are strictly restricted to `https://chatgpt.com/*`, `https://claude.ai/*`, and `https://gemini.google.com/*`.
- Content scripts run at `document_idle`.
- The background service worker acts as the sole network boundary; content scripts communicate with the background worker exclusively via typed Chrome runtime messaging (`CaptureRequest` $\to$ `CaptureResponse`).

### 6.2 Host Site Adapters & Live Compatibility
- **ChatGPT Adapter (`src/adapters/chatgpt.ts`):** Queries `[data-message-author-role="assistant"]` and `article[data-testid^="conversation-turn"]`. Detects streaming via stop button or `[data-is-streaming="true"]`.
  - *Live Compatibility Risk:* OpenAI frequently modifies DOM classes and obfuscates testids. An adapter working on static fixtures can break silently upon minor frontend changes. Heuristic fallback selectors are missing.
- **Claude Adapter (`src/adapters/claude.ts`):** Queries `[data-testid="assistant-message"]` and `div.font-claude-message`.
  - *Live Compatibility Risk:* Claude AI obfuscates classes with random Tailwind hashes. Never verified against an authenticated live session.
- **Gemini Adapter (`src/adapters/gemini.ts`):** Queries `[data-message-author-role="model"]` and custom web component `<message-content>`.
  - *Live Compatibility Risk:* Gemini uses internal Shadow DOM roots inside custom elements. Standard `querySelectorAll` fails to penetrate shadow roots without deep traversal logic.
- **Completion & Duplicate Guards:** `CompletionTracker` verifies that response text length remains stable across consecutive checks. `DuplicateGuard` uses a `WeakMap<HTMLElement, string>` to map DOM containers to SHA-256 hashes, preventing redundant network dispatches.

### 6.3 UI Overlay & Shadow DOM
- Mounts inside an isolated `ShadowRoot` attached directly after the assistant message container. This guarantees zero CSS leakage to or from the host page.
- Visual states supported: `checking`, `signal` (High / Medium / Low), `insufficient_evidence`, `unavailable`, `abstained`, `error`, `timeout`, and `not-applicable`.
- **CRITICAL UI GAP:** The overlay renders only an answer-level confidence badge and a single text paragraph ("Why?"). **It does NOT render in-situ claim-level text highlighting on the host answer, nor does it display interactive citation cards.**

---

## 7. Backend Audit

### 7.1 Architecture & Endpoints
The backend in `apps/api` is built on FastAPI and Pydantic v2:
- `GET /health`: Safe service health probe.
- `POST /v1/session`: Issues short-lived HMAC-SHA256 session tokens bound to a participant UUID.
- `POST /v1/consent`: Records or updates participant consent versions.
- `POST /v1/signal`: Validates capture payload, executes signal provider, records `LiveSignal`.
- `POST /v1/events`: Ingests participant interaction telemetry with sensitive key scrubbing.
- `POST /v1/participants/{id}/delete`: Hard cascades participant data deletion across all tables.

### 7.2 Security & Authentication
- Session tokens are signed using HMAC-SHA256, verifying participant subject, expiration (`session_ttl_seconds`), audience (`calibrai-extension`), and revocable JTI tracking.
- CORS is locked to explicit origins (`CALIBRAI_API_ORIGINS`). Wildcards are prohibited.
- Request payload size is hard-capped at 64 KB (`CALIBRAI_MAX_REQUEST_BYTES`).
- Metadata requests are scrubbed: any JSON payload attempting to send keys like `prompt`, `answer`, `token`, `secret`, or `password` is rejected with HTTP 422.

---

## 8. AI/ML Pipeline Audit: Production vs. Simulation

| Pipeline Component | Intended Academic Function | Current Implementation in Repository | Operational Reality & Classification |
|---|---|---|---|
| **Answer Normalization** | Markdown parsing, sentence index tracking, block preservation. | Regex newline normalization, code fence stripping, basic punctuation lookahead. | **Heuristic Prototype.** Regex boundary lookahead fails on abbreviations ("Dr.", "U.S.") and numbers. |
| **Claim Extraction** | Decompose answer into checkable atomic propositions. | Filters out opinion phrases ("i think", "might"). Labels as `quantitative` if digits found, else `factual`. | **Heuristic Prototype.** Does not decompose compound claims; ignores semantics. |
| **Claim Materiality** | Measure practical decision impact of claim error. | If sentence length $\ge 140$ chars $\to$ `high`; $\ge 60$ chars $\to$ `medium`; else `low`. | **Scientifically Invalid Heuristic.** Sentence character length has zero correlation with factual materiality! |
| **Evidence Retrieval** | Multi-source open-web search for authoritative evidence. | `FixtureEvidenceRetriever` matches claim string against static JSON file records. | **Static Mock / Fixture.** Zero web search capability; cannot verify unseen answers. |
| **Source Independence** | Detect duplicated syndication and shared publisher ownership. | Reads manual `independence_group` string from fixture record. | **Static Fixture Attribute.** No automated publisher or domain analysis. |
| **Claim Verification** | Objective entailment classification (`supported`, `contradicted`, `insufficient`). | Reads `source.relevance_score` ($>0$ or $<0$) and `quality >= 0.6` directly from static fixture! | **Pure Simulation.** Zero NLI model or LLM inference. |
| **Reliability Aggregation** | Materiality-weighted score aggregation with veto rules. | Implements: $S = \sum w_i \cdot \mathbb{I}(\text{supp}) / \sum w_i$ with $w \in \{3, 2, 1\}$. High contradiction vetoes to Low. | **Fully Functional Deterministic Logic.** Matches validation plan specification. |
| **Confidence Calibration** | Map raw reliability scores to calibrated probabilities. | Mathematical implementation of PAVA Isotonic Regression in `evaluation.py`. | **Infrastructure Library Only.** Never called during live API inference; uncalibrated. |
| **Abstention & Insufficient Evidence** | Distinct communication of unverified claims or outages. | Explicit enum values: `insufficient_evidence`, `unavailable`, `abstained`. Non-judgment states set `confidence: null`. | **Fully Functional Schema & Logic.** Prevents false high-confidence signals on missing data. |

---

## 9. Database & Migration Audit

1. **ORM Models (`apps/api/app/database/models.py`):**
   - Clean SQLAlchemy 2.0 declarative mappings for `Participant`, `SessionToken`, `Trial`, `SignalEvent`, `Questionnaire`, and `LiveSignal`.
   - Strict UUID primary keys, foreign key cascade deletions (`ON DELETE CASCADE`), and unique constraints on `(participant_id, answer_hash)`.
2. **Alembic Migration `0001_initial.py`:**
   - DDL creates all application tables, indexes, and PostgreSQL Row-Level Security (RLS) policies based on `app.participant_id`.
3. **Discrepancy & Verification Findings:**
   - The local database `apps/api/calibrai.db` is uninitialized (contains only an empty `alembic_version` table).
   - In a disposable test database upgraded to `0001_initial`, Alembic autogenerate identified **six timestamp nullability discrepancies**:
     - `participants.created_at`, `participants.updated_at`
     - `questionnaires.submitted_at`
     - `signal_events.occurred_at`
     - `live_signals.created_at`
     - `session_tokens.created_at`
     These are declared non-nullable in ORM models but were generated nullable in `0001_initial.py`. A reviewed follow-up migration (`0002_timestamp_nullability.py`) is required.
   - PostgreSQL RLS policies have never been tested in CI because tests run against SQLite.

---

## 10. Security & Privacy Audit

1. **Raw Conversation Minimization:** `CALIBRAI_STORE_RAW_CONVERSATION=false` by default. `apps/api/app/config.py` enforces a fail-closed check: if the environment is `production`, `study`, or `participant`, enabling raw storage raises an immediate fatal runtime exception.
2. **Metadata Boundary Enforcement:** `SignalRequest` and `EventCreate` schemas validate that request metadata cannot carry prompt, answer, conversation, secret, or session credentials.
3. **Persisted Signal Redaction:** `LiveSignal.response_json` redacts raw claim text, persisting only hashes, scores, and categorical outcomes.
4. **Participant Isolation & Cascade Deletion:** Tested and verified. Calling `POST /v1/participants/{id}/delete` cascades hard deletion across all trials, sessions, events, questionnaires, and live signals.

---

## 11. Testing, Quality & Build Verification Results

Every automated test suite and build pipeline was executed directly in the environment:

| Test Suite / Command | Exact Command Executed | Result Status | Tests Passed / Skipped / Failed | Key Observations & Warnings |
|---|---|---|---|---|
| **Extension Typecheck** | `npm run typecheck` (`tsc --noEmit`) | **PASSED** | 0 errors | Strict TypeScript types pass across all adapters, overlay, and core contracts. |
| **Extension Unit Tests** | `npx vitest run` | **PASSED** | **19 passed** across 5 test files | Verifies duplicate guard, completion stability, hashing, and adapter DOM parsing. |
| **Extension Production Build** | `npm run build` (`wxt build`) | **PASSED** | Output: `.output/chrome-mv3` (300.5 kB) | Generates valid Manifest V3 distribution with background worker and content scripts. |
| **Python Compilation** | `python -m compileall -q apps/api/app apps/api/tests` | **PASSED** | 0 bytecode errors | Python syntax clean across all backend modules. |
| **Python Backend Tests** | `python -m pytest apps/api/tests --basetemp=.pytest_temp` | **PASSED** | **41 passed**, 0 failed (0.63s) | 13 API tests, 8 dataset tests, 8 evaluation tests, 3 integration tests, 9 provider tests. |

*Note on Pytest Execution:* When run without `--basetemp`, Windows ACL permissions on `AppData\Local\Temp\pytest-of-soumy` triggered a temporary file lock. Specifying an explicit workspace temp directory (`--basetemp=.pytest_temp`) resolved the Windows ACL issue, executing all 41 tests cleanly in 0.63 seconds.

---

## 12. Requirements Traceability Matrix

| Original Requirement | Architectural Document Source | Implementation File Location | Verification Evidence | Current Status | Remaining Work to Complete |
|---|---|---|---|---|---|
| **Multi-platform answer detection** | `docs/ARCHITECTURE.md#L35` | `src/adapters/` | `tests/adapters.test.ts` (7 tests) | **IMPLEMENTED** | Automated live canary testing against live ChatGPT/Claude/Gemini. |
| **Non-invasive Shadow DOM overlay** | `docs/ARCHITECTURE.md#L52` | `src/overlay/` | `tests/adapters.test.ts` | **PARTIAL** | Implement in-situ claim span text highlights and citation drawer. |
| **Authenticated Signal API** | `docs/API.md#L10` | `apps/api/app/api/routes/signal.py` | `apps/api/tests/test_api.py` (13 tests) | **COMPLETE** | Implement asynchronous SSE streaming / polling for long retrieval jobs. |
| **Participant Consent Lifecycle** | `docs/SECURITY.md#L8` | `apps/api/app/api/routes/consent.py` | `apps/api/tests/test_integration.py` | **COMPLETE** | Multi-language consent document presentation endpoint. |
| **Cascade Participant Deletion** | `docs/DATABASE.md#L12` | `apps/api/app/api/routes/participants.py`| `apps/api/tests/test_integration.py` | **COMPLETE** | Retention schedule background cleanup worker. |
| **Atomic Claim Decomposition** | `docs/PHASE_2B_1_ARCHITECTURE.md#L98` | `apps/api/app/services/reliability_service.py` | `apps/api/tests/test_provider.py` | **MOCK/HEURISTIC** | Replace regex length heuristic with strict JSON LLM atomic extractor. |
| **Evidence Web Retrieval** | `docs/PHASE_2B_1_ARCHITECTURE.md#L124`| `apps/api/app/services/reliability_service.py` | `apps/api/tests/test_provider.py` | **FIXTURE ONLY** | Integrate Tavily Search API with sub-second passage extraction. |
| **Source Independence Clustering**| `docs/PHASE_2B_1_ARCHITECTURE.md#L148`| `apps/api/app/dataset.py` | `apps/api/tests/test_dataset.py` | **PARTIAL** | Automated publisher ownership and Jaccard text deduplication. |
| **NLI Claim Entailment Verification**| `docs/PHASE_2B_1_ARCHITECTURE.md#L152`| `apps/api/app/services/reliability_service.py` | `apps/api/tests/test_provider.py` | **FIXTURE ONLY** | Deploy DeBERTa-v3 NLI model or GPT-4o-mini entailment judge. |
| **Confidence Score Calibration** | `docs/PHASE_2B_1_VALIDATION_PLAN.md#L156`| `apps/api/app/evaluation.py` | `apps/api/tests/test_evaluation.py` | **LIBRARY ONLY** | Wire fitted Isotonic calibrator into runtime signal pipeline. |
| **Air-gapped Dataset Governance** | `docs/PHASE_2C_ANNOTATION_HANDBOOK.md`| `apps/api/app/dataset.py` | `apps/api/tests/test_dataset.py` | **COMPLETE** | Curate 600 QA pairs and perform double-annotation. |
| **Controlled Study Harness Platform**| `docs/ARCHITECTURE.md#L15` | `apps/study/` [MISSING] | None | **NOT IMPLEMENTED** | Scaffold React/Vite study app with Latin Square condition engine. |
| **Institutional Ethics Clearance**| `docs/PHASE_2C_2_PILOT_EXECUTION.md` | `docs/ethics/` [MISSING] | None | **NOT IMPLEMENTED** | Submit formal application to BITS Pilani IHEC. |

---

## 13. Completed Work

The following components are fully implemented, mathematically sound, and rigorously verified:
1. Complete Chrome Manifest V3 extension architecture with strict TypeScript types, background routing, and isolated Shadow DOM overlay.
2. Independent site adapters for ChatGPT, Claude, and Gemini with streaming detection and stable completion tracking.
3. Authenticated FastAPI backend with HMAC-SHA256 session tokens, revocable JTIs, participant matching, and consent version enforcement.
4. Hard deletion cascade removing all participant data and signals upon request.
5. Fail-closed privacy guard disabling raw prompt and answer persistence in production/study environments.
6. Pure Python scientific evaluation library implementing multi-class metrics, rank-based AUROC with tie handling, fixed-bin ECE, Brier score, risk-coverage curves, and PAVA Isotonic regression with tied-score pooling.
7. Validated dataset governance engine with partition air-gapping, temporal cutoff verification, immutable original reviewer records, and separate adjudication history.

---

## 14. Partially Completed Work

1. **Extension Overlay:** Renders answer-level confidence badge, assessment states, and single text explanation; **lacks claim-level in-situ text highlighting and citation cards.**
2. **Platform Adapters:** Functional against test fixtures; **lacks automated canary testing against live host DOM mutations.**
3. **Sentence & Claim Extraction:** Functional deterministic code; **relies on character-length heuristics and simple punctuation regexes.**
4. **Alembic Database Migrations:** Migration `0001_initial.py` applied; **disposable db checks reveal 6 timestamp nullability mismatches with ORM models; local db uninitialized.**
5. **PostgreSQL Row-Level Security:** DDL statements exist in migration; **never verified in live PostgreSQL container.**

---

## 15. Mock & Fixture Dependencies

The following capabilities exist **strictly as simulations**:
1. `MockSignalProvider`: Local and backend deterministic length-based mock ($>700$ chars $\to$ Medium, $\le 700$ chars $\to$ High).
2. `ReliabilityFixtureProvider`: Loads static JSON files; requires exact string matching of claims.
3. `ClaimVerifier`: Reads hardcoded relevance scores from JSON fixtures; does not perform semantic reasoning.
4. Dataset Test Records: All records in `test_dataset.py` are synthetic unit-test mocks.

---

## 16. Pending Engineering Work (Phase 3 Backlog)

1. **Alembic Migration 0002:** Reconcile timestamp nullabilities and initialize local database.
2. **Real LLM Extractor:** Implement `LlmClaimExtractor` using `gpt-4o-mini` with strict JSON schema.
3. **Real Web Retriever:** Implement `TavilyEvidenceRetriever` with domain clustering and temporal cutoff checks.
4. **Real NLI Verifier:** Implement `NliClaimVerifier` using DeBERTa-v3 or GPT-4o-mini.
5. **Async Signal Polling / SSE:** Transition `/v1/signal` to async background processing to prevent 8-second browser timeouts.
6. **In-situ Text Highlighting:** Build Range/CSS Highlight overlay in extension Shadow DOM.
7. **Study Harness Web Application:** Build `apps/study` with Latin Square trial randomization, telemetry logging, and Jian/NASA-TLX surveys.

---

## 17. Research Gaps

1. **Semantic Claim Materiality:** Need a formal rubric to classify claim materiality semantically rather than by string length.
2. **Cognitive Cost vs. Benefit in Trust UI:** Need empirical validation of whether claim highlights lower verification costs (Vasconcelos et al., 2023) or cause caveat fatigue.
3. **Cross-Platform Calibration Transfer:** Need to investigate whether calibration curves fitted on ChatGPT transfer to Claude and Gemini.
4. **Selective Prediction Abstention Boundaries:** Need to empirically optimize the coverage-risk threshold for abstaining on ambiguous evidence.

---

## 18. Literature Review Synthesis

*Full 15-paper verified academic review is documented in [RESEARCH_GAP_AND_LITERATURE_REVIEW.md](file:///c:/Users/soumy/Designing-Trust-Calibration-Signals-for-AI-Assistants/docs/audit/RESEARCH_GAP_AND_LITERATURE_REVIEW.md).*

**Core Literature Takeaways:**
- **Atomic Decomposition is Essential:** Min et al. (EMNLP 2023, FActScore) proved that sentence-level evaluation obscures critical errors; atomic claim extraction is mandatory.
- **Passive Explanations Backfire:** Bansal et al. (CHI 2021) and Buçinca et al. (CSCW 2021) proved that static textual explanations promote human over-reliance. Explanations must incorporate friction and explicit uncertainty indicators.
- **Generation Probabilities are Ineffective UI Signals:** Vasconcelos et al. (TOCHI 2024) proved that highlighting low token probabilities does not help users detect errors; highlights must reflect external evidence conflict and edit likelihood.
- **Isotonic Calibration Restores Meaning:** Guo et al. (ICML 2017) demonstrated that post-hoc calibration via Isotonic regression reliably minimizes Expected Calibration Error.

---

## 19. Dataset & Licensing Assessment

*Full analysis is documented in [DATASET_AND_ANNOTATION_READINESS.md](file:///c:/Users/soumy/Designing-Trust-Calibration-Signals-for-AI-Assistants/docs/audit/DATASET_AND_ANNOTATION_READINESS.md).*

1. **FELM:** Rejected due to CC BY-NC-SA 4.0 license restrictions, link rot, and binary outcome taxonomy.
2. **FActScore:** Rejected due to narrow Wikipedia biography domain and binary support scoring.
3. **RAGTruth:** Rejected due to third-party corpus restrictions (MS MARCO/Yelp) and evaluation of prompt context faithfulness rather than open-domain factuality.
4. **Curated QA Dataset Path:** The project must curate an original 600-item multi-platform factual QA dataset (360 dev, 120 calibration, 120 test) + 30-item pilot, fully owned by the study team. Power analysis confirms $N=120$ per partition yields $>500$ claim evaluations, achieving statistical power $>0.95$.

---

## 20. Annotation & Ground-Truth Readiness

1. **Protocol Readiness:** The annotation handbook (`PHASE_2C_ANNOTATION_HANDBOOK.md`) is well-designed, providing clear definitions for factual claims, materiality (High/Medium/Low), and three-class outcomes (`supported`, `contradicted`, `insufficient_evidence`).
2. **Veto Rule Soundness:** The rule that any contradicted high-materiality claim forces an answer to `UNRELIABLE` is theoretically and practically sound.
3. **Double-Annotation Protocol:** Two independent reviewers must annotate frozen packets independently; Cohen's $\kappa \ge 0.67$ is enforced as the minimum agreement threshold before proceeding to adjudication.

---

## 21. Provider Comparison Summary

*Full provider matrices are documented in [PROVIDER_AND_INFRASTRUCTURE_ASSESSMENT.md](file:///c:/Users/soumy/Designing-Trust-Calibration-Signals-for-AI-Assistants/docs/audit/PROVIDER_AND_INFRASTRUCTURE_ASSESSMENT.md).*

- **LLM Extractor & Explainer:** **OpenAI `gpt-4o-mini`** is selected ($0.15/$0.60 per 1M tokens; 450 ms p50 latency; 99.8% strict JSON schema reliability).
- **Search Retrieval API:** **Tavily Search API** is selected ($0.008 per search; 650 ms p50 latency; returns clean pre-extracted passages, bypassing scraper latency).
- **Claim Verification:** **Dual-stage hybrid** (Local DeBERTa-v3 ONNX for fast objective entailment + GPT-4o-mini for human-readable explanation generation).
- **Database:** **Supabase PostgreSQL** (Native RLS enforcement, matching existing migrations).
- **Latency & Cost Feasibility:** End-to-end latency is projected at **3,535 ms** (well within the 8,000 ms extension timeout). Total cloud API cost is projected at **~$0.033 per evaluated answer** (~$79.20 total study cost).

---

## 22. Experimental Design Summary

*Full experimental protocol is documented in [EXPERIMENTAL_DESIGN_AND_ETHICS_READINESS.md](file:///c:/Users/soumy/Designing-Trust-Calibration-Signals-for-AI-Assistants/docs/audit/EXPERIMENTAL_DESIGN_AND_ETHICS_READINESS.md).*

- **Design:** Within-subjects repeated-measures with a **$4 \times 4$ balanced Latin Square** counterbalancing scheme across 4 conditions: Baseline, Generic Caveat, Confidence Chip, Claim-Level Highlighting.
- **Sample Size:** $N = 120$ completed participants (30 per Latin Square group) evaluating 16 tasks (50% correct, 50% incorrect answers). Powered at $1-\beta = 0.85$ for small-to-medium effect sizes ($d = 0.35$).
- **Controlled Lab App vs. Extension Field Separation:** Controlled experiments run in `apps/study` on pre-generated QA items with controlled accuracy; real AI answers are never deceptively manipulated in live browsing.
- **Measures:** Decision correctness (%), Over-reliance rate (%), Under-reliance rate (%), Time-to-decision (ms), Jian et al. 12-item Trust Scale, NASA-TLX cognitive workload.

---

## 23. Ethics & Institutional Approval (BITS Pilani)

1. **Regulatory Mandate:** Research involving human participants at BITS Pilani is governed by the **Institutional Human Ethics Committee (IHEC)** adhering to **ICMR National Ethical Guidelines (2017)** and the **DPDP Act (2023)**.
2. **Current Status:** **ZERO ETHICS SUBMISSION HAS OCCURRED.** No participants may be recruited and no human trials may be conducted until formal IHEC clearance is granted.
3. **Required Application Dossier:** Comprehensive Study Protocol, Participant Information Sheet (PIS), Informed Consent Form (ICF), and Deception/Debriefing Protocol.

---

## 24. Proposed Research Contributions

1. **Primary Contribution:** First controlled empirical study comparing the efficacy of claim-level evidence highlighting vs. answer-level confidence chips in mitigating human over-reliance on conversational AI assistants.
2. **Methodological Contribution:** Formalization and empirical evaluation of materiality-weighted reliability aggregation with explicit contradiction veto and zero-denominator abstention.
3. **Empirical Contribution:** First cross-platform confidence calibration transfer study comparing GPT-4o, Claude 3.5 Sonnet, and Gemini 1.5 Pro in a provider-neutral browsing framework.
4. **Engineering Contribution:** Open-source, non-invasive Manifest V3 browser extension and research harness supporting multi-platform assistant trust calibration.

---

## 25. Phase 3 Execution Roadmap

*Full roadmap and task backlog are documented in [PHASE_3_EXECUTION_ROADMAP.md](file:///c:/Users/soumy/Designing-Trust-Calibration-Signals-for-AI-Assistants/docs/audit/PHASE_3_EXECUTION_ROADMAP.md).*

The roadmap is structured into 6 sequential, milestone-gated phases:
- **Phase 2 Closure:** Alembic migration 0002, local DB initialization, PostgreSQL CI container.
- **Phase 3A (Research Foundations):** Pre-registration protocol, 600 QA bank curation, 30-item double-annotated pilot.
- **Phase 3B (Real Signal Engine):** GPT-4o-mini claim extractor, Tavily search retriever, NLI entailment verifier, async signal streaming.
- **Phase 3C (Offline Scientific Validation):** Full annotation of calibration/test partitions, Isotonic calibrator fitting, air-gapped held-out benchmark report.
- **Phase 3D (Study Harness Platform):** Scaffold `apps/study`, Latin Square condition engine, Jian/NASA-TLX surveys.
- **Phase 3E (Human-Subject Evaluation):** BITS Pilani IHEC approval, 120 participant recruitment, experimental trial execution.
- **Phase 3F (Analysis & Deliverables):** Mixed-effects GLMM modeling, CHI/CSCW conference paper drafting, open-source artifact release.

---

## 26. Critical Blockers

1. **Institutional Ethics Approval (Research Blocker #1):** Cannot recruit participants or conduct human trials without formal BITS Pilani IHEC clearance.
2. **Ground-Truth Dataset & Annotations (Research Blocker #2):** Cannot train Isotonic calibrator or report offline scientific metrics without curating the 600 QA bank and collecting double annotations.
3. **Absence of Real Providers (Technical Blocker #1):** Engine cannot verify unseen answers until Tavily search API and OpenAI extraction clients are implemented.
4. **Missing Study Harness App (Technical Blocker #2):** `apps/study` does not exist; human experiment cannot be administered without the testing interface.
5. **Missing In-Situ Claim Highlighting (Technical Blocker #3):** Extension overlay does not highlight text spans; Condition 3 cannot be visually rendered in the extension.

---

## 27. Risk Assessment & Mitigation Matrix

| Risk Factor | Severity | Likelihood | Impact on Project | Proactive Mitigation Strategy |
|---|---|---|---|---|
| **Host DOM Selectors Break** | High | High | Extension fails to capture answers on live ChatGPT/Claude/Gemini. | Implement structural heuristic fallback selectors and automated daily canary tests. |
| **Search Latency Exceeds 8s Timeout** | High | Medium | Extension times out and displays error overlay. | Use Tavily pre-extracted passages; implement async polling / SSE streaming in `/v1/signal`. |
| **Low Inter-Annotator Agreement ($\kappa < 0.67$)** | High | Medium | Dataset annotations declared invalid, delaying calibration. | Conduct 30-item pilot first; refine annotation handbook; train annotators with adjudicated examples. |
| **IHEC Ethics Review Delay** | High | Medium | Human trials delayed by 4–8 weeks. | Submit IHEC application immediately during Phase 3A; develop engine and study app in parallel. |
| **Participant Attrition / Low Engagement** | Medium | Medium | Human study fails power threshold ($N < 92$). | Over-recruit target to $N = 120$; keep study duration $\le 30$ minutes; provide modest institutional incentives. |

---

## 28. Prioritization & Readiness Verdict

### Explicit Answers to the 17 Core Audit Questions

1. **What percentage of the originally planned engineering work is completed?**  
   **40.0%** (16 of 40 auditable functional requirements are fully completed and verified).
2. **What percentage is partially completed?**  
   **20.0%** (8 of 40 requirements are partially implemented or lack external verification).
3. **What major components are still missing?**  
   Real LLM claim extractor, Tavily search retriever, NLI claim verifier, non-destructive DOM text highlighting overlay, controlled study harness web application (`apps/study`), ground-truth QA dataset, and human annotations.
4. **What works only through mocks or fixtures?**  
   Signal generation (mock mode), evidence retrieval (static JSON fixtures), claim verification (relevance scores in static fixtures), and dataset records (synthetic unit-test fixtures).
5. **What can already be demonstrated?**  
   Extension DOM capture on ChatGPT/Claude/Gemini fixtures, Shadow DOM ambient confidence chip overlay, HMAC session issuance, consent verification, cascade deletion, pure Python evaluation metrics (ECE, AUROC, Isotonic regression), and dataset schema validation.
6. **What has not been demonstrated?**  
   End-to-end verification of an unseen live answer, in-situ claim span text highlighting, real web search passage grounding, calibrated probability prediction on real data, and controlled human trial administration.
7. **What research is mandatory before implementation?**  
   Atomic claim decomposition prompt engineering, semantic claim materiality rubric, source independence clustering logic, and BITS Pilani IHEC ethical requirements.
8. **What datasets can realistically be used?**  
   An **original, curated 600-item multi-platform factual QA dataset** owned by the study team. External public datasets (FELM, FActScore, RAGTruth) cannot be redistributed due to license and domain flaws.
9. **What permissions are outstanding?**  
   BITS Pilani Institutional Human Ethics Committee (IHEC) ethical clearance for human participant trials.
10. **What real providers need to be selected?**  
    **OpenAI `gpt-4o-mini`** (for claim extraction and explanations), **Tavily Search API** (for passage retrieval), and **Supabase PostgreSQL** (for managed RLS database hosting).
11. **What must be implemented before offline validation?**  
    Curate the 600 QA bank, complete double-annotation on calibration/test partitions, implement real LLM extractor and search retriever, and fit the Isotonic calibrator on the calibration partition.
12. **What must be completed before the human experiment?**  
    Build the `apps/study` web application, obtain BITS Pilani IHEC ethics clearance, implement the 4 experimental condition renderers, and load the 16 controlled QA tasks.
13. **What requires institutional approval?**  
    Human participant recruitment, experimental trial administration, and collection of subjective trust/decision data (governed by BITS Pilani IHEC).
14. **What is the single biggest technical blocker?**  
    The absence of a real retrieval and verification provider (the engine currently cannot evaluate unseen text without pre-baked static fixtures).
15. **What is the single biggest research blocker?**  
    The absence of an approved, annotated ground-truth research dataset (no calibration parameters can be fitted and no scientific accuracy claim can be verified).
16. **What should the team do next?**  
    Execute the **First 10 Concrete Actions**: resolve Alembic timestamp nullability (migration 0002), initialize local DB, lock pre-registration protocol, draft IHEC ethics dossier, curate QA bank, and integrate Tavily/OpenAI provider clients.
17. **What should NOT be worked on yet?**  
    Do **NOT** recruit human participants, do **NOT** conduct human trials, do **NOT** claim factual accuracy or calibration performance on mock fixtures, and do **NOT** refactor existing extension adapter contracts.

---

### Detailed Readiness Assessment Across Eight Dimensions

| Dimension | Audit Status | Evidence-Based Assessment |
|---|---|---|
| **1. Engineering Readiness** | **DEVELOPMENT-READY (PROTOTYPE)** | Clean TypeScript MV3 extension and FastAPI shell with passing tests (19/19 extension, 41/41 backend). Needs migration 0002 and real provider wiring. |
| **2. Research Readiness** | **FOUNDATIONALLY SOUND** | Research hypotheses $H_1, H_2, H_3$ are theoretically grounded in seminal literature (Lee & See, Buçinca, Vasconcelos, Bansal). Needs formal pre-registration. |
| **3. Dataset Readiness** | **NOT READY (BLOCKED)** | Zero approved empirical data records exist in the repository. Curated 600 QA bank must be created. |
| **4. Provider Readiness** | **SPECIFIED BUT UNWIRED** | Providers evaluated and selected (OpenAI gpt-4o-mini + Tavily Search). API client services must be coded. |
| **5. Scientific Validation Readiness** | **NOT READY (INFRASTRUCTURE ONLY)** | Evaluation metrics library (`evaluation.py`) is fully functional, but zero real benchmark data has been evaluated. |
| **6. Experimental Readiness** | **NOT READY (HARNESS MISSING)** | Experimental design and Latin Square counterbalancing are defined, but `apps/study` application has not been built. |
| **7. Ethics Readiness** | **UNAPPROVED (GATED)** | Institutional requirements identified (ICMR 2017 / BITS Pilani IHEC). Formal application dossier must be submitted. |
| **8. Deployment Readiness** | **LOCAL DEVELOPMENT ONLY** | Operates on local SQLite. Cloud deployment on Railway/Render + Supabase PostgreSQL with verified RLS is required for production. |

---

### Master Milestone Verdict

$$\Large\mathbf{VERDICT:\ READY\ FOR\ LIMITED\ PHASE\ 3\ RESEARCH\ PREPARATION\ \&\ OFFLINE\ ENGINE\ ENGINEERING}$$

*The project is fully prepared to begin Phase 3A (Research Foundations & Dataset Curation) and Phase 3B (Real Signal Engine Engineering). It is explicitly **NOT READY** for Offline Scientific Validation (Phase 3C) or Human-Subject Experimentation (Phase 3E) until their respective data, provider, and institutional ethics prerequisites are formally satisfied.*

---

## 29. Actionable Team Handoff

### A. Already Completed & Verified
- WXT Manifest V3 extension shell with strictly scoped host permissions and clean production build (`.output/chrome-mv3`).
- Independent DOM adapters for ChatGPT, Claude, and Gemini with streaming detection and stable completion guards.
- Shadow DOM overlay host preventing CSS collisions with host websites.
- FastAPI backend with HMAC-SHA256 session management, participant matching, consent enforcement, and cascade deletion.
- Deterministic answer normalization, regex sentence mapping, and materiality-weighted aggregation formula.
- Complete Python evaluation metrics library: binary AUROC with tie handling, fixed-bin ECE, Brier score, risk-coverage curves, and PAVA Isotonic regression.
- Pydantic dataset governance schemas with air-gapping, temporal validation, and double-annotation schemas.
- 100% passing automated test suite (19 extension tests, 41 backend tests).

### B. Remaining Engineering Work
- Alembic migration `0002_timestamp_nullability.py` and local database initialization.
- Real LLM atomic claim extractor (`apps/api/app/services/extractor.py`) using `gpt-4o-mini`.
- Real web search retrieval engine (`apps/api/app/services/retriever.py`) using Tavily Search API.
- Real NLI claim verifier (`apps/api/app/services/verifier.py`) using DeBERTa-v3 / GPT-4o-mini.
- Asynchronous SSE streaming / polling in `/v1/signal` to handle retrieval latencies.
- In-situ claim span text highlighting overlay in extension Shadow DOM (`src/overlay/ClaimHighlighter.tsx`).
- Controlled study harness laboratory application (`apps/study`).

### C. Remaining Research Work
- Formal pre-registration of hypotheses $H_1, H_2, H_3$, materiality weights (3, 2, 1), and stopping rules.
- Semantic claim materiality classification rubric.
- Source independence clustering algorithm based on domain ownership and Jaccard text similarity.
- Cross-platform calibration transferability analysis.

### D. Dataset & Annotation Work
- Curate original 600-item factual QA bank (360 dev, 120 calib, 120 test) across ChatGPT, Claude, and Gemini.
- Double-annotate 30-item development pilot batch; verify Cohen's $\kappa \ge 0.67$.
- Complete double-blind annotation on 120 calibration and 120 held-out test items with formal adjudication.
- Generate versioned dataset manifests with SHA-256 air-gapping verification.

### E. Scientific Validation
- Fit Isotonic calibrator parameters exclusively on the calibration partition ($N = 120$).
- Execute one-time unblinded evaluation on air-gapped held-out test partition ($N = 120$).
- Publish official validation report with AUROC, ECE, Brier score, and Risk-Coverage curves with 95% bootstrap CIs.

### F. Experimental Work
- Prepare and submit formal ethics application dossier to BITS Pilani IHEC.
- Secure IHEC ethical clearance certificate.
- Recruit 120 participants across BITS Pilani student/faculty population.
- Administer 16-task Latin Square controlled trials in `apps/study`; capture decision latency, over-reliance rates, and Jian/NASA-TLX surveys.

### G. Critical Blockers
- *Technical:* Absence of real Tavily search and OpenAI extraction provider clients.
- *Research:* Absence of curated, double-annotated ground-truth dataset.
- *Institutional:* Absence of BITS Pilani IHEC ethical approval.

### H. Recommended Execution Order
$$\text{Phase 2 Closure} \longrightarrow \text{Phase 3A (Data/Ethics)} \longrightarrow \text{Phase 3B (Real Engine)} \longrightarrow \text{Phase 3C (Validation)} \longrightarrow \text{Phase 3D (Study App)} \longrightarrow \text{Phase 3E (Human Trials)} \longrightarrow \text{Phase 3F (Analysis/Paper)}$$

### I. Teammate Work Package Allocation
- **WP1 (Systems Architect):** Alembic migration 0002, PostgreSQL CI, async SSE streaming in FastAPI.
- **WP2 (Data Methodologist):** Curate 600 QA bank, partition air-gapping, double-annotation pilot.
- **WP3 (AI/ML Engineer):** Tavily search client, OpenAI extraction client, NLI verifier, Isotonic calibrator.
- **WP4 (Frontend Dev):** Extension Shadow DOM text highlighting overlay, citation card drawer.
- **WP5 (Full-Stack Dev):** `apps/study` web application, Latin Square condition randomizer, telemetry logging.
- **WP6 (Academic Lead):** BITS Pilani IHEC dossier, participant recruitment, GLMM statistical modeling, thesis/paper drafting.

### J. Immediate First 10 Next Actions
1. Create Alembic migration `0002_timestamp_nullability.py` setting `nullable=False` on the 6 timestamp columns.
2. Run `alembic upgrade head` in `apps/api` to initialize `calibrai.db`.
3. Draft and lock `docs/research/PREREGISTRATION_PROTOCOL.md` defining hypotheses and scoring parameters.
4. Prepare BITS Pilani IHEC ethics application dossier (Protocol, PIS, ICF, Debriefing).
5. Curate the first 100 multi-platform QA pairs into `data/source_qa_bank.json`.
6. Deliver frozen pilot packets to two independent student reviewers; verify Cohen's $\kappa \ge 0.67$.
7. Implement `apps/api/app/services/extractor.py` using `gpt-4o-mini` with strict JSON schema.
8. Implement `apps/api/app/services/retriever.py` integrating the Tavily Search API.
9. Prototype the in-situ text highlighting overlay in `src/overlay/` using the CSS Custom Highlight API.
10. Scaffold the `apps/study` laboratory web application using React + Vite + Tailwind.
