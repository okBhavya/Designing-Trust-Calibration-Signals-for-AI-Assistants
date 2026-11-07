# CalibrAI Phase 2C.2 Source Approval Checklist

## Status

No source or evidence bundle is approved by this repository. A source may be
used for the pilot only after an authorized study owner completes this
checklist and records supporting evidence. This document is a gate, not an
approval record.

## Required approval record

For each dataset family, source, and evidence bundle, record:

- approval ID, dataset version, and approving authority;
- source owner and organization;
- license or written permission for research use;
- permitted copying, passage storage, reviewer access, and redistribution;
- retention duration and deletion procedure;
- provenance of the prompt, AI answer, and each evidence passage;
- answer timestamp, publication timestamp, and retrieval timestamp;
- retrieval method and frozen-bundle creation timestamp;
- publisher, authorship, cited origin, and independence group;
- personal-data and sensitive-data review outcome;
- reproducibility instructions, content digest, and bundle location;
- partition assignment and confirmation that the source is not held out.

## Approval checks

### Ownership and permitted use

- [ ] Ownership is identified and documented.
- [ ] License or written research permission is stored with the approval record.
- [ ] Passage length and redistribution restrictions permit reviewer access.
- [ ] Retention and deletion obligations are understood.

### Provenance and time

- [ ] The prompt and answer have traceable origin.
- [ ] The answer timestamp includes a timezone.
- [ ] Each source has a URL and publisher.
- [ ] Publication timestamp is recorded when available.
- [ ] Retrieval timestamp includes a timezone.
- [ ] Time-sensitive evidence does not postdate the answer timestamp unless the
      task explicitly permits later updates.

### Independence and evidence quality

- [ ] Publisher ownership and authorship are recorded.
- [ ] Cited origin and text-similarity checks are completed.
- [ ] Syndicated or copied material shares an independence group.
- [ ] The relevant passage entails the claim or is explicitly insufficient.
- [ ] Conflicting evidence is preserved rather than silently discarded.

### Privacy and governance

- [ ] Personal data and sensitive data were reviewed and minimized.
- [ ] Participant identifiers are separated from dataset item IDs.
- [ ] Reviewer access is approved and prediction fields are excluded.
- [ ] The storage location is access-controlled and its retention is approved.
- [ ] Export protection and deletion procedures are documented.

### Reproducibility

- [ ] The evidence bundle is frozen and immutable for both reviewers.
- [ ] The bundle has a content digest.
- [ ] URLs, passages, metadata, and retrieval dates can be replayed or audited.
- [ ] The packet records dataset version, item ID, and partition.

## Approval decision

An approver may mark a bundle `approved`, `rejected`, or `blocked` only with a
dated rationale and supporting references. Until the decision is `approved`,
the bundle must not be sent to reviewers and must not enter the pilot dataset.
