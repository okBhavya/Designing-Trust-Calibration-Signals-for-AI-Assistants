from uuid import uuid4

import pytest


def consent(client, participant_id, headers, status="granted", version="test-consent"):
    return client.post(
        "/v1/consent",
        json={"participant_id": str(participant_id), "consent_version": version, "status": status},
        headers=headers,
    )


def signal_payload(participant_id, **overrides):
    payload = {
        "participant_id": str(participant_id),
        "platform": "chatgpt",
        "answer_hash": "a" * 64,
        "prompt": "Explain calibration",
        "answer": "Calibration compares confidence with accuracy.",
    }
    payload.update(overrides)
    return payload


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "calibrai-api"}


def test_raw_content_and_credentials_are_rejected_from_metadata(client, auth_headers):
    participant_id = uuid4()
    headers = auth_headers(participant_id)
    assert consent(client, participant_id, headers).status_code == 200
    response = client.post(
        "/v1/signal",
        json=signal_payload(participant_id, metadata={"answer": "must not be accepted"}),
        headers=headers,
    )
    assert response.status_code == 422


def test_cors_allows_authenticated_extension_requests(client):
    response = client.options(
        "/v1/signal",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "Authorization" in response.headers["access-control-allow-headers"]


def test_signal_requires_consent_and_returns_extension_compatible_response(client, auth_headers):
    participant_id = uuid4()
    headers = auth_headers(participant_id)
    assert client.post("/v1/signal", json=signal_payload(participant_id), headers=headers).status_code == 403
    assert consent(client, participant_id, headers).status_code == 200
    response = client.post("/v1/signal", json=signal_payload(participant_id), headers=headers)
    assert response.status_code == 200
    assert response.json()["confidence"] == "high"
    assert response.json()["modelVersion"] == "mock-v1"
    assert response.json()["status"] == "signal"


def test_signal_rejects_withdrawn_and_changed_consent(client, auth_headers):
    participant_id = uuid4()
    headers = auth_headers(participant_id)
    assert consent(client, participant_id, headers, status="withdrawn").status_code == 200
    assert client.post("/v1/signal", json=signal_payload(participant_id), headers=headers).status_code == 403
    assert consent(client, participant_id, headers, version="old-version").status_code == 200
    assert client.post("/v1/signal", json=signal_payload(participant_id), headers=headers).status_code == 403


@pytest.mark.parametrize("field,value", [("platform", "unknown"), ("answer_hash", "not-a-hash")])
def test_signal_rejects_invalid_values(client, auth_headers, field, value):
    participant_id = uuid4()
    headers = auth_headers(participant_id)
    consent(client, participant_id, headers)
    response = client.post(
        "/v1/signal",
        json=signal_payload(participant_id, **{field: value}),
        headers=headers,
    )
    assert response.status_code == 422


def test_participant_isolation_and_config(client, auth_headers):
    first, second = uuid4(), uuid4()
    first_headers = auth_headers(first)
    second_headers = auth_headers(second)
    consent(client, first, first_headers)
    assert client.get(f"/v1/config?participant_id={second}", headers=first_headers).status_code == 403
    assert client.get(f"/v1/config?participant_id={first}", headers=first_headers).json()["participant_id"] == str(first)
    assert client.get(f"/v1/config?participant_id={second}", headers=second_headers).status_code == 200


def test_events_validate_and_delete_cascades(client, auth_headers):
    participant_id = uuid4()
    headers = auth_headers(participant_id)
    consent(client, participant_id, headers)
    event = client.post(
        "/v1/events",
        json={"participant_id": str(participant_id), "event_type": "signal_shown", "platform": "gemini"},
        headers=headers,
    )
    assert event.status_code == 200
    invalid = client.post(
        "/v1/events",
        json={"participant_id": str(participant_id), "event_type": "not-an-event"},
        headers=headers,
    )
    assert invalid.status_code == 422
    assert client.delete(f"/v1/participant/{participant_id}", headers=headers).status_code == 204
    assert client.get(f"/v1/config?participant_id={participant_id}", headers=headers).status_code == 401


def test_duplicate_signal_is_rejected(client, auth_headers):
    participant_id = uuid4()
    headers = auth_headers(participant_id)
    consent(client, participant_id, headers)
    assert client.post("/v1/signal", json=signal_payload(participant_id), headers=headers).status_code == 200
    assert client.post("/v1/signal", json=signal_payload(participant_id), headers=headers).status_code == 409


def test_rate_limit(client, auth_headers, monkeypatch):
    from app.config import get_settings
    from app.core.rate_limit import limiter

    participant_id = uuid4()
    headers = auth_headers(participant_id)
    consent(client, participant_id, headers)
    monkeypatch.setattr(get_settings(), "rate_limit_requests", 1)
    limiter.clear()
    assert client.post("/v1/signal", json=signal_payload(participant_id), headers=headers).status_code == 200
    assert client.post(
        "/v1/signal",
        json=signal_payload(participant_id, answer_hash="b" * 64),
        headers=headers,
    ).status_code == 429


def test_authentication_and_revocation(client, auth_headers):
    participant_id = uuid4()
    headers = auth_headers(participant_id)
    assert client.get(f"/v1/config?participant_id={participant_id}").status_code == 401
    assert client.post("/v1/session/revoke", headers=headers).status_code == 204
    assert consent(client, participant_id, headers).status_code == 401


def test_expired_session_is_rejected(client, auth_headers, monkeypatch):
    import app.core.auth as auth

    participant_id = uuid4()
    headers = auth_headers(participant_id)
    original_time = auth.time.time()
    monkeypatch.setattr(auth.time, "time", lambda: original_time + 901)
    assert client.get(f"/v1/config?participant_id={participant_id}", headers=headers).status_code == 401
