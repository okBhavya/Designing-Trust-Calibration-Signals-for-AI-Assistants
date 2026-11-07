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

    @model_validator(mode="after")
    def validate_adjudication(self) -> "AdjudicationRecord":
        if self.reviewed_at.tzinfo is None:
            raise ValueError("reviewedAt must include a timezone")
        return self


class DatasetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

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

    @model_validator(mode="after")
    def validate_dataset_record(self) -> "DatasetRecord":
        if self.answer_timestamp.tzinfo is None:
            raise ValueError("answerTimestamp must include a timezone")
        for annotation in self.annotations:
            for claim in annotation.claims:
                if claim.time_sensitive:
                    for evidence in claim.evidence:
                        if evidence.published_at and evidence.published_at > self.answer_timestamp:
                            raise ValueError("Time-sensitive evidence cannot be published after the answer timestamp")
        return self


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    dataset_version: str = Field(min_length=1, alias="datasetVersion")
    generated_at: datetime = Field(alias="generatedAt")
    record_count: int = Field(ge=0, alias="recordCount")
    partition_counts: dict[str, int] = Field(alias="partitionCounts")
    label_counts: dict[str, int] = Field(alias="labelCounts")
    provenance: list[str] = Field(default_factory=list)
    content_digest: str = Field(pattern=r"^[a-f0-9]{64}$", alias="contentDigest")


class DatasetBundle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: str = Field(min_length=1, alias="schemaVersion")
    dataset_version: str = Field(min_length=1, alias="datasetVersion")
    records: list[DatasetRecord]
    manifest: DatasetManifest | None = None
