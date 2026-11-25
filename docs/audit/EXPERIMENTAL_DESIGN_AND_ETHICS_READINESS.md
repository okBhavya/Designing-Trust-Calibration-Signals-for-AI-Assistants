# CalibrAI: Human-Subject Experimental Design, Methodology & Ethics Protocol

**Audit Date:** November 2026  
**Auditor Roles:** Senior AI/ML Researcher, Research Methodologist, Human Factors & Ethics Specialist  
**Project:** CalibrAI ("Designing Trust Calibration Signals for AI Assistants")  

---

## 1. Research Hypotheses & Experimental Objectives

The ultimate objective of CalibrAI is to investigate whether evidence-grounded, claim-level calibration signals enable humans to make better reliance decisions when interacting with AI assistants.

### 1.1 Formal Research Hypotheses
- **Hypothesis 1 (Over-reliance Reduction - Primary):**  
  *Participants exposed to Claim-Level Highlighting (Condition 3) will exhibit significantly lower over-reliance rates on incorrect AI assistant responses compared to participants exposed to the Confidence Chip (Condition 2), the Generic Caveat (Condition 1), or the Baseline (Condition 0).*
  $$H_1: \mu_{\text{Overreliance}}(\text{Highlighting}) < \mu_{\text{Overreliance}}(\text{Chip}) \le \mu_{\text{Overreliance}}(\text{Caveat}) \le \mu_{\text{Overreliance}}(\text{Baseline})$$
- **Hypothesis 2 (Trust Calibration Sensitivity):**  
  *Participants in the Claim-Level Highlighting condition will demonstrate significantly higher trust resolution (higher subjective trust on correct answers and lower subjective trust on incorrect answers) compared to the Confidence Chip and Baseline conditions.*
- **Hypothesis 3 (Cognitive Load & Caveat Fatigue Tradeoff):**  
  *Claim-Level Highlighting will not significantly increase perceived cognitive workload (NASA-TLX) or decision latency compared to the Confidence Chip, while providing higher subjective explanation satisfaction.*

---

## 2. Experimental Arms & Interface Conditions

The experiment evaluates four distinct visual interface conditions:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Condition 0: Baseline (Control)                                             │
│ - Raw AI response exactly as rendered by modern assistant interfaces.      │
│ - No reliability indicator, badge, or trust signal.                        │
├─────────────────────────────────────────────────────────────────────────────┤
│ Condition 1: Generic Caveat (Industry Standard Control)                     │
│ - Static, ubiquitous disclaimer below the response:                         │
│   "AI assistants can make mistakes. Verify important information."          │
│ - Non-dynamic; identical across all correct and incorrect answers.         │
├─────────────────────────────────────────────────────────────────────────────┤
│ Condition 2: Confidence Chip (Answer-Level Aggregate Signal)                │
│ - Ambient badge below the response: "High Confidence" / "Low Confidence".   │
│ - Single color-coded status dot (Green / Red / Amber).                     │
│ - Expandable single-paragraph summary ("Why?").                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ Condition 3: Claim-Level Highlighting (Granular Evidence Signal)             │
│ - In-situ color highlights directly on answer claim spans:                  │
│   • Green underline/highlight: Supported by independent web evidence.       │
│   • Red underline/highlight: Contradicted by authoritative evidence.        │
│   • Yellow/Dotted underline: Insufficient evidence or conflicting reports.  │
│ - Interactive citation card drawer: Clicking any highlight reveals the      │
│   source snippet, publisher, freshness, and entailment rationale.           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Experimental Design: Within-Subjects Counterbalanced Latin Square

### 3.1 Design Architecture
To maximize statistical power while controlling for individual cognitive differences (e.g., domain expertise, baseline skepticism, Need for Cognition), a **within-subjects repeated-measures design** with a **$4 \times 4$ balanced Latin Square** counterbalancing scheme is selected.

