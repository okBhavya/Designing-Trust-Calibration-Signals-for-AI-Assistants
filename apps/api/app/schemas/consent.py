from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    participant_id: UUID
    consent_version: str = Field(min_length=1, max_length=100)
    status: Literal["granted", "withdrawn"]


class ConsentResponse(BaseModel):
    participant_id: UUID
    consent_version: str
    status: str
