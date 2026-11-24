# CalibrAI: Phase 3 Execution Roadmap & Engineering Backlog

**Audit Date:** November 2026  
**Auditor Roles:** Principal Software Architect, Project Director, Academic Supervisor  
**Project:** CalibrAI ("Designing Trust Calibration Signals for AI Assistants")  

---

## 1. Master Research Dependency Matrix

Before engineering begins, key scientific questions must be resolved through literature and empirical piloting. The matrix below defines the strict causal dependency from research to code.

| Research Domain | Core Research Question | Key Academic Literature | Required Scientific Decision | Implementation Impact | Concrete Deliverable |
|---|---|---|---|---|---|
| **Atomic Claim Decomposition** | How should long-form conversational text be segmented into verifiable units without losing context? | Min et al. (EMNLP 2023), Kamoi et al. (EMNLP 2023) | Adopt atomic declarative proposition decomposition; retain parent sentence index mapping. | Replaces regex sentence splitter with LLM-based few-shot prompt using strict JSON schema. | `apps/api/app/services/extraction_service.py` |
| **Claim Materiality Classification** | How should claim importance be quantified without subjective bias? | Lee & See (2004), Vasconcelos et al. (2024) | Classify materiality into 3 ordinal tiers (`high`, `medium`, `low`) based on decision impact and counterfactual outcome change. | Replaces character-length heuristic with semantic classifier; grounds materiality weights (3, 2, 1). | `docs/protocol/MATERIALITY_RUBRIC.md` |
| **Evidence Retrieval & Freshness** | How do we guarantee fresh, high-authority web evidence within sub-second latencies? | Vu et al. (ACL 2024), Gao et al. (EMNLP 2023) | Use Tavily search API for direct clean passage extraction; enforce evidence cutoff $\le \text{answer\_timestamp}$. | Bypasses complex Playwright scrapers; fits within the 8,000 ms extension timeout. | `apps/api/app/services/retrieval_service.py` |
| **Source Independence** | How do we detect duplicated wire reports and syndicated news across multiple URLs? | Thorne et al. (2018), Chen et al. (2023) | Cluster retrieved evidence by domain ownership and Jaccard text similarity ($\ge 0.70$). | Prevents multi-URL syndication from inflating independence score. | `apps/api/app/services/verification_service.py` |
| **Confidence Calibration** | How should raw heuristic scores be mapped to valid empirical probabilities? | Guo et al. (ICML 2017), Platt (1999) | Fit Isotonic Regression (PAVA) on calibration partition ($N = 120$); evaluate via ECE and Brier score. | Wires fitted calibrator into runtime signal pipeline before emitting confidence badge. | `apps/api/app/services/calibration_service.py` |
| **UI Cognitive Forcing** | How can visual signals prevent over-reliance without causing caveat fatigue? | Buçinca et al. (2021), Bansal et al. (2021), Vasconcelos (2023) | Implement progressive disclosure: ambient confidence chip + interactive claim span highlights + citation drawer. | Implements Range/CSS highlight overlay in extension Shadow DOM. | `src/overlay/ClaimHighlighter.tsx` |
| **Cross-Platform Calibration** | Do calibration parameters transfer across ChatGPT, Claude, and Gemini? | Farquhar et al. (Nature 2024), Chen et al. (2023) | Train platform-specific vs. pooled calibration curves; test for distribution shift via KS-test. | Determines whether backend maintains one global calibration curve or three platform models. | `notebooks/cross_platform_calibration.ipynb` |
| **Institutional Ethics Review** | How do we ensure compliance with ICMR 2017 and DPDP Act 2023? | ICMR Guidelines (2017), BITS Pilani IHEC SOPs | Submit formal protocol with voluntary consent, participant information sheet, and debriefing. | Unblocks human recruitment and participant data collection. | `docs/ethics/IHEC_APPLICATION_DOSSIER.pdf` |

---

