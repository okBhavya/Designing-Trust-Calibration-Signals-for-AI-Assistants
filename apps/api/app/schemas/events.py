from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.signal import Platform, AnswerHash

EventType = Literal["signal_shown", "explanation_opened", "signal_dismissed", "signal_hovered"]


class EventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant_id: UUID
    event_type: EventType
    platform: Platform | None = None
    answer_hash: AnswerHash | None = None
    session_id: UUID | None = None
    trial_id: UUID | None = None
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


class EventResponse(BaseModel):
    id: UUID
    accepted: bool = True
