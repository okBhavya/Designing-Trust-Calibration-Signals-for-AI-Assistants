from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_session, rate_limit
from app.core.errors import ApiError
from app.database.connection import get_db
from app.database.models import LiveSignal
from app.schemas.signal import SignalRequest, SignalResponse
from app.services.consent_service import require_capture_consent
from app.services.reliability_service import ProviderUnavailableError
from app.services.signal_service import MockSignalProvider, SignalProvider
from app.config import get_settings

router = APIRouter(prefix="/v1")


def get_provider() -> SignalProvider:
    settings = get_settings()
    if settings.signal_provider == "reliability_fixture":
        from app.services.reliability_service import ReliabilityFixtureProvider
        return ReliabilityFixtureProvider()
    if settings.signal_provider == "mock":
        return MockSignalProvider()
    raise ProviderUnavailableError("Configured signal provider is unavailable")


@router.post("/signal", response_model=SignalResponse, dependencies=[Depends(rate_limit)])
def signal(
    request: SignalRequest,
    session=Depends(get_current_session),
    db: Session = Depends(get_db),
):
    if session.participant_id != request.participant_id:
        raise ApiError(403, "Participant does not match authenticated session")
    participant = require_capture_consent(db, request.participant_id)
    result = get_provider().evaluate(request)
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
    db.commit()
    db.refresh(record)
    return result
