"""Backend half of the signal-response contract with the extension.

Real responses from each provider, rendered through the API, must match the committed samples in
contracts/signal_responses.json. The extension test tests/contract.test.ts runs the extension's own
validator (isSignalResponse) over the same file, so a shape change breaks one side or the other.

Regenerate after an intentional change:  UPDATE_CONTRACT=1 python -m pytest tests/test_contract.py
"""

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest

from test_selfconsistency import ANSWER, CLAIMS, FakeLLMClient, S, C, N, extraction_json, judge_json

CONTRACT = Path(__file__).resolve().parents[3] / "contracts" / "signal_responses.json"


def _samples(client, auth_headers, monkeypatch) -> dict:
    from app.api.routes import signal as signal_route
    from app.services.reliability_service import (
        FixtureEvidenceRetriever,
        ProviderUnavailableError,
        ReliabilityFixtureProvider,
    )
    from app.services.selfconsistency_service import SelfConsistencyProvider
    from app.services.signal_service import MockSignalProvider

    participant_id = uuid4()
    headers = auth_headers(participant_id)
    client.post(
        "/v1/consent",
        json={"participant_id": str(participant_id), "consent_version": "test-consent", "status": "granted"},
        headers=headers,
    )
    sky = "The sky is blue because sunlight scatters through the atmosphere."

    def unavailable():
        raise ProviderUnavailableError("down")

    providers = {
        "mock": lambda: MockSignalProvider(),
        "fixture_medium_with_flags": lambda: ReliabilityFixtureProvider(
            FixtureEvidenceRetriever(
                records=[{
                    "claim": sky, "sourceId": "src-1", "url": "https://example.test/sky",
                    "domain": "example.test", "relevanceScore": 1, "quality": 1, "independenceGroup": "example",
                }]
            )
        ),
        "fixture_insufficient_evidence": lambda: ReliabilityFixtureProvider(FixtureEvidenceRetriever(records=[])),
        "provider_unavailable": unavailable,
        "selfconsistency_with_flags": lambda: SelfConsistencyProvider(
            client_factory=lambda: FakeLLMClient(
                extraction=[extraction_json(CLAIMS)],
                judge=[judge_json([[S] * 5, [S, S, C, C, C], [S, N, N, N, N]])],
            )
        ),
    }
    answers = {
        "fixture_medium_with_flags": f"{sky} The moon is made of cheese.",
        "fixture_insufficient_evidence": "The moon is made of cheese.",
    }
    samples = {}
    for index, (name, factory) in enumerate(providers.items()):
        monkeypatch.setattr(signal_route, "get_provider", factory)
        response = client.post(
            "/v1/signal",
            json={
                "participant_id": str(participant_id),
                "platform": "claude",
                "answer_hash": f"{index:064x}",
                "prompt": "Tell me about the Eiffel Tower.",
                "answer": answers.get(name, ANSWER),
            },
            headers=headers,
        )
        assert response.status_code == 200, name
        body = response.json()
        body["processingLatencyMs"] = 0  # timing varies between runs
        samples[name] = body
    return samples


def test_backend_responses_match_the_extension_contract(client, auth_headers, monkeypatch):
    samples = _samples(client, auth_headers, monkeypatch)

    for name, body in samples.items():
        for flag in body["sentenceFlags"]:
            assert set(flag) <= {"sentenceIndex", "label", "explanation", "claimIds"}, name
            assert isinstance(flag["sentenceIndex"], int), name
    assert samples["fixture_medium_with_flags"]["sentenceFlags"], "contract must cover sentence flags"
    assert samples["selfconsistency_with_flags"]["sentenceFlags"], "contract must cover sentence flags"

    if os.environ.get("UPDATE_CONTRACT") == "1":
        CONTRACT.parent.mkdir(exist_ok=True)
        CONTRACT.write_text(
            json.dumps({"responses": samples}, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        pytest.skip("contract samples regenerated")
    committed = json.loads(CONTRACT.read_text(encoding="utf-8"))["responses"]
    assert samples == committed, (
        "Backend responses changed shape. If intentional, regenerate with UPDATE_CONTRACT=1 "
        "and make sure the extension contract test still passes."
    )
