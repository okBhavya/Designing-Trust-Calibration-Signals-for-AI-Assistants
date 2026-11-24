# CalibrAI: Dataset Governance, Annotation Protocols & Ground-Truth Readiness

**Audit Date:** November 2026  
**Auditor Roles:** Senior AI/ML Researcher, Research Methodologist, Data Governance Auditor  
**Project:** CalibrAI ("Designing Trust Calibration Signals for AI Assistants")  

---

## 1. Deep Audit of Candidate Research Datasets

CalibrAI requires an empirical dataset of question-answer pairs with fine-grained claim annotations, evidence provenance, and verified ground-truth reliability labels. The Phase 2 repository documents evaluated three public datasets: **FELM**, **FActScore**, and **RAGTruth**. This audit conducts an exhaustive analysis of their legal licenses, data structures, and scientific limitations.

### 1.1 Detailed Comparative Evaluation

| Evaluation Dimension | FELM (Chen et al., NeurIPS 2023) | FActScore (Min et al., EMNLP 2023) | RAGTruth (Yue et al., ACL 2024) |
|---|---|---|---|
| **Primary Paper** | *FELM: Benchmarking Factuality Evaluation of Large Language Models* | *FActScore: Fine-grained Atomic Evaluation of Factual Precision in Long Form Text Generation* | *RAGTruth: A Hallucination Corpus for Developing Trustworthy Retrieval-Augmented Language Models* |
| **Origin & Provenance** | Model-generated ChatGPT responses across 847 curated prompts in 5 domains (World Knowledge, Science/Tech, Writing, Reasoning, Math). | Generated biographies from 12 language models prompted on Wikidata human entities. | ~18,000 model-generated responses from GPT-4, GPT-3.5, and LLaMA-2 on MS MARCO, CNN/DailyMail, Yelp. |
| **Declared License** | **CC BY-NC-SA 4.0** (Creative Commons Attribution-NonCommercial-ShareAlike 4.0) | Code is **MIT**; underlying dataset contains scraped Wikipedia text and Wikidata facts. | Code is **MIT**; underlying data comprises MS MARCO, CNN/DM, and Yelp reviews. |
| **Commercial / Redistribution Rights** | **Non-Commercial Only (NC).** Commercial distribution or integration into proprietary tools is prohibited. ShareAlike forces any derivative dataset under CC BY-NC-SA. | Permissive for research, but Wikipedia text is licensed under **CC BY-SA 4.0**; requires strict upstream attribution. | **Severely Restricted.** MS MARCO and Yelp data terms prohibit commercial redistribution and impose strict terms of service on third-party hosting. |
| **Annotation Granularity** | Segment-level factuality (spans, binary factual/unfactual, error taxonomy: false information, reasoning error, etc.). | Atomic fact decomposition (short independent declarative propositions evaluated as supported/unsupported). | Word-level and span-level hallucination masks (contradiction vs. ungrounded fabrication). |
| **Evidence Grounding** | Reference URLs provided for many claims, but passages are NOT frozen or timestamped. Many external URLs suffer from link rot. | Grounded strictly in a static Wikipedia database snapshot dated **2023-04-01**. No live web URLs or external news sources. | Grounded strictly in pre-retrieved text snippets provided in prompt context. No external web URLs or dynamic sources. |
| **Outcome Taxonomy** | Binary: `True` vs. `False` + Error Type. | Binary: `Supported` vs. `Unsupported`. | Binary: `Hallucinatory` vs. `Faithful`. |
| **Compatibility with CalibrAI 3-Class Ontology** | **Incompatible.** Lacks explicit `insufficient_evidence` outcome (conflates unverified claims with false claims). | **Incompatible.** Binary scoring does not distinguish contradicted claims from claims lacking evidence. | **Incompatible.** Evaluates *faithfulness to provided context*, not *factuality against open-web evidence*. |
| **Claim Materiality & Importance** | Absent. All segments weighted equally. | Absent. All atomic facts weighted equally. | Absent. All spans weighted equally. |
| **Temporal Metadata** | Generation timestamps partially recorded; external URL publication dates absent. | Frozen to 2023-04-01 Wikipedia dump. | Static prompt context; no dynamic temporal validities. |
| **Repository Verdict** | **REJECTED AS SOURCE.** License restrictions (NC-SA), link rot, missing frozen passages, and binary ontology make FELM unsuitable for direct redistribution. | **REJECTED AS SOURCE.** Wikipedia biography domain is too narrow; binary scoring lacks three-class ontology; missing source independence. | **REJECTED AS SOURCE.** Evaluates RAG context faithfulness rather than open-domain factuality; third-party corpus licensing restrictions. |

