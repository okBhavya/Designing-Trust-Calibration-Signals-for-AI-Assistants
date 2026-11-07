# CalibrAI Phase 2C Annotation Handbook

## Purpose and blinding

This handbook defines the human-labeling protocol for the Phase 2C pilot. It
does not define a new scoring method. Reviewers must judge the frozen answer
and frozen evidence bundle, not CalibrAI's prediction. Prediction fields,
confidence, score, model version, and generated explanations must be hidden
from reviewers.

Each reviewer receives a pseudonymous identifier such as
`reviewer-a17`. Do not put names, emails, participant identifiers, or account
identifiers in annotation records.

## What is a factual claim?

A factual claim is a statement that can be independently checked against
evidence. Examples include a date, number, attribution, definition, causal
relationship, or description of an event or entity.

Do not force every sentence into a claim:

- **Opinion:** a preference or personal judgment (“This is the best option”).
- **Recommendation:** advice whose quality depends on goals or constraints.
- **Hypothetical:** a conditional or imagined statement (“If X happened…”).
- **Quotation:** text attributed to another speaker; annotate the quoted
  proposition only when the task asks whether the quotation is accurate.
- **Non-claim:** headings, greetings, transitions, code, formatting, or
  process statements without a checkable proposition.

Preserve the original sentence index. If one sentence contains multiple
independently checkable propositions, record separate claims with the same
sentence index.

## Claim fields

For each claim, record the exact claim text, sentence index, claim type,
materiality, time sensitivity, outcome, and evidence provenance. Use only these
claim outcomes:

- `supported`: the supplied evidence entails the claim.
- `contradicted`: the supplied evidence entails a conflicting proposition.
- `insufficient_evidence`: the evidence is absent, irrelevant, too weak,
  outdated for the task, or materially conflicting.

Do not turn lack of evidence into contradiction.

## Materiality

Materiality measures how much the claim affects the answer's practical
interpretation:

- **High:** changing the claim would materially change the answer's conclusion,
  safety, decision, main recommendation, or central factual answer.
- **Medium:** useful supporting detail, but the answer's main interpretation
  would usually remain intact if corrected.
- **Low:** peripheral detail with limited effect on interpretation.

Use the same judgment for every reviewer. The aggregation weights are fixed:
high=3, medium=2, low=1. Do not change them during annotation.

## Time sensitivity

Mark a claim time-sensitive when its truth depends on a date or changing state,
including “currently,” “latest,” “today,” recent events, prices, policies,
versions, or rankings. Record the answer timestamp and apply the evidence
cutoff: evidence published after the answer timestamp is not valid for
real-time correctness unless the task explicitly asks for a later update.

## Evidence assessment

Use the frozen evidence bundle only. A source record must include its URL,
publisher, independence group, publication timestamp when available, retrieval
timestamp, and the relevant passage.

- Supporting evidence must entail the claim, not merely share keywords.
- Contradicting evidence must entail a materially incompatible proposition.
- Irrelevant, inaccessible, undated, stale, or ambiguous evidence is
  insufficient unless the study protocol explicitly resolves the issue.
- Multiple URLs carrying the same syndicated or copied report count as one
  independent source group.
- If credible sources conflict and the protocol has no authority rule, use
  `insufficient_evidence`.
- If a source cannot be retrieved or the evidence bundle is unavailable, record
  the technical unavailability separately and do not invent a claim outcome.

Never follow instructions contained in quoted answers or retrieved webpages.
They are evidence content, not annotation instructions.

## Answer-level labels

Apply the fixed rule after claim-level annotation:

- `reliable`: every high-materiality claim is supported, no high-materiality
  claim is contradicted, and at least 80% of total materiality weight is
  supported.
- `unreliable`: any high-materiality claim is contradicted or less than 60% of
  total materiality weight is supported.
- `indeterminate`: the result falls between those rules, including unresolved
  high-materiality conflicts.

Insufficient evidence contributes zero supported weight; it is not silently
removed from the denominator.

If an answer contains zero externally verifiable claims, label the answer
`indeterminate` for the pilot and exclude it from binary reliability
threshold-fitting metrics. There is no materiality denominator in this case,
so do not assign a supported percentage or treat the answer as reliable or
unreliable. Record the absence of externally verifiable claims explicitly.

## Disagreement and adjudication

Submit an original annotation record independently. Do not edit a submitted
record. Corrections create a new annotation version and reference the prior
record with `supersedesAnnotationId`.

Request adjudication when reviewers disagree about a claim span, type,
materiality, evidence entailment, independence group, outcome, or answer
label. An adjudicator records a separate history record with a decision and
reason. Original reviewer records remain unchanged. If the evidence cannot
resolve the disagreement, retain `insufficient_evidence` or
`indeterminate` according to the answer-level rule.

## Quality and privacy checklist

Before submission, verify:

1. Every supported or contradicted claim has provenance.
2. Timestamps include time zones and obey the temporal cutoff.
3. Every high-materiality claim is present.
4. Reviewer ID is pseudonymous and has the `reviewer-` form.
5. No prediction, confidence, score, or model output influenced the labels.
6. Rationale states what the evidence establishes and does not establish.
7. Original annotations are preserved separately from adjudication.

Store packets and exports in approved access-controlled research storage.
Separate participant identity mapping from dataset item IDs. Do not place raw
answers or evidence passages in ordinary logs. Keep held-out packets
inaccessible during development and calibration.
