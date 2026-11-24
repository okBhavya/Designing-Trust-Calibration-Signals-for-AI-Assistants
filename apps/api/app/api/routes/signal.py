from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedSession, require_session
from app.core.exceptions import ApiError
from app.core.rate_limit import rate_limit
from app.database.connection import get_db
from app.database.models import LiveSignal
from app.schemas.signal import SignalRequest, SignalResponse
from app.services.consent_service import require_capture_consent
from app.services.reliability_service import ProviderUnavailableError, ReliabilityFixtureProvider
from app.services.signal_service import MockSignalProvider, SignalProvider
from app.config import get_settings

router = APIRouter(prefix="/v1")


def _privacy_safe_response(result: SignalResponse) -> dict:
    payload = result.model_dump(by_alias=True)
    payload["claimAssessments"] = [
        {
            key: value
            for key, value in assessment.items()
            if key != "claim"
        }
        for assessment in payload.get("claimAssessments", [])
    ]
    return payload


def get_provider() -> SignalProvider:
    settings = get_settings()
    if settings.signal_provider == "reliability_fixture":
        return ReliabilityFixtureProvider()
    if settings.signal_provider == "mock":
        return MockSignalProvider()
    raise ProviderUnavailableError("Configured signal provider is unavailable")


def _stored_signal(db: Session, participant_id, answer_hash: str) -> LiveSignal | None:
    return db.scalar(
        select(LiveSignal).where(
            LiveSignal.participant_id == participant_id,
            LiveSignal.answer_hash == answer_hash,
        )
    )


@router.post("/signal", response_model=SignalResponse, dependencies=[Depends(rate_limit)])
def signal(
    request: SignalRequest,
    session: AuthenticatedSession = Depends(require_session),
    db: Session = Depends(get_db),
) -> SignalResponse:
    if session.participant_id != request.participant_id:
        raise ApiError(403, "Participant does not match authenticated session")
    participant = require_capture_consent(db, request.participant_id)
    # A revisited answer (e.g. after a page reload) gets the response stored the
    # first time instead of a 409. The stored copy omits raw claim text.
    stored = _stored_signal(db, participant.id, request.answer_hash)
    if stored is not None:
        return JSONResponse(stored.response_json)
    try:
        result = get_provider().evaluate(request)
    except ProviderUnavailableError:
        result = SignalResponse(
            confidence=None,
            assessmentState="unavailable",
            score=0,
            explanation="Evidence evaluation is temporarily unavailable.",
            modelVersion="reliability-unavailable-v1",
            processingLatencyMs=0,
        )
    settings = get_settings()
    record = LiveSignal(
        participant_id=participant.id,
        session_id=request.session_id,
        platform=request.platform,
        answer_hash=request.answer_hash,
        prompt=request.prompt if settings.store_raw_conversation else None,
        answer=request.answer if settings.store_raw_conversation else None,
        response_json=_privacy_safe_response(result),
        model_version=result.model_version,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if "live_signals.participant_id" in str(error) or "uq_live_signal_participant_hash" in str(error):
            # A concurrent request stored this answer first; return its response.
            stored = _stored_signal(db, participant.id, request.answer_hash)
            if stored is not None:
                return JSONResponse(stored.response_json)
        raise
    return result
