from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "participants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("consent_version", sa.String(100)),
        sa.Column("consent_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("condition", sa.String(100), nullable=False, server_default="default"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "trials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("participant_id", sa.Uuid(), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trial_key", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.UniqueConstraint("participant_id", "trial_key", name="uq_trial_participant_key"),
    )
    op.create_table(
        "signal_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("participant_id", sa.Uuid(), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Uuid()),
        sa.Column("trial_id", sa.Uuid(), sa.ForeignKey("trials.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("platform", sa.String(20)),
        sa.Column("answer_hash", sa.String(64)),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_signal_events_participant_occurred", "signal_events", ["participant_id", "occurred_at"])
    op.create_table(
        "questionnaires",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("participant_id", sa.Uuid(), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instrument", sa.String(100), nullable=False),
        sa.Column("responses", sa.JSON(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("participant_id", "instrument", name="uq_questionnaire_participant_instrument"),
    )
    op.create_table(
        "live_signals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("participant_id", sa.Uuid(), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.Uuid()),
        sa.Column("platform", sa.String(20), nullable=False),
        sa.Column("answer_hash", sa.String(64), nullable=False),
        sa.Column("prompt", sa.Text()),
        sa.Column("answer", sa.Text()),
        sa.Column("response_json", sa.JSON(), nullable=False),
        sa.Column("model_version", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("participant_id", "answer_hash", name="uq_live_signal_participant_hash"),
    )
    op.create_index("ix_live_signals_platform_created", "live_signals", ["platform", "created_at"])
    op.create_table(
        "session_tokens",
        sa.Column("jti", sa.String(128), primary_key=True),
        sa.Column("participant_id", sa.Uuid(), sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_session_tokens_participant", "session_tokens", ["participant_id"])
    if op.get_bind().dialect.name == "postgresql":
        for table in ("participants", "trials", "signal_events", "questionnaires", "live_signals", "session_tokens"):
            op.execute(sa.text(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY"))
        op.execute(sa.text(
            "CREATE POLICY participants_isolation ON participants "
            "USING (id::text = current_setting('app.participant_id', true))"
        ))
        for table in ("trials", "signal_events", "questionnaires", "live_signals"):
            op.execute(sa.text(
                f"CREATE POLICY {table}_participant_isolation ON {table} "
                "USING (participant_id::text = current_setting('app.participant_id', true))"
            ))
        op.execute(sa.text(
            "CREATE POLICY session_tokens_participant_isolation ON session_tokens "
            "USING (participant_id::text = current_setting('app.participant_id', true))"
        ))


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        for table in ("trials", "signal_events", "questionnaires", "live_signals", "session_tokens"):
            op.execute(sa.text(f"DROP POLICY IF EXISTS {table}_participant_isolation ON {table}"))
        op.execute(sa.text("DROP POLICY IF EXISTS participants_isolation ON participants"))
    op.drop_index("ix_session_tokens_participant", table_name="session_tokens")
    op.drop_table("session_tokens")
    op.drop_index("ix_live_signals_platform_created", table_name="live_signals")
    op.drop_table("live_signals")
    op.drop_table("questionnaires")
    op.drop_index("ix_signal_events_participant_occurred", table_name="signal_events")
    op.drop_table("signal_events")
    op.drop_table("trials")
    op.drop_table("participants")
