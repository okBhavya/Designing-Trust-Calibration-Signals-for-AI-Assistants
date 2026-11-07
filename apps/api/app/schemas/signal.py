from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Platform = Literal["chatgpt", "claude", "gemini"]
Confidence = Literal["high", "medium", "low"]
AssessmentState = Literal[
    "high", "medium", "low", "insufficient_evidence", "unavailable", "abstained"
]
AnswerHash = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class SignalRequest(BaseModel):
    participant_id: UUID
    platform: Platform
    answer_hash: AnswerHash
    prompt: str | None = None
    answer: str | None = None
    session_id: UUID | None = None
    metadata: dict[str, str] = Field(default_factory=dict, max_length=20)


class SentenceFlag(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    sentence_index: int = Field(ge=0)
    label: str = Field(min_length=1, max_length=100)
    explanation: str | None = Field(default=None, max_length=500)
    claim_ids: list[str] = Field(default_factory=list, alias="claimIds")


class ClaimAssessment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    claim_id: str | None = Field(default=None, alias="claimId")
    claim: str = Field(min_length=1, max_length=2_000)
    assessment: str = Field(min_length=1, max_length=100)
    confidence: Confidence
    evidence_strength: str | None = Field(default=None, alias="evidenceStrength")
    uncertainty: float | None = Field(default=None, ge=0, le=1)
    supporting_source_ids: list[str] = Field(default_factory=list, alias="supportingSourceIds")
    contradicting_source_ids: list[str] = Field(default_factory=list, alias="contradictingSourceIds")


class SignalResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["signal"] = "signal"
    confidence: Confidence | None = None
    assessment_state: AssessmentState = Field(default="abstained", alias="assessmentState")
    score: float = Field(ge=0, le=1)
    sentence_flags: list[SentenceFlag] = Field(default_factory=list, alias="sentenceFlags")
    claim_assessments: list[ClaimAssessment] = Field(default_factory=list, alias="claimAssessments")
    explanation: str = Field(min_length=1, max_length=1_000)
    model_version: str = Field(min_length=1, max_length=50, alias="modelVersion")
    processing_latency_ms: int = Field(ge=0, alias="processingLatencyMs")
