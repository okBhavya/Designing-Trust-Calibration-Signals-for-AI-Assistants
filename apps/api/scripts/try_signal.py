"""Run one prompt + answer through the selfconsistency provider against the live LLM API.

Each run makes 7 billed LLM calls (1 extraction, 5 samples, 1 judge).

    $env:LLM_API_KEY = '...'
    python scripts/try_signal.py --prompt "When was the Eiffel Tower finished?" `
        --answer "The Eiffel Tower was completed in 1889 for the World's Fair."

Use --answer-file to read a long answer from a file. Set CALIBRAI_LLM_MODEL to change the model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.schemas.signal import SignalRequest  # noqa: E402
from app.services.selfconsistency_service import SelfConsistencyProvider  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prompt", required=True, help="The user's original prompt")
    answer = parser.add_mutually_exclusive_group(required=True)
    answer.add_argument("--answer", help="The AI answer to evaluate")
    answer.add_argument("--answer-file", type=Path, help="Read the AI answer from this file")
    parser.add_argument("--platform", default="chatgpt", choices=["chatgpt", "claude", "gemini"])
    args = parser.parse_args()

    settings = get_settings()
    if settings.llm_api_key is None or not settings.llm_api_key.get_secret_value():
        print("LLM_API_KEY is not set; it is required for a live run.", file=sys.stderr)
        return 2

    answer_text = args.answer if args.answer is not None else args.answer_file.read_text(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    request = SignalRequest(
        participant_id=uuid4(),
        platform=args.platform,
        answer_hash=hashlib.sha256(answer_text.strip().encode("utf-8")).hexdigest(),
        prompt=args.prompt,
        answer=answer_text,
    )
    result = SelfConsistencyProvider().evaluate(request)
    print(json.dumps(result.model_dump(by_alias=True), indent=2, ensure_ascii=False))
    return 0 if result.assessment_state != "unavailable" else 1


if __name__ == "__main__":
    raise SystemExit(main())