### 1.2 Evaluation of Alternative Public Datasets

Because FELM, FActScore, and RAGTruth are rejected for direct redistribution, alternative public benchmarks were evaluated:

1. **FreshQA (Vu et al., ACL 2024):**
   - *Strengths:* 600 natural open-domain questions categorized by temporal dynamism (fast-changing, slow-changing, stable, false-premise). Evaluates open-web search grounding.
   - *Limitations:* Answers are short factual entities; lacks complex multi-sentence responses and claim-level span segmentations.
   - *Applicability:* Excellent reference for prompt design and temporal cutoff benchmarking, but cannot serve as a fine-grained claim dataset without significant re-annotation.
2. **TruthfulQA (Lin et al., ACL 2022):**
   - *Strengths:* 817 questions designed to elicit imitative human falsehoods and misconceptions.
   - *Limitations:* Highly adversarial and artificial questions; not representative of everyday conversational assistant interactions. Binary truth/informativeness scoring.
3. **ALCE (Gao et al., EMNLP 2023 - *Enabling Large Language Models to Generate Text with Citations*):**
   - *Strengths:* Focuses on citation generation and passage-level attribution for long-form QA across ASQA, QAMPARI, and ELI5.
   - *Limitations:* Evaluates whether model cites its own prompt passages; does not address post-hoc verification of un-cited model responses.
4. **Conclusion on External Datasets:**
   No existing off-the-shelf public dataset satisfies CalibrAI's unique triad of:
   - Natural conversational responses across ChatGPT, Claude, and Gemini.
   - Three-class claim outcomes (`supported`, `contradicted`, `insufficient_evidence`).
   - Explicit claim materiality assignments (`high`, `medium`, `low`) and frozen multi-source evidence bundles with independence grouping.

---

## 2. CalibrAI Curated Research Dataset: Architecture & Sample Size Justification

The definitive path forward is the creation of an **original, rigorously governed CalibrAI Curated Factual QA Dataset**.

### 2.1 Proposed Dataset Sizing & Partitioning

The proposed target dataset consists of **600 multi-platform question-answer instances** accompanied by an isolated **30-example development pilot**:

```
CalibrAI Research Dataset (N = 600 instances)
├── Development Partition (60%, N = 360)
│   ├── Used for: Prompt engineering, regex/NLP boundary tuning, error analysis.
│   └── Access: Open to developers; zero threshold fitting or evaluation.
├── Calibration Partition (20%, N = 120)
│   ├── Used for: Isotonic regression fitting, risk-coverage threshold selection, temperature scaling.
│   └── Access: Restricted to automated calibration scripts; locked before evaluation.
└── Held-Out Test Partition (20%, N = 120)
    ├── Used for: Final scientific evaluation report (AUROC, ECE, Brier score, Macro-F1).
    └── Access: STRICTLY AIR-GAPPED; evaluated exactly once upon study completion.

Isolated Pilot Batch (N = 30)
└── Development-Only: Used exclusively for reviewer training, annotator agreement calibration, and handbook refinement.
```

### 2.2 Statistical Power & Sample Size Derivation

Is $N = 120$ sufficient for the calibration and held-out test partitions?

