import logging
from uuid import uuid4


def test_authenticated_capture_lifecycle_uses_mock_provider_and_deletes_data(
    client, auth_headers, caplog
):
    participant_id = uuid4()
    headers = auth_headers(participant_id)
    payload = {
        "participant_id": str(participant_id),
        "platform": "gemini",
        "answer_hash": "b" * 64,
        "prompt": "Explain calibration.",
        "answer": "Calibration compares confidence with accuracy.",
        "metadata": {"source": "integration-test"},
    }

    with caplog.at_level(logging.INFO):
        assert client.post("/v1/signal", json=payload, headers=headers).status_code == 403
        assert client.post(
            "/v1/consent",
            json={
                "participant_id": str(participant_id),
                "consent_version": "test-consent",
                "status": "granted",
            },
            headers=headers,
        ).status_code == 200
        response = client.post("/v1/signal", json=payload, headers=headers)

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "signal"
    assert result["confidence"] == "high"
    assert result["modelVersion"] == "mock-v1"
    assert result["score"] == 0.85
    assert "Explain calibration." not in caplog.text
    assert "Calibration compares confidence with accuracy." not in caplog.text

    assert client.post("/v1/signal", json=payload, headers=headers).status_code == 409
    assert client.post(
        "/v1/consent",
        json={
            "participant_id": str(participant_id),
            "consent_version": "test-consent",
            "status": "withdrawn",
        },
        headers=headers,
    ).status_code == 200
    assert client.post(
        "/v1/signal",
        json={**payload, "answer_hash": "c" * 64},
        headers=headers,
    ).status_code == 403
    assert client.delete(f"/v1/participant/{participant_id}", headers=headers).status_code == 204
    assert client.get(f"/v1/config?participant_id={participant_id}", headers=headers).status_code == 401


def test_session_failure_paths_and_associated_records_are_rejected(client, auth_headers):
    participant_id = uuid4()
    headers = auth_headers(participant_id)
    invalid_headers = {"Authorization": headers["Authorization"][:-1] + "x"}
    assert client.get(f"/v1/config?participant_id={participant_id}").status_code == 401
    assert client.get(f"/v1/config?participant_id={participant_id}", headers=invalid_headers).status_code == 401
    assert client.post("/v1/session/revoke", headers=headers).status_code == 204
    assert client.post(
        "/v1/consent",
        json={
            "participant_id": str(participant_id),
            "consent_version": "test-consent",
            "status": "granted",
        },
        headers=headers,
    ).status_code == 401


def test_reliability_fixture_provider_is_feature_flagged_and_does_not_store_raw_content(
    client, auth_headers, monkeypatch
):
    from app.config import get_settings
    from app.database.models import LiveSignal
    from app.database.connection import get_db

    participant_id = uuid4()
    headers = auth_headers(participant_id)
    assert client.post(
        "/v1/consent",
        json={
            "participant_id": str(participant_id),
            "consent_version": "test-consent",
            "status": "granted",
        },
        headers=headers,
    ).status_code == 200
    monkeypatch.setattr(get_settings(), "signal_provider", "reliability_fixture")
    payload = {
        "participant_id": str(participant_id),
        "platform": "chatgpt",
        "answer_hash": "d" * 64,
        "prompt": "What is the moon made of?",
        "answer": "The moon is made of cheese.",
    }
    response = client.post("/v1/signal", json=payload, headers=headers)
    assert response.status_code == 200
    assert response.json()["assessmentState"] == "insufficient_evidence"
    assert response.json()["claimAssessments"][0]["assessment"] == "insufficient_evidence"

    db = next(client.app.dependency_overrides[get_db]())
    try:
        record = db.query(LiveSignal).filter_by(participant_id=participant_id).one()
        assert record.prompt is None
        assert record.answer is None
        assert "moon" not in str(record.response_json).lower()
        assert all("claim" not in assessment for assessment in record.response_json["claimAssessments"])
    finally:
        db.close()
