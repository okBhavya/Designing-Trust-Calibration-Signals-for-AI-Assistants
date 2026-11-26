from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.connection import Base


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    consent_version: Mapped[str | None] = mapped_column(String(100))
    consent_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    condition: Mapped[str] = mapped_column(String(100), default="default", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    trials: Mapped[list["Trial"]] = relationship(back_populates="participant", cascade="all, delete-orphan")
    signal_events: Mapped[list["SignalEvent"]] = relationship(back_populates="participant", cascade="all, delete-orphan")
    questionnaires: Mapped[list["Questionnaire"]] = relationship(back_populates="participant", cascade="all, delete-orphan")
    live_signals: Mapped[list["LiveSignal"]] = relationship(back_populates="participant", cascade="all, delete-orphan")
    sessions: Mapped[list["SessionToken"]] = relationship(back_populates="participant", cascade="all, delete-orphan")


class SessionToken(Base):
    __tablename__ = "session_tokens"

    jti: Mapped[str] = mapped_column(String(128), primary_key=True)
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    participant: Mapped[Participant] = relationship(back_populates="sessions")
    __table_args__ = (Index("ix_session_tokens_participant", "participant_id"),)


class Trial(Base):
    """One main study trial: what the participant saw and what they decided. Practice trials are not stored."""

    __tablename__ = "trials"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    condition: Mapped[str] = mapped_column(String(100), nullable=False)
    ai_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    signal_level: Mapped[str | None] = mapped_column(String(40))
    signal_score: Mapped[float | None] = mapped_column(Float)
    shown_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decision: Mapped[str] = mapped_column(String(10), nullable=False)
    self_confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    final_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    participant: Mapped[Participant] = relationship(back_populates="trials")
    __table_args__ = (
        UniqueConstraint("participant_id", "question_id", name="uq_trial_participant_key"),
        CheckConstraint("decision IN ('accept', 'reject')", name="ck_trials_decision"),
        CheckConstraint("self_confidence BETWEEN 1 AND 5", name="ck_trials_self_confidence"),
    )


class SignalEvent(Base):
    __tablename__ = "signal_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[UUID | None] = mapped_column()
    trial_id: Mapped[UUID | None] = mapped_column(ForeignKey("trials.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(20))
    answer_hash: Mapped[str | None] = mapped_column(String(64))
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    participant: Mapped[Participant] = relationship(back_populates="signal_events")
    __table_args__ = (Index("ix_signal_events_participant_occurred", "participant_id", "occurred_at"),)


class Questionnaire(Base):
    __tablename__ = "questionnaires"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    instrument: Mapped[str] = mapped_column(String(100), nullable=False)
    responses: Mapped[dict] = mapped_column(JSON, nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    participant: Mapped[Participant] = relationship(back_populates="questionnaires")
    __table_args__ = (UniqueConstraint("participant_id", "instrument", name="uq_questionnaire_participant_instrument"),)


class LiveSignal(Base):
    __tablename__ = "live_signals"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    participant_id: Mapped[UUID] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[UUID | None] = mapped_column()
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    answer_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt: Mapped[str | None] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text)
    response_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    model_version: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    participant: Mapped[Participant] = relationship(back_populates="live_signals")
    __table_args__ = (
        UniqueConstraint("participant_id", "answer_hash", name="uq_live_signal_participant_hash"),
        Index("ix_live_signals_platform_created", "platform", "created_at"),
    )