1. **Answer-Level vs. Claim-Level Power:**
   Each answer generates an average of 4.5 claims (empirically capped between 1 and 8). Therefore:
   - $N = 120$ answers yields approximately $120 \times 4.5 \approx \mathbf{540\text{ claim-level evaluations}}$ per partition!
   - For claim-level classification (three-class: supported, contradicted, insufficient), $N = 540$ provides high statistical power ($> 0.95$) to detect small effect size differences ($\Delta F1 \ge 0.05$ at $\alpha = 0.05$).
2. **Binary Answer-Level Calibration (ECE & AUROC):**
   In binary reliability evaluation (`reliable` vs. `unreliable`, excluding `indeterminate`), assuming a balanced prevalence ($p = 0.50$):
   - With $N = 100$ evaluable answers, the standard error of accuracy is $\text{SE} = \sqrt{\frac{0.5 \times 0.5}{100}} = 0.05$ (margin of error $\pm 9.8\%$).
   - For AUROC, by Hanley & McNeil (1982), with $n_1 = 50$ and $n_2 = 50$, an AUROC of 0.80 has a standard error:
     $$\text{SE}(\text{AUC}) \approx \sqrt{\frac{0.80(1-0.80) + (50-1)(0.08) + (50-1)(0.04)}{50 \times 50}} \approx 0.044$$
     This yields a 95% confidence interval of $[0.71, 0.89]$, which is sufficiently powered to reject the null hypothesis ($\text{AUC} = 0.50$, $z = 6.82, p < 10^{-6}$).
3. **Partition Stratification Requirements:**
   To guarantee statistical validity, each partition ($N = 120$) must maintain quota stratification:
   - Platform balance: 40 ChatGPT, 40 Claude, 40 Gemini answers.
   - Domain balance: 30 History/Geography, 30 Science/Technology, 30 Health/Life Sciences, 30 Governance/Economy.
   - Ground-truth reliability balance: Target ~45 reliable, ~45 unreliable, ~30 indeterminate.

---

## 3. Audit of Annotation Handbook & Scoring Methodology

The repository's annotation protocol is defined in `docs/PHASE_2C_ANNOTATION_HANDBOOK.md` and enforced in `apps/api/app/dataset.py`. This audit inspects the mathematical and empirical defensibility of these rules.

### 3.1 Answer-Level Decision Logic

CalibrAI defines three mutually exclusive answer-level states:

1. **RELIABLE:**
   - Condition 1: Every high-materiality claim is `supported`.
   - Condition 2: No high-materiality claim is `contradicted`.
   - Condition 3: At least 80% of total materiality weight is supported:
     $$\frac{\sum_{i=1}^K w_i \cdot \mathbb{I}(\text{outcome}_i = \text{supported})}{\sum_{i=1}^K w_i} \ge 0.80, \quad w_i \in \{1, 2, 3\}$$
2. **UNRELIABLE:**
   - Condition 1: Any high-materiality claim is `contradicted` (VETO RULE), **OR**
   - Condition 2: Less than 60% of total materiality weight is supported:
     $$\frac{\sum_{i=1}^K w_i \cdot \mathbb{I}(\text{outcome}_i = \text{supported})}{\sum_{i=1}^K w_i} < 0.60$$
3. **INDETERMINATE:**
   - Any answer where the weighted supported ratio falls in $[0.60, 0.80)$.
   - Any answer where high-materiality claims have unresolved conflicting evidence.
   - Any answer containing **zero externally checkable claims** ($\sum w_i = 0$).

### 3.2 Methodological Critique & Edge Cases

