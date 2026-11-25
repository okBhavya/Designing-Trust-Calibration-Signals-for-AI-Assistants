"""Export study data as CSV: participants, trials, events and questionnaires.

    python apps/api/scripts/export_study.py                      # -> apps/api/exports/<UTC time>/
    python apps/api/scripts/export_study.py --out some/dir --database-url sqlite:///./calibrai.db

Only study participants (condition baseline, A or C) whose consent is currently granted are
exported, together with their own rows. Participants are identified by their random participant_id
and carry no personal data: participants.csv holds only the id, the condition and the consent
version. The output folder holds participant data, so apps/api/exports/ is git-ignored; keep exports
out of the repository.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_DIR))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.database.models import Participant, Questionnaire, SignalEvent, Trial  # noqa: E402
from app.services.study_service import STUDY_CONDITIONS  # noqa: E402

PARTICIPANT_COLUMNS = ["participant_id", "condition", "consent_version"]
TRIAL_COLUMNS = [
    "participant_id", "question_id", "position", "condition", "ai_correct", "signal_level", "signal_score",
    "shown_at", "decided_at", "decision_ms", "decision", "self_confidence", "final_correct",
]
EVENT_METADATA_KEYS = ["question_id", "condition", "phase", "sentence_index"]
EVENT_COLUMNS = ["participant_id", "event_type", "occurred_at", *EVENT_METADATA_KEYS, "metadata"]
QUESTIONNAIRE_COLUMNS = ["participant_id", "instrument", "item", "value", "submitted_at"]


def _iso(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:  # SQLite returns naive values; they were written as UTC
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _milliseconds(start: datetime, end: datetime) -> int:
    return round((end - start).total_seconds() * 1000)


def export_study(db: Session, out_dir: Path) -> dict[str, int]:
    """Writes the four CSV files into out_dir and returns the row count of each."""
    participants = db.scalars(
        select(Participant)
        .where(Participant.condition.in_(STUDY_CONDITIONS), Participant.consent_status == "granted")
        .order_by(Participant.id)
    ).all()
    ids = [participant.id for participant in participants]
    rows: dict[str, list[dict]] = {
        "participants": [
            {"participant_id": p.id, "condition": p.condition, "consent_version": p.consent_version} for p in participants
        ],
        "trials": [
            {
                "participant_id": t.participant_id, "question_id": t.question_id, "position": t.position,
                "condition": t.condition, "ai_correct": t.ai_correct, "signal_level": t.signal_level or "",
                "signal_score": "" if t.signal_score is None else t.signal_score,
                "shown_at": _iso(t.shown_at), "decided_at": _iso(t.decided_at),
                "decision_ms": _milliseconds(t.shown_at, t.decided_at), "decision": t.decision,
                "self_confidence": t.self_confidence, "final_correct": t.final_correct,
            }
            for t in db.scalars(
                select(Trial).where(Trial.participant_id.in_(ids)).order_by(Trial.participant_id, Trial.position)
            )
        ],
        "events": [
            {
                "participant_id": e.participant_id, "event_type": e.event_type, "occurred_at": _iso(e.occurred_at),
                **{key: e.metadata_json.get(key, "") for key in EVENT_METADATA_KEYS},
                "metadata": json.dumps(e.metadata_json, sort_keys=True),
            }
            for e in db.scalars(
                select(SignalEvent)
                .where(SignalEvent.participant_id.in_(ids))
                .order_by(SignalEvent.participant_id, SignalEvent.occurred_at)
            )
        ],
        "questionnaires": [
            {"participant_id": q.participant_id, "instrument": q.instrument, "item": item, "value": value,
             "submitted_at": _iso(q.submitted_at)}
            for q in db.scalars(
                select(Questionnaire)
                .where(Questionnaire.participant_id.in_(ids))
                .order_by(Questionnaire.participant_id, Questionnaire.instrument)
            )
            for item, value in sorted(q.responses.items())
        ],
    }
    columns = {
        "participants": PARTICIPANT_COLUMNS, "trials": TRIAL_COLUMNS,
        "events": EVENT_COLUMNS, "questionnaires": QUESTIONNAIRE_COLUMNS,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, table in rows.items():
        with (out_dir / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns[name])
            writer.writeheader()
            writer.writerows(table)
    return {name: len(table) for name, table in rows.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, help="output folder (default: apps/api/exports/<UTC time>)")
    parser.add_argument("--database-url", help="defaults to CALIBRAI_DATABASE_URL / apps/api/.env")
    args = parser.parse_args()
    out_dir = (args.out or API_DIR / "exports" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")).resolve()
    os.chdir(API_DIR)  # Settings reads apps/api/.env relative to the working directory

    from sqlalchemy.orm import sessionmaker

    from app.config import get_settings
    from app.database.connection import build_engine

    get_settings.cache_clear()  # settings were first read before the chdir, without apps/api/.env

    engine = build_engine(args.database_url)
    with sessionmaker(bind=engine)() as db:
        counts = export_study(db, out_dir)
    engine.dispose()
    print(f"Wrote {out_dir}")
    for name, count in counts.items():
        print(f"  {name}.csv: {count} row(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
