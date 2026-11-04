import re
from uuid import UUID

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def validate_participant_id(participant_id: UUID) -> UUID:
    if not UUID_PATTERN.fullmatch(str(participant_id)):
        raise ValueError("participant_id must be a canonical UUID")
    return participant_id