| Rule / Definition | Methodological Strengths | Vulnerabilities & Edge Cases | Recommended Refinement |
|---|---|---|---|
| **High-Materiality Veto** | Prevents dangerous dilution where 5 correct trivial claims mask a lethal contradiction. Reflects real-world decision risk. | If an annotator misclassifies a medium claim as high, a single contested detail invalidates an otherwise excellent answer. | Require independent double-review on all `high` materiality tags; any disagreement on materiality triggers adjudication. |
| **Materiality Weights (3, 2, 1)** | Simple, integer, monotonic weighting ($w_{\text{high}}=3, w_{\text{med}}=2, w_{\text{low}}=1$). | Arbitrary linear progression. Why is high worth $3\times$ low instead of $5\times$ or $10\times$? | Retain (3, 2, 1) as the frozen pre-registered rule; conduct sensitivity analysis in Phase 3F with alternative weights (e.g., exponential 4, 2, 1). |
| **80% / 60% Thresholds** | Creates a 20% "buffer zone" for `indeterminate` cases, preventing noisy threshold flipping near the boundary. | The thresholds were chosen a priori without empirical fitting on human trust preferences. | Maintain as the pre-registered ground-truth rule; use the calibration partition to empirically fit the *model's* predicted score thresholds to this ground truth. |
| **Zero-Denominator Edge Case** | Explicitly handled in `dataset.py` and handbook: marked `indeterminate`, excluded from binary metrics, assigned `confidence: null`. | Some users might expect subjective advice to be classified as reliable if it is harmless. | The current handling is scientifically correct. Trust calibration cannot assess the factuality of non-factual text; abstention is mandatory. |
| **Insufficient Evidence in Denominator** | Claims with `insufficient_evidence` remain in the denominator $\sum w_i$ and contribute 0 to the numerator. | Severe search engine outages cause answers to be labeled `unreliable` if score drops below 0.60. | Distinguish *technical retrieval failure* (which yields `assessmentState: unavailable`) from *genuine factual un-verifiability* (which yields `insufficient_evidence`). |

---

## 4. Inter-Annotator Agreement (IAA) Protocol

To guarantee academic rigor, human annotations must not rely on a single reviewer.

### 4.1 Double-Blinded Annotation Protocol
1. **Blinding:** Both reviewers receive frozen packets containing the original prompt, AI answer, sentence indices, claim spans, and frozen evidence bundle.
2. **Prediction Masking:** All CalibrAI predictions, confidence scores, model versions, and generated explanations are completely stripped from annotation packets.
3. **Independence:** Reviewers submit annotations independently through secure forms. Neither reviewer can see the other's submissions.

### 4.2 Agreement Metrics & Stopping Rule
- **Claim-Level Agreement (Three-Class Outcome):**
  Measured using **Cohen's Kappa ($\kappa$)** for pairs of reviewers, and **Krippendorff's Alpha ($\alpha$)** across the pool:
  $$\kappa = \frac{P_o - P_e}{1 - P_e}$$
- **Materiality Agreement:** Measured using Cohen's weighted kappa ($\kappa_w$) with linear penalties across ordinal values (`low`, `medium`, `high`).
- **Pre-Registered Progression Threshold:**
  - $\kappa \ge 0.75$: Excellent agreement; proceed directly to adjudication.
  - $0.67 \le \kappa < 0.75$: Acceptable agreement; proceed with adjudication and document contested patterns.
  - $\kappa < 0.67$: **STOPPING RULE TRIGGERED.** All annotation is suspended. The handbook must be clarified, reviewer training repeated, and pilot batch re-annotated.

---

## 5. Dataset Acquisition & Governance Action Checklist

Before any data enters the calibration or test partitions, the following checklist must be satisfied:

- [ ] **Data Source Permissibility:** Every prompt-answer pair is generated directly by the study team or acquired under a fully documented, royalty-free, perpetual research license.
- [ ] **Evidence Passage Rights:** Retrieved web text snippets must adhere to fair-use quotation standards for academic research (passages limited to $\le 250$ words).
- [ ] **Temporal Anchoring:** Prompt timestamp, AI generation timestamp, evidence retrieval timestamp, and evidence publication timestamp are fully recorded in ISO 8601 UTC format.
- [ ] **Evidence Freezing:** Evidence URLs and extracted text snippets are stored immutably in version-controlled JSON bundles with SHA-256 content digests.
- [ ] **Partition Air-Gapping:** SHA-256 prompt/answer digests and near-duplicate text embeddings are checked across partitions to guarantee zero leakage between development, calibration, and held-out test sets.
- [ ] **Privacy & PII Sanitization:** All prompt-answer pairs are scrubbed of personal identifiers, IP addresses, usernames, and proprietary credentials.
