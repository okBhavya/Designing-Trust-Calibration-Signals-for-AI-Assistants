from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

StudyCondition = Literal["baseline", "A", "C"]
SignalLevel = Literal["high", "medium", "low", "insufficient_evidence", "abstained", "unavailable"]
Instrument = Literal["demographics", "trust"]

AGE_BANDS = ("18-24", "25-34", "35-44", "45-54", "55-64", "65+", "prefer_not_to_say")
TRUST_ITEMS = tuple(f"trust_{number}" for number in range(1, 6))


class StudyEnrollRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enrollment_code: str = Field(min_length=1, max_length=256)
    # The consent text version the participant was shown; must equal the server's current version.
    consent_version: str = Field(min_length=1, max_length=100)
    consent: Literal[True]


class StudyEnrollResponse(BaseModel):
    participant_id: UUID
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    condition: StudyCondition
    consent_version: str


class StudyTrialRequest(BaseModel):
    """One main trial. Practice trials are never sent."""

    model_config = ConfigDict(extra="forbid")

    participant_id: UUID
    question_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.:-]+$")
    position: int = Field(ge=0, le=999, description="0-based place in this participant's randomized order")
    condition: StudyCondition
    ai_correct: bool
    # The item's pre-computed signal, recorded in every condition (baseline participants don't see it).
    signal_level: SignalLevel | None = None
    signal_score: float | None = Field(default=None, ge=0, le=1)
    shown_at: AwareDatetime
    decided_at: AwareDatetime
    decision: Literal["accept", "reject"]
    self_confidence: int = Field(ge=1, le=5)
    final_correct: bool

    @model_validator(mode="after")
    def check_consistency(self) -> "StudyTrialRequest":
        if self.decided_at < self.shown_at:
            raise ValueError("decided_at cannot be earlier than shown_at")
        if self.final_correct != ((self.decision == "accept") == self.ai_correct):
            raise ValueError("final_correct must be true exactly when the decision matches ai_correct")
        return self


class StudyQuestionnaireRequest(BaseModel):
    """demographics: age_band + ai_experience (1-5). trust: trust_1..trust_5 (Likert 1-7)."""

    model_config = ConfigDict(extra="forbid")

    participant_id: UUID
    instrument: Instrument
    # Strict: a JSON true or "4" is not silently read as a Likert value.
    responses: dict[str, StrictInt | StrictStr] = Field(max_length=20)

    @model_validator(mode="after")
    def check_items(self) -> "StudyQuestionnaireRequest":
        responses = self.responses
        if self.instrument == "demographics":
            expected = {"age_band", "ai_experience"}
            if set(responses) != expected:
                raise ValueError(f"demographics needs exactly {sorted(expected)}")
            if responses["age_band"] not in AGE_BANDS:
                raise ValueError(f"age_band must be one of {list(AGE_BANDS)}")
            _check_scale(responses, "ai_experience", 1, 5)
        else:
            if set(responses) != set(TRUST_ITEMS):
                raise ValueError(f"trust needs exactly {list(TRUST_ITEMS)}")
            for item in TRUST_ITEMS:
                _check_scale(responses, item, 1, 7)
        return self


def _check_scale(responses: dict[str, int | str], item: str, low: int, high: int) -> None:
    value = responses[item]
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{item} must be an integer from {low} to {high}")


class StudyRecordResponse(BaseModel):
    id: UUID
    # False when this exact record was already stored (a retried request): nothing new was written.
    created: bool
