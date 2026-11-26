"""Study harness endpoints (apps/study): enrollment, main trials and questionnaires.

Trials and questionnaires are idempotent: the harness retries failed posts, so re-sending a record
that is already stored returns it with created=false instead of failing or writing it twice.
"""

import hmac
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.auth import AuthenticatedSession, create_session_token, require_session
from app.core.rate_limit import rate_limit
from app.database.connection import get_db
from app.database.models import Participant, Questionnaire, Trial
from app.schemas.study import (
    StudyEnrollRequest,
    StudyEnrollResponse,
    StudyQuestionnaireRequest,
    StudyRecordResponse,
    StudyTrialRequest,
)
from app.services.consent_service import require_capture_consent
from app.services.study_service import assign_condition

router = APIRouter(prefix="/v1/study")


@router.post("/enroll", response_model=StudyEnrollResponse, status_code=201, dependencies=[Depends(rate_limit)])
def enroll(request: StudyEnrollRequest, db: Session = Depends(get_db)) -> StudyEnrollResponse:
    """Creates a pseudonymous participant with current consent and an assigned condition, in one call."""
    settings = get_settings()
    if settings.study_enrollment_code is None:
        raise HTTPException(status_code=503, detail="Study enrollment is closed")
    expected = settings.study_enrollment_code.get_secret_value().encode()
    if not hmac.compare_digest(request.enrollment_code.encode(), expected):
        raise HTTPException(status_code=401, detail="Invalid study enrollment code")
    if request.consent_version != settings.consent_version:
        raise HTTPException(status_code=409, detail="The consent text is out of date; reload the study page")
    participant = Participant(
        id=uuid4(),
        consent_version=settings.consent_version,
        consent_status="granted",
        condition=assign_condition(db),
    )
    db.add(participant)
    db.flush()
    token, expires_in, _ = create_session_token(participant.id, db)
    db.commit()
    return StudyEnrollResponse(
        participant_id=participant.id,
        access_token=token,
        expires_in=expires_in,
        condition=participant.condition,
        consent_version=participant.consent_version,
    )


@router.post("/trials", response_model=StudyRecordResponse, status_code=201)
def record_trial(
    request: StudyTrialRequest,
    response: Response,
    session: AuthenticatedSession = Depends(require_session),
    db: Session = Depends(get_db),
) -> StudyRecordResponse:
    participant = _consenting_participant(db, session, request.participant_id)
    if request.condition != participant.condition:
        raise HTTPException(status_code=409, detail="Trial condition does not match the participant's assigned condition")
    trial = Trial(participant_id=participant.id, **request.model_dump(exclude={"participant_id"}))
    db.add(trial)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        stored = db.scalar(
            select(Trial).where(Trial.participant_id == participant.id, Trial.question_id == request.question_id)
        )
        if stored is None:
            raise
        same = (stored.position, stored.decision, stored.self_confidence, stored.ai_correct) == (
            request.position, request.decision, request.self_confidence, request.ai_correct
        )
        if not same:
            raise HTTPException(status_code=409, detail="A different response to this question is already recorded")
        response.status_code = 200
        return StudyRecordResponse(id=stored.id, created=False)
    return StudyRecordResponse(id=trial.id, created=True)


@router.post("/questionnaire", response_model=StudyRecordResponse, status_code=201)
def record_questionnaire(
    request: StudyQuestionnaireRequest,
    response: Response,
    session: AuthenticatedSession = Depends(require_session),
    db: Session = Depends(get_db),
) -> StudyRecordResponse:
    participant = _consenting_participant(db, session, request.participant_id)
    record = Questionnaire(participant_id=participant.id, instrument=request.instrument, responses=request.responses)
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        stored = db.scalar(
            select(Questionnaire).where(
                Questionnaire.participant_id == participant.id, Questionnaire.instrument == request.instrument
            )
        )
        if stored is None:
            raise
        if stored.responses != request.responses:
            raise HTTPException(status_code=409, detail="Different answers to this questionnaire are already recorded")
        response.status_code = 200
        return StudyRecordResponse(id=stored.id, created=False)
    return StudyRecordResponse(id=record.id, created=True)


def _consenting_participant(db: Session, session: AuthenticatedSession, participant_id: UUID) -> Participant:
    if session.participant_id != participant_id:
        raise HTTPException(status_code=403, detail="Participant does not match authenticated session")
    return require_capture_consent(db, participant_id)