- **Total Tasks:** Each participant evaluates **16 independent factual decision tasks** (4 questions per experimental condition).
- **Trial Balancing:**
  - 50% of trials present **factually correct/reliable AI responses**.
  - 50% of trials present **subtly flawed/unreliable AI responses** (containing high-materiality contradictions or unsupported factual fabrications).
- **Latin Square Counterbalancing:** Participants are randomly assigned to one of 4 counterbalanced sequence groups to prevent order and fatigue effects:

| Sequence Group | Block 1 (Tasks 1–4) | Block 2 (Tasks 5–8) | Block 3 (Tasks 9–12) | Block 4 (Tasks 13–16) |
|---|---|---|---|---|
| **Group A** | Condition 0 (Baseline) | Condition 1 (Caveat) | Condition 2 (Chip) | Condition 3 (Highlight) |
| **Group B** | Condition 1 (Caveat) | Condition 3 (Highlight) | Condition 0 (Baseline) | Condition 2 (Chip) |
| **Group C** | Condition 2 (Chip) | Condition 0 (Baseline) | Condition 3 (Highlight) | Condition 1 (Caveat) |
| **Group D** | Condition 3 (Highlight) | Condition 2 (Chip) | Condition 1 (Caveat) | Condition 0 (Baseline) |

### 3.2 Pre-Generated Controlled Trial Bank vs. Live Extension Separation
**CRITICAL METHODOLOGICAL DISTINCTION:**
- **The Human Experiment must NOT manipulate live AI answers deceptively in real-time.** Intercepting live user browsing and inserting synthetic errors into live ChatGPT/Claude responses violates research ethics and risks participant deception.
- **Controlled Evaluation Environment (`apps/study`):**
  The human-subject experiment runs inside a dedicated, laboratory-grade web application (`apps/study`). The application presents **pre-generated, rigorously curated prompt-answer pairs** with verified ground truth and controlled accuracy distributions.
- **Browser Extension Field Usability Evaluation:**
  The Chrome extension is evaluated separately in a **naturalistic field deployment study** where consented participants use CalibrAI on their everyday live prompts, evaluating system stability, perceived latency, and real-world utility without deceptive interventions.

---

## 4. Dependent Variables & Psychometric Instruments

For each trial, the study harness logs behavioral telemetry and administers standardized psychometric scales:

| Metric Category | Dependent Variable | Measurement Method & Operational Definition |
|---|---|---|
| **Objective Decision Accuracy** | **Decision Correctness (%)** | Binary: Did the participant accept a correct answer or reject an incorrect answer? |
| **Calibration Metrics** | **Over-reliance Rate (%)** | Proportion of *incorrect AI responses* that the participant erroneously accepted as true. |
| **Calibration Metrics** | **Under-reliance Rate (%)** | Proportion of *correct AI responses* that the participant erroneously rejected. |
| **Cognitive Efficiency** | **Time-to-Decision ($T_{\text{dec}}$)** | Milliseconds elapsed from response presentation to final acceptance/rejection click. |
| **Subjective Trust** | **Jian et al. (2000) Trust Scale** | Validated 12-item 7-point Likert scale administered post-block measuring system trust, distrust, and dependability. |
| **Cognitive Workload** | **NASA-TLX (Raw TLX)** | 6-item scale measuring Mental Demand, Temporal Demand, Performance, Effort, and Frustration. |
| **Usability & Annoyance** | **Caveat Fatigue & Intrusiveness** | 5-point Likert items assessing visual clutter, annoyance, and disruption to reading flow. |

---

## 5. Statistical Power Analysis & Sample Size

### 5.1 Power Calculation (G*Power 3.1)
- **Statistical Model:** Repeated-measures within-between interaction ANOVA and Generalized Linear Mixed-Effects Model (GLMM with binomial logit link for binary decision accuracy).
- **Assumptions:**
  - Significance level: $\alpha = 0.05$
  - Desired statistical power: $1 - \beta = 0.85$
  - Expected effect size: Cohen's $f = 0.15$ (small-to-medium effect size, corresponding to a Cohen's $d \approx 0.35 - 0.40$, typical in HCI trust calibration literature; Buçinca et al., 2021).
  - Number of measurements: 4 conditions per participant.
  - Correlation among repeated measures: $r = 0.50$.
