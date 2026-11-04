from uuid import uuid4

from app.schemas.signal import SignalRequest
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
