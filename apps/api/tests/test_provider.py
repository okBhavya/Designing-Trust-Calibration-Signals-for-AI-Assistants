from uuid import uuid4

import pytest

from app.schemas.signal import SignalRequest
from app.services.signal_service import MockSignalProvider


def test_mock_provider_is_platform_neutral():
    provider = MockSignalProvider()
    request = SignalRequest(
        participant_id=uuid4(),
        platform="chatgpt",
        answer_hash="a" * 64,
        prompt="hello",
        answer="world",
    )
    response = provider.evaluate(request)
    assert response.status == "signal"
    assert response.model_version == "mock-v1"
    assert response.confidence == "high"
    assert 0 <= response.score <= 1


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