## 2. Comprehensive Implementation Backlog

### Phase 2 Closure: Engineering Hardening & Migration Consistency
- [ ] **Task 2.1 — Alembic Schema Timestamp Nullability Migration:**
  - *Rationale:* SQLAlchemy models declare `created_at` non-nullable, but `0001_initial.py` created them nullable.
  - *Files:* Create `apps/api/alembic/versions/0002_timestamp_nullability.py`.
  - *Acceptance Criteria:* `alembic upgrade head` runs cleanly; autogenerate diff against metadata returns zero differences.
  - *Priority:* P2 | *Effort:* 2 hours | *Dependencies:* None.
- [ ] **Task 2.2 — Initialize Local SQLite & Setup Script:**
  - *Rationale:* `apps/api/calibrai.db` is uninitialized, causing local run errors if migrations are not executed.
  - *Files:* `apps/api/README.md`, update setup scripts.
  - *Acceptance Criteria:* Running `alembic upgrade head` populates all tables; `GET /health` passes against initialized DB.
  - *Priority:* P2 | *Effort:* 1 hour | *Dependencies:* Task 2.1.
- [ ] **Task 2.3 — Add PostgreSQL Docker Service for CI:**
  - *Rationale:* PostgreSQL RLS policies are currently untested in SQLite-based CI.
  - *Files:* `.github/workflows/ci.yml`, `docker-compose.test.yml`.
  - *Acceptance Criteria:* CI spins up PostgreSQL 15, applies migrations, and verifies tenant isolation policies.
  - *Priority:* P2 | *Effort:* 4 hours | *Dependencies:* Task 2.1.

---

### Phase 3A: Research Foundations & Dataset Governance
- [ ] **Task 3A.1 — Finalize Empirical Research Protocol & Pre-Registration:**
  - *Rationale:* Pre-registering hypotheses, materiality weights, and stopping rules prevents p-hacking.
  - *Files:* Create `docs/research/PREREGISTRATION_PROTOCOL.md`.
  - *Acceptance Criteria:* Formal document locking $H_1, H_2, H_3$, materiality weights (3, 2, 1), 80%/60% thresholds.
  - *Priority:* P1 | *Effort:* 8 hours | *Dependencies:* Literature review.
- [ ] **Task 3A.2 — Curate 600 Factual QA Source Bank:**
  - *Rationale:* Need original prompts spanning ChatGPT, Claude, and Gemini across 4 domains.
  - *Files:* `data/raw_qa_bank.json`.
  - *Acceptance Criteria:* 600 verified pairs (200 ChatGPT, 200 Claude, 200 Gemini) with ISO timestamps.
  - *Priority:* P1 | *Effort:* 24 hours | *Dependencies:* Task 3A.1.
- [ ] **Task 3A.3 — Partition Air-Gapping & Leakage Verification:**
  - *Rationale:* Prevent contamination between dev (360), calibration (120), and test (120).
  - *Files:* `scripts/partition_dataset.py`.
  - *Acceptance Criteria:* `apps/api/app/dataset.py` validator confirms 0 prompt/answer hash overlap and near-duplicate similarity $< 0.70$.
  - *Priority:* P1 | *Effort:* 4 hours | *Dependencies:* Task 3A.2.
- [ ] **Task 3A.4 — Double-Annotate 30-Example Pilot Batch:**
  - *Rationale:* Validate annotation handbook and verify inter-rater agreement before full dataset labeling.
  - *Files:* `data/pilot_packets/`, `data/pilot_annotations/`.
  - *Acceptance Criteria:* Two independent reviewers achieve Cohen's $\kappa \ge 0.67$ on claim outcomes and materiality.
  - *Priority:* P1 | *Effort:* 16 hours | *Dependencies:* Task 3A.3.

---

