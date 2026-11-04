from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedSession, require_session
from app.database.connection import get_db
from app.services.consent_service import get_participant

router = APIRouter(prefix="/v1")


@router.delete("/participant/{participant_id}", status_code=204)
def delete_participant(
    participant_id: UUID,
    session: AuthenticatedSession = Depends(require_session),
    db: Session = Depends(get_db),
) -> Response:
    if session.participant_id != participant_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Participant does not match authenticated session")
    participant = get_participant(db, participant_id)
    db.delete(participant)
    db.commit()
    return Response(status_code=204)
