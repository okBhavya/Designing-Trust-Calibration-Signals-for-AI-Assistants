from uuid import uuid4

import pytest

from app.schemas.signal import SignalRequest
from app.services.reliability_service import (
    FixtureEvidenceRetriever,
    Claim,
    ProviderUnavailableError,
    ReliabilityFixtureProvider,
    Verification,
    aggregate,
    extract_claims,
    normalize_answer,
    resolve_fixture_path,
)
from app.services.signal_service import MockSignalProvider


def test_mock_provider_is_platform_neutral():
    provider = MockSignalProvider()
    response = provider.evaluate(
        SignalRequest(
            participant_id=uuid4(),
            platform="claude",
            answer_hash="a" * 64,
            answer="A short answer.",
        )
    )
    assert response.model_version == "mock-v1"
    assert response.confidence == "high"
    assert 0 <= response.score <= 1


def test_reliability_pipeline_preserves_sentence_indices_and_claim_cap():
    sentences = normalize_answer("First fact. Second fact.\n```python\nx = 1\n```")
    claims = extract_claims(sentences)
    assert [claim.sentence_index for claim in claims] == [0, 1]
    assert all(claim.sentence_index >= 0 for claim in claims)


def test_aggregation_counts_insufficient_evidence_in_denominator():
    provider = ReliabilityFixtureProvider(
        FixtureEvidenceRetriever(
            records=[{
                "claim": "The sky is blue because sunlight scatters through the atmosphere.",
                "sourceId": "src-1",
                "url": "https://example.test/sky",
                "domain": "example.test",
                "snippet": "The sky is blue.",
                "relevanceScore": 1,
                "quality": 1,
                "independenceGroup": "example",
            }]
        )
    )
    request = SignalRequest(
        participant_id=uuid4(),
        platform="chatgpt",
        answer_hash="a" * 64,
        answer="The sky is blue because sunlight scatters through the atmosphere. The moon is made of cheese.",
    )
    response = provider.evaluate(request)
    assert response.assessment_state == "medium"
    assert response.claim_assessments[0].assessment == "supported"
    assert response.claim_assessments[1].assessment == "insufficient_evidence"


def test_empty_reliability_input_is_unavailable_not_low():
    request = SignalRequest(
        participant_id=uuid4(),
        platform="gemini",
        answer_hash="b" * 64,
        answer=None,
    )
    response = ReliabilityFixtureProvider().evaluate(request)
    assert response.assessment_state == "unavailable"
    assert response.confidence is None


def test_aggregation_uses_frozen_sixty_percent_low_threshold():
    claims = [
        Claim(f"c{i}", f"claim {i}", i, "factual", materiality, False)
        for i, materiality in enumerate(["medium", "medium", "low", "low", "low"])
    ]
    verifications = tuple(
        Verification(
            claim,
            "supported" if index < 2 else "insufficient_evidence",
            "moderate",
            0.5,
            (),
            (),
            "",
        )
        for index, claim in enumerate(claims)
    )
    state, _, score = aggregate(verifications)
    assert score == pytest.approx(4 / 7)
    assert state == "low"


def test_missing_evidence_fixture_is_explicitly_unavailable():
    with pytest.raises(ProviderUnavailableError):
        FixtureEvidenceRetriever("missing-evidence-fixture.json")


def test_fixture_path_cannot_escape_configured_directory(tmp_path):
    with pytest.raises(ProviderUnavailableError, match="outside"):
        resolve_fixture_path("..\\secrets.json", str(tmp_path / "fixtures"))


def test_raw_storage_is_rejected_for_participant_environment(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "participant")
    monkeypatch.setattr(settings, "store_raw_conversation", True)
    with pytest.raises(RuntimeError, match="Raw conversation"):
        settings.validate_deployment_security()


def test_reliability_fixture_is_rejected_in_production(monkeypatch):
    from app.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "session_signing_secret", "secure-session-secret")
    monkeypatch.setattr(settings, "enrollment_secret", "secure-enrollment-secret")
    monkeypatch.setattr(settings, "signal_provider", "reliability_fixture")
    with pytest.raises(RuntimeError, match="fixture provider"):
        settings.validate_deployment_security()
