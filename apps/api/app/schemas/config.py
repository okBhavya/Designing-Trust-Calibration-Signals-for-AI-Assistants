from uuid import UUID

from pydantic import BaseModel


class ParticipantConfig(BaseModel):
    participant_id: UUID
    condition: str
    feature_flags: dict[str, bool]
