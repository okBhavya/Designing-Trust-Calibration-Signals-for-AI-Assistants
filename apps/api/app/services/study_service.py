import random
from typing import get_args

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models import Participant
from app.schemas.study import StudyCondition

STUDY_CONDITIONS: tuple[str, ...] = get_args(StudyCondition)
_rng = random.SystemRandom()


def condition_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Participant.condition, func.count())
        .where(Participant.condition.in_(STUDY_CONDITIONS))
        .group_by(Participant.condition)
    ).all()
    counts = {condition: 0 for condition in STUDY_CONDITIONS}
    counts.update({condition: count for condition, count in rows})
    return counts


def assign_condition(db: Session, rng: random.Random | None = None) -> str:
    """Balanced assignment: the least-filled study condition, ties broken at random.

    Counts every participant still in the database, including withdrawn ones (they were assigned);
    deleted participants no longer count. Two simultaneous enrollments can both see the same counts,
    so groups can differ by a few participants under heavy concurrency.
    """
    counts = condition_counts(db)
    fewest = min(counts.values())
    return (rng or _rng).choice([condition for condition in STUDY_CONDITIONS if counts[condition] == fewest])