### Phase 3B: Real Signal Engine (LLM + Search + NLI)
- [ ] **Task 3B.1 — Implement LLM Atomic Claim Extractor:**
  - *Rationale:* Replace character-length regex heuristic with semantic claim decomposition.
  - *Files:* `apps/api/app/services/extractor.py`.
  - *Acceptance Criteria:* Uses `gpt-4o-mini` with strict JSON schema to return $\le 8$ atomic claims, sentence indices, and materiality.
  - *Priority:* P1 | *Effort:* 12 hours | *Dependencies:* Task 3A.1.
- [ ] **Task 3B.2 — Implement Tavily Web Retrieval Provider:**
  - *Rationale:* Replace static JSON fixture with live web search and clean passage extraction.
  - *Files:* `apps/api/app/services/retriever.py`.
  - *Acceptance Criteria:* Issues parallel search queries; clusters sources by domain; enforces temporal cutoff $\le \text{answer\_timestamp}$.
  - *Priority:* P1 | *Effort:* 12 hours | *Dependencies:* Task 3B.1.
- [ ] **Task 3B.3 — Implement NLI Claim Entailment Verifier:**
  - *Rationale:* Replace mock relevance scores with real Natural Language Inference entailment.
  - *Files:* `apps/api/app/services/verifier.py`.
  - *Acceptance Criteria:* Evaluates claim against passages using DeBERTa-v3 / GPT-4o-mini; returns `supported`, `contradicted`, or `insufficient_evidence`.
  - *Priority:* P1 | *Effort:* 14 hours | *Dependencies:* Task 3B.2.
- [ ] **Task 3B.4 — Wire Aggregator & Isotonic Calibrator:**
  - *Rationale:* Integrate real verifications into materiality-weighted aggregation and calibrate output probability.
  - *Files:* `apps/api/app/services/reliability_service.py`.
  - *Acceptance Criteria:* High contradiction veto triggers Low; calibrated score maps to High/Medium/Low; latency $\le 4,500$ ms.
  - *Priority:* P1 | *Effort:* 8 hours | *Dependencies:* Task 3B.3.
- [ ] **Task 3B.5 — Asynchronous Signal Polling / SSE Streaming:**
  - *Rationale:* Prevent HTTP timeout if complex web search takes $> 8,000$ ms.
  - *Files:* `apps/api/app/api/routes/signal.py`, `src/core/backendSignal.ts`.
  - *Acceptance Criteria:* Client receives initial checking state, polls or streams result, overlay mounts upon completion.
  - *Priority:* P2 | *Effort:* 16 hours | *Dependencies:* Task 3B.4.

---

### Phase 3C: Offline Scientific Validation
- [ ] **Task 3C.1 — Full Annotation of Calibration & Held-Out Partitions:**
  - *Rationale:* Produce ground-truth labels for 120 calibration and 120 held-out test items.
  - *Files:* `data/partitions/calibration.json`, `data/partitions/test.json`.
  - *Acceptance Criteria:* Two independent annotators + adjudication; manifest generated with complete provenance.
  - *Priority:* P1 | *Effort:* 40 hours | *Dependencies:* Task 3A.4.
- [ ] **Task 3C.2 — Fit Isotonic Calibrator on Calibration Partition:**
  - *Rationale:* Calibrate raw reliability scores on isolated calibration data without touching test data.
  - *Files:* `scripts/fit_calibration.py`, `models/calibrator_v1.json`.
  - *Acceptance Criteria:* Isotonic regression parameters locked; ECE on calibration partition reduced by $\ge 40\%$.
  - *Priority:* P1 | *Effort:* 6 hours | *Dependencies:* Task 3B.4, Task 3C.1.
- [ ] **Task 3C.3 — Execute Held-Out Benchmark & Generate Scientific Report:**
  - *Rationale:* One-time unblinded evaluation on air-gapped held-out test partition.
  - *Files:* `scripts/evaluate_held_out.py`, `docs/reports/OFFLINE_VALIDATION_RESULTS.md`.
  - *Acceptance Criteria:* Reports binary AUROC, ECE, Brier score, Risk-Coverage curves, and per-platform confusion matrices with bootstrap 95% CIs.
  - *Priority:* P1 | *Effort:* 12 hours | *Dependencies:* Task 3C.2.

