from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedSession, require_session
from app.core.security import validate_participant_id
from app.database.connection import get_db
from app.database.models import Participant
from app.schemas.consent import ConsentRequest, ConsentResponse

router = APIRouter(prefix="/v1")


@router.post("/consent", response_model=ConsentResponse)
def record_consent(
    request: ConsentRequest,
    session: AuthenticatedSession = Depends(require_session),
    db: Session = Depends(get_db),
) -> ConsentResponse:
    if session.participant_id != request.participant_id:
        raise HTTPException(status_code=403, detail="Participant does not match authenticated session")
    participant_id = validate_participant_id(request.participant_id)
    participant = db.get(Participant, participant_id)
    if participant is None:
        participant = Participant(id=participant_id)
        db.add(participant)
    participant.consent_version = request.consent_version
    participant.consent_status = request.status
    db.commit()
    return ConsentResponse(
        participant_id=participant.id,
        consent_version=request.consent_version,
        status=participant.consent_status,
    )