- **Required Sample Size:**
  $$N_{\text{calculated}} = 92\text{ participants}$$
- **Target Recruitment with Attrition Buffer:**
  To account for a 15–20% dropout rate, incomplete questionnaires, or failed attention checks:
  $$\mathbf{N_{\text{target}} = 120\text{ completed participants}}\quad (30\text{ per Latin Square sequence group})$$

### 5.2 Mixed-Effects Regression Specification
Data will be analyzed using a Generalized Linear Mixed Model (GLMM):
$$\text{logit}(P(\text{Reliance}_{ij} = 1)) = \beta_0 + \beta_1 \text{Condition}_j + \beta_2 \text{AI\_Correctness}_{ij} + \beta_3 (\text{Condition}_j \times \text{AI\_Correctness}_{ij}) + u_i + v_j + \epsilon_{ij}$$
Where:
- $u_i \sim \mathcal{N}(0, \sigma_u^2)$ is the random intercept for participant $i$.
- $v_j \sim \mathcal{N}(0, \sigma_v^2)$ is the random intercept for task item $j$.
- A significant negative interaction coefficient $\beta_3 < 0$ for Condition 3 confirms that claim-level highlighting selectively suppresses reliance when the AI response is incorrect.

---

## 6. Institutional Ethics Review Protocol (BITS Pilani IHEC)

Any empirical human-subject study involving BITS Pilani students or faculty must comply with institutional governance.

### 6.1 Governing Regulatory Framework
1. **ICMR National Ethical Guidelines for Biomedical and Health Research Involving Human Participants (2017):**
   Governs human-subject research ethics across higher education institutions in India.
2. **BITS Pilani Institutional Human Ethics Committee (IHEC):**
   The formal committee reviewing behavioral, psychological, and computer science studies involving human participants.
3. **Digital Personal Data Protection Act (DPDP Act 2023, India):**
   Governs the collection, processing, storage, and erasure of digital personal data.

### 6.2 Mandatory Ethics Application Package Components
Before recruiting participants, the study team must prepare and submit the formal IHEC dossier:

- [ ] **IHEC Standard Application Form:** Principal Investigator (faculty supervisor) + Co-Investigators (student researchers).
- [ ] **Comprehensive Study Protocol:** Rationale, hypotheses, methodology, Latin Square randomization, and data analysis plan.
- [ ] **Participant Information Sheet (PIS):** Plain-language explanation of study goals, time commitment (~30 minutes), voluntary participation, right to withdraw without academic penalty.
- [ ] **Informed Consent Form (ICF):** Explicit opt-in checkbox confirming understanding, agreement to digital data logging, and consent for anonymized research publication.
- [ ] **Deception & Debriefing Protocol:** Explains that some pre-generated answers contain deliberate factual errors to test verification, followed by an immediate educational debriefing revealing the true factual answers upon study completion.
- [ ] **Data Protection & Anonymization Plan:** All participant UUIDs are decoupled from names/emails; database records are scrubbed; raw logs contain zero biometric or academic grading data.
- [ ] **Participant Compensation:** Modest educational stipend or certificate of participation commensurate with institutional policy.

### 6.3 Participant Inclusion & Exclusion Criteria
- **Inclusion Criteria:**
  - Enrolled undergraduate or postgraduate student at BITS Pilani (or adult fluent in English).
  - Age $\ge 18$ years.
  - Regular user of AI conversational assistants (at least once per week).
- **Exclusion Criteria:**
  - Severe uncorrected visual impairment.
  - Red-green color blindness (unless high-contrast accessible pattern mode is activated).
  - Direct involvement in the design or implementation of the CalibrAI codebase.