---

### Phase 3D: Study Harness Platform (`apps/study`)
- [ ] **Task 3D.1 — Scaffold Study Harness Web App:**
  - *Rationale:* Build dedicated laboratory web app for controlled experimental trials.
  - *Files:* `apps/study/` (React + Vite + Tailwind).
  - *Acceptance Criteria:* Participant login, informed consent workflow, study task runner, Latin Square randomizer.
  - *Priority:* P1 | *Effort:* 24 hours | *Dependencies:* Task 2.1.
- [ ] **Task 3D.2 — Implement 4-Condition Rendering Components:**
  - *Rationale:* Render Baseline, Caveat, Confidence Chip, and Claim-Level Highlighting consistently.
  - *Files:* `apps/study/src/components/conditions/`.
  - *Acceptance Criteria:* In-situ claim span highlights wrap text; clicking opens interactive citation drawer.
  - *Priority:* P1 | *Effort:* 16 hours | *Dependencies:* Task 3D.1.
- [ ] **Task 3D.3 — Telemetry Logging & Psychometric Questionnaires:**
  - *Rationale:* Capture millisecond-level decision latency, acceptance/rejection, Jian trust scale, NASA-TLX.
  - *Files:* `apps/study/src/services/telemetry.ts`.
  - *Acceptance Criteria:* Logs trial events to `POST /v1/events` and questionnaires to `POST /v1/questionnaires`.
  - *Priority:* P1 | *Effort:* 12 hours | *Dependencies:* Task 3D.2.

---

### Phase 3E: Human-Subject Evaluation (BITS Pilani)
- [ ] **Task 3E.1 — Institutional Ethics Committee (IHEC) Submission:**
  - *Rationale:* Obtain institutional approval before human subject recruitment.
  - *Files:* `docs/ethics/IHEC_APPLICATION.pdf`.
  - *Acceptance Criteria:* Formal review and ethical clearance certificate from BITS Pilani IHEC.
  - *Priority:* P1 | *Effort:* 16 hours | *Dependencies:* Task 3A.1, Task 3D.1.
- [ ] **Task 3E.2 — Participant Recruitment & Experiment Execution:**
  - *Rationale:* Collect experimental trial data across 120 participants (30 per Latin Square group).
  - *Files:* Participant tracking database.
  - *Acceptance Criteria:* 120 completed sessions (1,920 individual trial decisions) with complete survey responses.
  - *Priority:* P1 | *Effort:* 40 hours | *Dependencies:* Task 3E.1, Task 3D.3.

---

### Phase 3F: Statistical Analysis & Academic Deliverables
- [ ] **Task 3F.1 — Statistical Modeling (Mixed-Effects GLMM):**
  - *Rationale:* Test $H_1, H_2, H_3$ controlling for participant and question random effects.
  - *Files:* `analysis/glmm_reliance_models.R` or Python `statsmodels`.
  - *Acceptance Criteria:* Regression coefficients, p-values, odds ratios, and interaction plots for reliance and cognitive load.
  - *Priority:* P1 | *Effort:* 16 hours | *Dependencies:* Task 3E.2.
- [ ] **Task 3F.2 — Academic Paper Drafting & Demonstration Video:**
  - *Rationale:* Produce final peer-reviewed conference paper (CHI / CSCW / FAccT) and demonstration.
  - *Files:* `paper/calibrai_chi2027.tex`, `docs/DEMO.md`.
  - *Acceptance Criteria:* Complete academic manuscript reporting offline metrics, human study findings, and discussion.
  - *Priority:* P1 | *Effort:* 40 hours | *Dependencies:* Task 3F.1, Task 3C.3.

