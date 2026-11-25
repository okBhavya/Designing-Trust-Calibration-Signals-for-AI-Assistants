"""Study trial columns, and NOT NULL on the server-defaulted timestamps.

- trials: rename trial_key -> question_id, started_at -> shown_at, completed_at -> decided_at, and add
  the study columns (position, condition, ai_correct, signal_level, signal_score, decision,
  self_confidence, final_correct). No endpoint wrote to trials before this revision, so the upgrade
  refuses to run on a non-empty table instead of inventing values for the new NOT NULL columns.
- The six timestamps that the models declare NOT NULL but 0001 created nullable (the audit's
  migration diffs): participants.created_at, participants.updated_at, questionnaires.submitted_at,
  signal_events.occurred_at, live_signals.created_at, session_tokens.created_at.

Batch mode lets SQLite (which cannot ALTER a column in place) recreate the tables; on PostgreSQL the
same operations run as plain ALTER TABLE statements.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_study_trials"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TIMESTAMP = sa.DateTime(timezone=True)
SERVER_DEFAULTED_TIMESTAMPS = (
    ("participants", "created_at"),
    ("participants", "updated_at"),
    ("questionnaires", "submitted_at"),
    ("signal_events", "occurred_at"),
    ("live_signals", "created_at"),
    ("session_tokens", "created_at"),
)
STUDY_COLUMNS = (
    ("position", sa.Integer()),
    ("condition", sa.String(100)),
    ("ai_correct", sa.Boolean()),
    ("signal_level", sa.String(40)),
    ("signal_score", sa.Float()),
    ("decision", sa.String(10)),
    ("self_confidence", sa.Integer()),
    ("final_correct", sa.Boolean()),
)
NULLABLE_STUDY_COLUMNS = {"signal_level", "signal_score"}


def upgrade() -> None:
    bind = op.get_bind()
    existing_trials = bind.execute(sa.text("SELECT COUNT(*) FROM trials")).scalar_one()
    if existing_trials:
        raise RuntimeError(
            f"trials has {existing_trials} row(s); 0002 adds NOT NULL study columns and cannot fill them. "
            "Export and clear the table, or backfill it in a reviewed migration, before upgrading."
        )

    for table, column in SERVER_DEFAULTED_TIMESTAMPS:
        op.execute(sa.text(f"UPDATE {table} SET {column} = CURRENT_TIMESTAMP WHERE {column} IS NULL"))
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, existing_type=TIMESTAMP, existing_server_default=sa.func.now(), nullable=False)

    with op.batch_alter_table("trials") as batch:
        batch.drop_constraint("uq_trial_participant_key", type_="unique")
        batch.alter_column("trial_key", new_column_name="question_id", existing_type=sa.String(100), existing_nullable=False)
        batch.alter_column("started_at", new_column_name="shown_at", existing_type=TIMESTAMP, nullable=False)
        batch.alter_column("completed_at", new_column_name="decided_at", existing_type=TIMESTAMP, nullable=False)
        for name, column_type in STUDY_COLUMNS:
            batch.add_column(sa.Column(name, column_type, nullable=name in NULLABLE_STUDY_COLUMNS))
    # A separate batch: SQLite batch mode cannot build a constraint on a column renamed in the same batch.
    with op.batch_alter_table("trials") as batch:
        batch.create_unique_constraint("uq_trial_participant_key", ["participant_id", "question_id"])
        batch.create_check_constraint("ck_trials_decision", "decision IN ('accept', 'reject')")
        batch.create_check_constraint("ck_trials_self_confidence", "self_confidence BETWEEN 1 AND 5")


def downgrade() -> None:
    with op.batch_alter_table("trials") as batch:
        batch.drop_constraint("ck_trials_self_confidence", type_="check")
        batch.drop_constraint("ck_trials_decision", type_="check")
        batch.drop_constraint("uq_trial_participant_key", type_="unique")
        for name, _ in reversed(STUDY_COLUMNS):
            batch.drop_column(name)
        batch.alter_column("decided_at", new_column_name="completed_at", existing_type=TIMESTAMP, nullable=True)
        batch.alter_column("shown_at", new_column_name="started_at", existing_type=TIMESTAMP, nullable=True)
        batch.alter_column("question_id", new_column_name="trial_key", existing_type=sa.String(100), existing_nullable=False)
    with op.batch_alter_table("trials") as batch:
        batch.create_unique_constraint("uq_trial_participant_key", ["participant_id", "trial_key"])

    for table, column in reversed(SERVER_DEFAULTED_TIMESTAMPS):
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, existing_type=TIMESTAMP, existing_server_default=sa.func.now(), nullable=True)
