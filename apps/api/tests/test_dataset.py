from datetime import datetime, timezone

import pytest

from app.dataset import (
    AnswerLabel,
    AdjudicationRecord,
    ClaimOutcome,
    DatasetBundle,
    DatasetRecord,
    AnnotationRecord,
    ClaimAnnotation,
    EvidenceRecord,
    Partition,
    build_manifest,
    export_dataset,
    hash_text,
    import_dataset,
    validate_dataset,
)


def record(item_id: str, partition: Partition, answer: str, label: AnswerLabel | None = None):
    reviewed = datetime(2026, 11, 1, tzinfo=timezone.utc)
    claim = ClaimAnnotation(
        claimId=f"{item_id}-claim",
        sentenceIndex=0,
        text=answer,
        materiality="high",
        timeSensitive=False,
        outcome=ClaimOutcome.INSUFFICIENT_EVIDENCE,
    )
    annotation = AnnotationRecord(
        annotationId=f"{item_id}-annotation",
        itemId=item_id,
        reviewerId="reviewer-pseudonym-1",
        annotationVersion=1,
        reviewedAt=reviewed,
        claims=[claim],
        answerLabel=label,
    )
    return DatasetRecord(
        itemId=item_id,
        datasetVersion="2c-dev-1",
        partition=partition,
        promptHash=hash_text(f"prompt-{item_id}"),
        answerHash=hash_text(answer),
        prompt=f"Prompt {item_id}",
        answer=answer,
        answerTimestamp=reviewed,
        annotations=[annotation],
        finalAnswerLabel=label,
    )


def test_dataset_round_trip_and_manifest(tmp_path):
    bundle = DatasetBundle(
        schemaVersion="1",
        datasetVersion="2c-dev-1",
        records=[record("item-1", Partition.DEVELOPMENT, "A claim.", AnswerLabel.INDETERMINATE)],
    )
    path = tmp_path / "dataset.json"
    export_dataset(bundle, path)
    loaded = import_dataset(path)
    assert loaded.manifest is not None
    assert loaded.manifest.record_count == 1
    assert loaded.manifest.partition_counts["development"] == 1
    assert loaded.manifest.content_digest == build_manifest(bundle).content_digest


def test_partition_leakage_and_near_duplicate_detection():
    first = record("item-1", Partition.DEVELOPMENT, "The same answer.")
    second = record("item-2", Partition.TEST, "The same answer.")
    errors = validate_dataset([first, second])
    assert any("partition leakage" in error for error in errors)
    assert any("near-duplicate" in error for error in errors)


def test_supported_claim_requires_provenance():
    with pytest.raises(ValueError, match="require evidence provenance"):
        ClaimAnnotation(
            claimId="claim-1",
            sentenceIndex=0,
            text="A factual claim.",
            materiality="high",
            timeSensitive=False,
            outcome=ClaimOutcome.SUPPORTED,
        )


def test_adjudication_is_separate_and_requires_reason():
    with pytest.raises(ValueError, match="Original annotations"):
        AnnotationRecord(
            annotationId="final-1",
            itemId="item-1",
            reviewerId="reviewer-adjudicator-pseudonym",
            annotationVersion=1,
            reviewedAt=datetime(2026, 11, 1, tzinfo=timezone.utc),
            adjudicationDecision=AnswerLabel.RELIABLE,
        )


def test_adjudication_history_references_original_annotation():
    base = record("item-1", Partition.DEVELOPMENT, "Claim.")
    adjudication = AdjudicationRecord(
        adjudicationId="adj-1",
        itemId="item-1",
        annotationId="item-1-annotation",
        reviewerId="reviewer-adjudicator-pseudonym",
        annotationVersion=1,
        reviewedAt=datetime(2026, 11, 2, tzinfo=timezone.utc),
        adjudicationDecision=AnswerLabel.INDETERMINATE,
        adjudicationReason="Reviewers disagreed.",
    )
    updated = base.model_copy(update={"adjudication_history": [adjudication]})
    assert updated.adjudication_history[0].annotation_id == base.annotations[0].annotation_id


def test_original_annotation_is_immutable():
    annotation = record("item-1", Partition.DEVELOPMENT, "Claim.").annotations[0]
    with pytest.raises((TypeError, ValueError)):
        annotation.answer_label = AnswerLabel.RELIABLE


def test_conflicting_reviewer_labels_are_reported():
    first = record("item-1", Partition.DEVELOPMENT, "Claim.")
    second_annotation = first.annotations[0].model_copy(
        deep=True,
        update={
            "annotation_id": "item-1-annotation-2",
            "answer_label": AnswerLabel.UNRELIABLE,
            "claims": [
                first.annotations[0].claims[0].model_copy(update={"outcome": ClaimOutcome.CONTRADICTED})
            ],
        },
    )
    combined = first.model_copy(deep=True, update={"annotations": [first.annotations[0], second_annotation]})
    errors = validate_dataset([combined])
    assert any("conflicting reviewer" in error for error in errors)


def test_time_sensitive_evidence_cannot_postdate_answer():
    base = record("item-1", Partition.CALIBRATION, "Current fact.").model_dump(by_alias=True)
    base.pop("annotations")
    annotation_base = record("item-1", Partition.CALIBRATION, "Current fact.").annotations[0].model_dump(
        by_alias=True
    )
    annotation_base.pop("claims")
    with pytest.raises(ValueError, match="published after"):
        DatasetRecord(
            **base,
            annotations=[
                AnnotationRecord(
                    **annotation_base,
                    claims=[
                        ClaimAnnotation(
                            claimId="item-1-claim",
                            sentenceIndex=0,
                            text="Current fact.",
                            materiality="high",
                            timeSensitive=True,
                            outcome=ClaimOutcome.SUPPORTED,
                            evidence=[
                                EvidenceRecord(
                                    sourceId="source-1",
                                    url="https://example.test/source",
                                    publisher="Example",
                                    independenceGroup="example",
                                    publishedAt=datetime(2026, 12, 1, tzinfo=timezone.utc),
                                    retrievedAt=datetime(2026, 12, 2, tzinfo=timezone.utc),
                                    passage="Evidence",
                                )
                            ],
                        )
                    ],
                )
            ],
        )