---

## 3. Team Allocation: Six Independent Work Packages

To maximize velocity and avoid merge conflicts, the project is structured into six independent Work Packages (WPs):

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ WP1: Core Platform & Security Engineering (Lead: Systems Architect)         │
│ - Tasks: 2.1, 2.2, 2.3, 3B.5.                                              │
│ - Deliverables: Alembic migration 0002, PostgreSQL CI, async SSE streaming. │
├─────────────────────────────────────────────────────────────────────────────┤
│ WP2: Dataset Curation & Annotation Governance (Lead: Data Methodologist)    │
│ - Tasks: 3A.1, 3A.2, 3A.3, 3A.4, 3C.1.                                     │
│ - Deliverables: 600 QA bank, partition air-gapping, double-blind labels.     │
├─────────────────────────────────────────────────────────────────────────────┤
│ WP3: Real Verification Engine & Calibration (Lead: AI/ML Engineer)         │
│ - Tasks: 3B.1, 3B.2, 3B.3, 3B.4, 3C.2, 3C.3.                               │
│ - Deliverables: Tavily search, DeBERTa NLI, Isotonic calibrator, benchmark. │
├─────────────────────────────────────────────────────────────────────────────┤
│ WP4: Extension Overlay & Highlighting UI (Lead: Frontend/Extension Dev)     │
│ - Tasks: Range text highlight overlay, citation drawer, live canary tests.  │
│ - Deliverables: Shadow DOM claim span highlighting, dark mode UX polish.    │
├─────────────────────────────────────────────────────────────────────────────┤
│ WP5: Controlled Study Harness Platform (Lead: Full-Stack Dev)               │
│ - Tasks: 3D.1, 3D.2, 3D.3.                                                 │
│ - Deliverables: apps/study web application, Latin Square engine, surveys.    │
├─────────────────────────────────────────────────────────────────────────────┤
│ WP6: Institutional Ethics, Human Trials & Stats (Lead: Academic Supervisor) │
│ - Tasks: 3E.1, 3E.2, 3F.1, 3F.2.                                            │
│ - Deliverables: IHEC approval, 120-participant study, GLMM analysis, paper. │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Immediate Concrete Next Actions (First 10 Tasks)

1. **Action 1 (Database):** Create Alembic migration `0002_timestamp_nullability.py` setting `nullable=False` on the 6 timestamp columns to reconcile ORM models with database schemas.
2. **Action 2 (Local DB):** Run `alembic upgrade head` in `apps/api` to initialize `calibrai.db` with all tables.
3. **Action 3 (Research Pre-Registration):** Draft and lock `docs/research/PREREGISTRATION_PROTOCOL.md` defining hypotheses $H_1, H_2, H_3$, materiality weights (3, 2, 1), and 80%/60% thresholds.
4. **Action 4 (Ethics Application):** Prepare BITS Pilani IHEC application dossier (Protocol, PIS, ICF, Debriefing document).
5. **Action 5 (QA Bank Curation):** Curate the first 100 open-domain question-answer instances (balanced across ChatGPT, Claude, and Gemini) into `data/source_qa_bank.json`.
6. **Action 6 (Pilot Annotation):** Deliver frozen pilot packets to two independent student reviewers; evaluate Cohen's $\kappa$ stopping threshold.
7. **Action 7 (Provider Client):** Implement `apps/api/app/services/extractor.py` using OpenAI `gpt-4o-mini` with strict JSON schema for atomic claim extraction.
8. **Action 8 (Search Client):** Implement `apps/api/app/services/retriever.py` integrating the Tavily Search API with domain clustering.
9. **Action 9 (Extension UI):** Prototype the non-destructive text highlighting overlay in `src/overlay/` using the CSS Custom Highlight API or Range DOM injection.
10. **Action 10 (Study App Scaffold):** Initialize `apps/study` repository structure using Vite + React 18 + Tailwind.
