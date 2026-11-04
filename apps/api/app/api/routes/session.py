from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.auth import AuthenticatedSession, create_session_token, require_session
from app.core.rate_limit import rate_limit
from app.database.connection import get_db
from app.database.models import Participant, SessionToken
from app.schemas.session import SessionCreateRequest, SessionResponse

router = APIRouter(prefix="/v1")


@router.post("/session", response_model=SessionResponse, dependencies=[Depends(rate_limit)])
def create_session(request: SessionCreateRequest, db: Session = Depends(get_db)) -> SessionResponse:
    settings = get_settings()
    if not secrets_compare(request.enrollment_secret, settings.enrollment_secret):
        raise HTTPException(status_code=401, detail="Invalid enrollment credentials")
    participant = db.get(Participant, request.participant_id)
    if participant is None:
        participant = Participant(id=request.participant_id)
        db.add(participant)
        db.flush()
    token, expires_in, _ = create_session_token(participant.id, db)
    db.commit()
    return SessionResponse(
        access_token=token,
        expires_in=expires_in,
        participant_id=participant.id,
    )


@router.post("/session/revoke", status_code=204)
def revoke_session(
    session: AuthenticatedSession = Depends(require_session),
    db: Session = Depends(get_db),
) -> None:
    token_session = db.get(SessionToken, session.jti)
    if token_session:
        token_session.revoked = True
        db.commit()


def secrets_compare(provided: str, expected: str) -> bool:
    import hmac

    return hmac.compare_digest(provided.encode(), expected.encode())
