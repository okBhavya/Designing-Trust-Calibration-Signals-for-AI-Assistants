from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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


class EventResponse(BaseModel):
    id: UUID
    accepted: bool = True
