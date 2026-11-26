"""Alembic migrations must produce exactly the schema the models describe."""

from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from app.config import get_settings
from app.database.connection import Base

API_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def alembic_db(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'migrations.db').as_posix()}"
    monkeypatch.setattr(get_settings(), "database_url", url)  # alembic/env.py reads the URL from settings
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "alembic"))
    engine = sa.create_engine(url)
    yield config, engine
    engine.dispose()


def schema_diff(engine) -> list:
    with engine.connect() as connection:
        return compare_metadata(MigrationContext.configure(connection), Base.metadata)


def test_upgrade_head_matches_the_models(alembic_db):
    config, engine = alembic_db
    command.upgrade(config, "head")
    assert schema_diff(engine) == []


def test_0002_round_trips_and_keeps_the_trial_constraints(alembic_db):
    config, engine = alembic_db
    command.upgrade(config, "head")
    command.downgrade(config, "0001_initial")
    columns = {column["name"] for column in sa.inspect(engine).get_columns("trials")}
    assert {"trial_key", "started_at", "completed_at"} <= columns and "decision" not in columns
    command.upgrade(config, "head")
    inspector = sa.inspect(engine)
    unique = {c["name"]: c["column_names"] for c in inspector.get_unique_constraints("trials")}
    assert unique["uq_trial_participant_key"] == ["participant_id", "question_id"]
    checks = {c["name"] for c in inspector.get_check_constraints("trials")}
    assert {"ck_trials_decision", "ck_trials_self_confidence"} <= checks
    nullable = {c["name"]: c["nullable"] for c in inspector.get_columns("participants")}
    assert nullable["created_at"] is False and nullable["updated_at"] is False


def test_0002_refuses_to_guess_values_for_existing_trials(alembic_db):
    config, engine = alembic_db
    command.upgrade(config, "0001_initial")
    with engine.begin() as connection:
        connection.execute(sa.text("INSERT INTO participants (id, consent_status, condition) VALUES ('11111111111141118111111111111111', 'granted', 'A')"))
        connection.execute(sa.text(
            "INSERT INTO trials (id, participant_id, trial_key, metadata) "
            "VALUES ('22222222222242228222222222222222', '11111111111141118111111111111111', 'q1', '{}')"
        ))
    with pytest.raises(RuntimeError, match="trials has 1 row"):
        command.upgrade(config, "head")
