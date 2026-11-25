# Validation question sources

Record for `data/validation/questions.jsonl` and the files derived from it
(`results.jsonl`, `report.md`, `reliability_diagram.png`, and the study items in
`data/questions.json`), following
[the source approval checklist](../../docs/PHASE_2C_2_SOURCE_APPROVAL.md).

## Status: NOT APPROVED

This record was prepared by the engineering team. Under the checklist only an
authorized study owner may mark a source `approved`. Until that happens:

- these questions may be used for **engineering validation of the signal only**;
- they must **not** be shown to study participants, so `data/questions.json` is a
  candidate set, not an approved study instrument;
- they must **not** enter the annotation dataset or its calibration / held-out
  partitions.

| Field | NQ-open | SimpleQA |
|---|---|---|
| Approval ID | pending | pending |
| Approval decision | pending: neither approved, rejected nor blocked | pending |
| Approving authority | to be named by the study owner | to be named by the study owner |
| Dataset version | Hugging Face `google-research-datasets/nq_open`, revision `5dd9790a83002ad084ddeb7c420dc716852c6f28`, `validation` split (3,610 rows) | `simple_qa_test_set.csv`, SHA-256 `feee3f7e7db3617e94e8fcf1977b756ec420ef8568f4e0fcbbe0e92e9d5fc032` (4,326 rows) |
| Source owner | Google Research (Natural Questions); open-domain version by Lee et al. | OpenAI |
| License | CC BY-SA 3.0 (dataset card) | MIT (`openai/simple-evals` repository, "Copyright (c) 2024 OpenAI") |
| Retrieved | 2026-11-24T20:54:11Z via the Hugging Face datasets-server rows API | 2026-11-24T20:54:11Z from `openaipublic.blob.core.windows.net/simple-evals/` |
| Sampled | 60 of 3,561 after the time-sensitivity filter | 40 of 4,326 |

Machine-readable provenance: [`build_info.json`](build_info.json) (seed, URLs,
revision, hashes, filter, and the SHA-256 of `questions.jsonl`).

## Ownership and permitted use

- [x] Ownership is identified (table above).
- [x] License recorded: CC BY-SA 3.0 and MIT both permit research use, copying and
      redistribution.
- [x] Redistribution terms:
      - **NQ-open is share-alike.** The question text and gold answers in
        `questions.jsonl`, `results.jsonl` and `data/questions.json` are adaptations of
        NQ-open, so they must keep CC BY-SA 3.0 and this attribution.
      - **SimpleQA requires the MIT notice** to be kept with copies.
- [ ] **Owner:** retention duration and deletion procedure. The files hold only
      public questions and model-generated answers; no participant data.

## Provenance and time

- [x] Every question has a traceable origin: its `id` is the source row
      (`nq-<row index>` in the NQ-open validation split, `simpleqa-<row index>` in the CSV).
- [x] Answer timestamps. The AI answers are generated during the validation run;
      each row of `results.jsonl` records `finished_at` (UTC) and the answering
      model.
- [x] Time-sensitive questions are excluded from NQ-open by a keyword filter
      (`current`, `latest`, `now`, `this year`, `recent`, ...; full pattern in
      `build_info.json`). SimpleQA was built to have time-invariant answers.
- [ ] **Owner:** confirm that the gold answers are acceptable as ground truth. NQ-open
      has known answer gaps and some ambiguous questions; see the report's limitations.

## Independence and evidence quality

Not applicable in the checklist's sense: this set has no evidence passages. Labels
come from gold answers, by normalized string match or an LLM judge. `label_source`
records which one decided each label.

## Privacy and governance

- [x] The questions are public benchmark items. A spot check found no personal data
      beyond public figures named in trivia questions.
- [x] No participant identifiers are involved.
- [ ] **Owner:** approve reviewer and participant access before any study use.
- [ ] **Owner:** approve where these files are stored and for how long (currently the
      project repository).

## Reproducibility

- [x] Rebuild: `python apps/api/scripts/validate.py --build-questions` (seed
      20261125). The dataset revision and CSV hash above detect upstream changes.
- [x] `questions.jsonl` has a content digest (`build_info.json`).
- [x] Each `results.jsonl` row records the model version, tokens, cost and timestamp.
- [x] Partition: engineering validation only, not part of any annotation partition.

## Attribution

- **Natural Questions:** Kwiatkowski et al., "Natural Questions: a Benchmark for
  Question Answering Research", TACL 2019. Open-domain subset: Lee et al., "Latent
  Retrieval for Weakly Supervised Open Domain Question Answering", ACL 2019. Licensed
  under CC BY-SA 3.0 (https://creativecommons.org/licenses/by-sa/3.0/). The
  adaptation here selects 60 validation questions; text and answers are unchanged.
- **SimpleQA:** Wei et al., "Measuring short-form factuality in large language
  models", OpenAI 2024. MIT License, Copyright (c) 2024 OpenAI. The adaptation here
  selects 40 questions; text and answers are unchanged.

## Rejected alternative

TriviaQA was considered and not used. Its dataset card lists the license as
"unknown", and states that the University of Washington does not own the copyright
of the questions, so it cannot meet the checklist's license requirement.
