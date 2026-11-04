from uuid import UUID

from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import ApiError
from app.database.models import Participant


def get_participant(db: Session, participant_id: UUID) -> Participant:
    participant = db.get(Participant, participant_id)
    if participant is None:
        raise ApiError(404, "Participant not found")
    return participant


def require_capture_consent(db: Session, participant_id: UUID) -> Participant:
    participant = get_participant(db, participant_id)
    settings = get_settings()
    if participant.consent_status != "granted" or participant.consent_version != settings.consent_version:
        raise ApiError(403, "Current consent is required before capturing conversation data")
    return participant
