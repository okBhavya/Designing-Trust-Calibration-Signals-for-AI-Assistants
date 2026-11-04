from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant_id: UUID
    enrollment_secret: str = Field(min_length=16, max_length=256)


class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    participant_id: UUID


class SessionRevokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=20, max_length=4096)
