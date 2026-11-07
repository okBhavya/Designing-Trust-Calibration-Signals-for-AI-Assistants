from __future__ import annotations

import difflib
import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Partition(StrEnum):
    DEVELOPMENT = "development"
    CALIBRATION = "calibration"
    TEST = "test"


class ClaimOutcome(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AnswerLabel(StrEnum):
    RELIABLE = "reliable"
    UNRELIABLE = "unreliable"
    INDETERMINATE = "indeterminate"


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1, alias="sourceId")
    url: str = Field(pattern=r"^https?://", min_length=1)
    publisher: str = Field(min_length=1)
    independence_group: str = Field(min_length=1, alias="independenceGroup")
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    retrieved_at: datetime = Field(alias="retrievedAt")
    passage: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_times(self) -> "EvidenceRecord":
        if self.published_at and self.published_at > self.retrieved_at:
            raise ValueError("publishedAt cannot be later than retrievedAt")
        for value in (self.published_at, self.retrieved_at):
            if value and value.tzinfo is None:
                raise ValueError("Evidence timestamps must include a timezone")
        return self


class ClaimAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim_id: str = Field(min_length=1, alias="claimId")
    sentence_index: int = Field(ge=0, alias="sentenceIndex")
    text: str = Field(min_length=1)
    materiality: str = Field(pattern=r"^(high|medium|low)$")
    time_sensitive: bool = Field(alias="timeSensitive")
    outcome: ClaimOutcome | None = None
    evidence: list[EvidenceRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence(self) -> "ClaimAnnotation":
        if self.outcome in {ClaimOutcome.SUPPORTED, ClaimOutcome.CONTRADICTED} and not self.evidence:
            raise ValueError("Supported or contradicted claims require evidence provenance")
        return self


class AnnotationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    annotation_id: str = Field(min_length=1, alias="annotationId")
    item_id: str = Field(min_length=1, alias="itemId")
    reviewer_id: str = Field(pattern=r"^reviewer-[A-Za-z0-9_-]+$", alias="reviewerId")
    annotation_version: int = Field(ge=1, alias="annotationVersion")
    reviewed_at: datetime = Field(alias="reviewedAt")
    claims: list[ClaimAnnotation] = Field(default_factory=list)
    answer_label: AnswerLabel | None = Field(default=None, alias="answerLabel")
    adjudication_decision: AnswerLabel | None = Field(default=None, alias="adjudicationDecision")
    adjudication_reason: str | None = Field(default=None, alias="adjudicationReason")
    supersedes_annotation_id: str | None = Field(default=None, alias="supersedesAnnotationId")
    exclusion_reason: str | None = Field(default=None, alias="exclusionReason")

    @model_validator(mode="after")
    def validate_record(self) -> "AnnotationRecord":
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewedAt must include a timezone")
        if self.adjudication_decision or self.adjudication_reason:
            raise ValueError("Original annotations cannot contain adjudication fields")
        if self.exclusion_reason and not self.exclusion_reason.strip():
            raise ValueError("exclusionReason cannot be empty")
        if self.adjudication_decision and self.answer_label is not None:
            raise ValueError("Final adjudicated labels must not overwrite original answerLabel")
        return self


class AdjudicationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    adjudication_id: str = Field(min_length=1, alias="adjudicationId")
    item_id: str = Field(min_length=1, alias="itemId")
    annotation_id: str = Field(min_length=1, alias="annotationId")
    reviewer_id: str = Field(pattern=r"^reviewer-[A-Za-z0-9_-]+$", alias="reviewerId")
    annotation_version: int = Field(ge=1, alias="annotationVersion")
    reviewed_at: datetime = Field(alias="reviewedAt")
    decision: AnswerLabel = Field(alias="adjudicationDecision")
    reason: str = Field(min_length=1, alias="adjudicationReason")
    supersedes_annotation_id: str | None = Field(default=None, alias="supersedesAnnotationId")

    @model_validator(mode="after")
    def validate_record(self) -> "AdjudicationRecord":
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewedAt must include a timezone")
        return self


class DatasetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    item_id: str = Field(min_length=1, alias="itemId")
    dataset_version: str = Field(min_length=1, alias="datasetVersion")
    partition: Partition
    prompt_hash: str = Field(pattern=r"^[a-f0-9]{64}$", alias="promptHash")
    answer_hash: str = Field(pattern=r"^[a-f0-9]{64}$", alias="answerHash")
    prompt: str | None = None
    answer: str | None = None
    answer_timestamp: datetime = Field(alias="answerTimestamp")
    annotations: list[AnnotationRecord] = Field(default_factory=list)
    adjudication_history: list[AdjudicationRecord] = Field(default_factory=list, alias="adjudicationHistory")
    final_answer_label: AnswerLabel | None = Field(default=None, alias="finalAnswerLabel")
    expected_high_materiality_claim_ids: list[str] = Field(
        default_factory=list, alias="expectedHighMaterialityClaimIds"
    )
    exclusion_reason: str | None = Field(default=None, alias="exclusionReason")

    @model_validator(mode="after")
    def validate_record(self) -> "DatasetRecord":
        if self.answer_timestamp.tzinfo is None:
            raise ValueError("answerTimestamp must include a timezone")
        for annotation in self.annotations:
            for claim in annotation.claims:
                for evidence in claim.evidence:
                    if (
                        claim.time_sensitive
                        and evidence.published_at
                        and evidence.published_at > self.answer_timestamp
                    ):
                        raise ValueError("Time-sensitive evidence cannot be published after the answer timestamp")
        claim_ids = {claim.claim_id for annotation in self.annotations for claim in annotation.claims}
        missing = set(self.expected_high_materiality_claim_ids) - claim_ids
        if missing:
            raise ValueError(f"Missing high-materiality claims: {sorted(missing)}")
        if self.final_answer_label and not self.annotations:
            raise ValueError("Final answer labels require reviewer annotations")
        annotation_ids = {annotation.annotation_id for annotation in self.annotations}
        for adjudication in self.adjudication_history:
            if adjudication.item_id != self.item_id:
                raise ValueError("Adjudication itemId must match dataset itemId")
            if adjudication.annotation_id not in annotation_ids:
                raise ValueError("Adjudication must reference an original annotation")
        return self


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_version: str = Field(min_length=1, alias="datasetVersion")
    generated_at: datetime = Field(alias="generatedAt")
    record_count: int = Field(ge=0, alias="recordCount")
    partition_counts: dict[str, int] = Field(alias="partitionCounts")
    label_counts: dict[str, int] = Field(alias="labelCounts")
    provenance: list[str] = Field(min_length=1)
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$", alias="contentDigest")


class DatasetBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(min_length=1, alias="schemaVersion")
    dataset_version: str = Field(min_length=1, alias="datasetVersion")
    records: list[DatasetRecord]
    manifest: DatasetManifest | None = None


def _similarity(left: DatasetRecord, right: DatasetRecord) -> float:
    left_value = left.answer or left.answer_hash
    right_value = right.answer or right.answer_hash
    return difflib.SequenceMatcher(None, left_value.lower().strip(), right_value.lower().strip()).ratio()


def validate_dataset(records: Iterable[DatasetRecord]) -> list[str]:
    items = list(records)
    errors: list[str] = []
    seen_items: set[str] = set()
    seen_hashes: dict[str, tuple[str, Partition]] = {}
    seen_annotations: set[str] = set()
    for record in items:
        if record.item_id in seen_items:
            errors.append(f"duplicate itemId: {record.item_id}")
        seen_items.add(record.item_id)
        if record.final_answer_label and record.final_answer_label == AnswerLabel.INDETERMINATE:
            pass
        for annotation in record.annotations:
            if annotation.annotation_id in seen_annotations:
                errors.append(f"duplicate annotationId: {annotation.annotation_id}")
            seen_annotations.add(annotation.annotation_id)
        claim_outcomes: dict[str, set[ClaimOutcome | None]] = {}
        answer_labels: set[AnswerLabel | None] = set()
        for annotation in record.annotations:
            answer_labels.add(annotation.answer_label)
            for claim in annotation.claims:
                claim_outcomes.setdefault(claim.claim_id, set()).add(claim.outcome)
        if len(answer_labels - {None}) > 1:
            errors.append(f"conflicting reviewer answer labels: {record.item_id}")
        if any(len(outcomes - {None}) > 1 for outcomes in claim_outcomes.values()):
            errors.append(f"conflicting reviewer claim labels: {record.item_id}")
        for annotation in record.annotations:
            if annotation.supersedes_annotation_id and annotation.supersedes_annotation_id not in seen_annotations:
                errors.append(
                    f"superseded annotation is not present before use: {annotation.annotation_id}"
                )
        for field_name, value in (("promptHash", record.prompt_hash), ("answerHash", record.answer_hash)):
            previous = seen_hashes.get(value)
            if previous and previous[1] != record.partition:
                errors.append(
                    f"partition leakage for {field_name}: {previous[0]} and {record.item_id}"
                )
            seen_hashes[value] = (record.item_id, record.partition)
        for other in items:
            if other.item_id >= record.item_id or other.partition == record.partition:
                continue
            if _similarity(record, other) >= 0.95:
                errors.append(f"near-duplicate records across partitions: {record.item_id} and {other.item_id}")
    return sorted(set(errors))


def build_manifest(bundle: DatasetBundle) -> DatasetManifest:
    partition_counts = {partition.value: 0 for partition in Partition}
    label_counts = {label.value: 0 for label in AnswerLabel}
    for record in bundle.records:
        partition_counts[record.partition.value] += 1
        if record.final_answer_label:
            label_counts[record.final_answer_label.value] += 1
    errors = validate_dataset(bundle.records)
    if errors:
        raise ValueError("; ".join(errors))
    canonical = json.dumps(
        bundle.model_dump(mode="json", by_alias=True, exclude={"manifest"}),
        sort_keys=True,
        separators=(",", ":"),
    )
    return DatasetManifest(
        datasetVersion=bundle.dataset_version,
        generatedAt=datetime.now(timezone.utc),
        recordCount=len(bundle.records),
        partitionCounts=partition_counts,
        labelCounts=label_counts,
        provenance=["validated-by-calibrai-dataset-store"],
        contentDigest=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


def export_dataset(bundle: DatasetBundle, path: str | Path) -> None:
    manifest = build_manifest(bundle)
    output = bundle.model_copy(update={"manifest": manifest})
    Path(path).write_text(
        json.dumps(output.model_dump(mode="json", by_alias=True), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def import_dataset(path: str | Path) -> DatasetBundle:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    bundle = DatasetBundle.model_validate(payload)
    calculated = build_manifest(bundle)
    if bundle.manifest and bundle.manifest.model_dump(exclude={"generated_at"}) != calculated.model_dump(
        exclude={"generated_at"}
    ):
        raise ValueError("Dataset manifest does not match records")
    return bundle.model_copy(update={"manifest": calculated})


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
