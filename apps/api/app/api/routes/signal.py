from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedSession, require_session
from app.core.exceptions import ApiError
from app.core.rate_limit import rate_limit
from app.database.connection import get_db
from app.database.models import LiveSignal
from app.schemas.signal import SignalRequest, SignalResponse
from app.services.consent_service import require_capture_consent
from app.services.signal_service import MockSignalProvider, SignalProvider

router = APIRouter(prefix="/v1")
provider: SignalProvider = MockSignalProvider()


@router.post("/signal", response_model=SignalResponse, dependencies=[Depends(rate_limit)])
def signal(
    request: SignalRequest,
    session: AuthenticatedSession = Depends(require_session),
    db: Session = Depends(get_db),
) -> SignalResponse:
    if session.participant_id != request.participant_id:
        raise ApiError(403, "Participant does not match authenticated session")
    participant = require_capture_consent(db, request.participant_id)
    result = provider.evaluate(request)
    record = LiveSignal(
        participant_id=participant.id,
        session_id=request.session_id,
        platform=request.platform,
        answer_hash=request.answer_hash,
        prompt=request.prompt,
        answer=request.answer,
        response_json=result.model_dump(by_alias=True),
        model_version=result.model_version,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if "live_signals.participant_id" in str(error) or "uq_live_signal_participant_hash" in str(error):
            raise ApiError(409, "A signal already exists for this answer") from error
        raise
    return result
