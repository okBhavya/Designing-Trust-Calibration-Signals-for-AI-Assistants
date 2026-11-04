from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedSession, require_session
from app.database.connection import get_db
from app.database.models import SignalEvent
from app.schemas.events import EventRequest, EventResponse
from app.services.consent_service import get_participant

router = APIRouter(prefix="/v1")


@router.post("/events", response_model=EventResponse)
def event(
    request: EventRequest,
    session: AuthenticatedSession = Depends(require_session),
    db: Session = Depends(get_db),
) -> EventResponse:
    if session.participant_id != request.participant_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Participant does not match authenticated session")
    participant = get_participant(db, request.participant_id)
    record = SignalEvent(
        participant_id=participant.id,
        session_id=request.session_id,
        trial_id=request.trial_id,
        event_type=request.event_type,
        platform=request.platform,
        answer_hash=request.answer_hash,
        metadata_json=request.metadata,
    )
    db.add(record)
    db.commit()
    return EventResponse(id=record.id)
