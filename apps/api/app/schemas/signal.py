from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Platform = Literal["chatgpt", "claude", "gemini"]
Confidence = Literal["high", "medium", "low"]
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


class SentenceFlag(BaseModel):
    sentence_index: int = Field(ge=0)
    label: str = Field(min_length=1, max_length=100)
    explanation: str | None = Field(default=None, max_length=500)


class ClaimAssessment(BaseModel):
    claim: str = Field(min_length=1, max_length=2_000)
    assessment: str = Field(min_length=1, max_length=100)
    confidence: Confidence


class SignalResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status: Literal["signal"] = "signal"
    confidence: Confidence
    score: float = Field(ge=0, le=1)
    sentence_flags: list[SentenceFlag] = Field(default_factory=list, alias="sentenceFlags")
    claim_assessments: list[ClaimAssessment] = Field(default_factory=list, alias="claimAssessments")
    explanation: str = Field(max_length=1_000)
    model_version: str = Field(alias="modelVersion", min_length=1, max_length=100)
    processing_latency_ms: int = Field(alias="processingLatencyMs", ge=0)
