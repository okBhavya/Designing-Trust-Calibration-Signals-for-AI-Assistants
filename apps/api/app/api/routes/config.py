from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedSession, require_session
from app.database.connection import get_db
from app.schemas.config import ParticipantConfig
from app.services.consent_service import get_participant

router = APIRouter(prefix="/v1")


@router.get("/config", response_model=ParticipantConfig)
def config(
    participant_id: UUID,
    session: AuthenticatedSession = Depends(require_session),
    db: Session = Depends(get_db),
) -> ParticipantConfig:
    if session.participant_id != participant_id:
        raise HTTPException(status_code=403, detail="Participant does not match authenticated session")
    participant = get_participant(db, participant_id)
    return ParticipantConfig(
        participant_id=participant.id,
        condition=participant.condition,
        feature_flags={"mock_signal": True},
    )
