from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Platform = Literal["chatgpt", "claude", "gemini"]
Confidence = Literal["high", "medium", "low"]
AssessmentState = Literal[
    "high", "medium", "low", "insufficient_evidence", "unavailable", "abstained"
]
AnswerHash = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class SignalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant_id: UUID
    platform: Platform
    answer_hash: AnswerHash
    prompt: str | None = Field(default=None, max_length=50_000)
    answer: str | None = Field(default=None, max_length=200_000)
    session_id: UUID | None = None
    metadata: dict[str, str] = Field(default_factory=dict, max_length=20)

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, str]) -> dict[str, str]:
        forbidden = {"prompt", "answer", "conversation", "response", "token", "secret"}
        if any(key.lower() in forbidden for key in value):
            raise ValueError("Raw conversation and credential metadata are not accepted")
        if any(len(key) > 64 or len(item) > 256 for key, item in value.items()):
            raise ValueError("Metadata keys and values are too long")
        return value


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
    explanation: str = Field(max_length=1_000)
    model_version: str = Field(alias="modelVersion", min_length=1, max_length=100)
    processing_latency_ms: int = Field(alias="processingLatencyMs", ge=0)
