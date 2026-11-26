from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
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
        feature_flags=feature_flags(get_settings()),
    )


def feature_flags(settings: Settings) -> dict[str, bool]:
    """What this deployment actually does, from its settings."""
    return {
        "mock_signal": settings.signal_provider == "mock",
        "live_signal": settings.signal_provider == "selfconsistency",
        "fixture_signal": settings.signal_provider == "reliability_fixture",
        "study_enrollment_open": settings.study_enrollment_code is not None,
        "raw_conversation_storage": settings.store_raw_conversation,
    }
