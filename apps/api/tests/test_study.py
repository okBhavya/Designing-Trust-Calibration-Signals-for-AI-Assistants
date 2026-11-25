import csv
import importlib.util
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings, get_settings
from app.database.connection import get_db
from app.main import app, create_app
from app.services import study_service

CODE = "study-code-for-tests"
SHOWN = datetime(2026, 11, 26, 10, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def study(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "study_enrollment_code", SecretStr(CODE))
    monkeypatch.setattr(study_service, "_rng", random.Random(7))
    return client


def enroll(client, code=CODE, version="test-consent"):
    return client.post("/v1/study/enroll", json={"enrollment_code": code, "consent_version": version, "consent": True})


def enrolled(client):
    body = enroll(client).json()
    return body["participant_id"], {"Authorization": f"Bearer {body['access_token']}"}, body["condition"]


def trial(participant_id, condition, **overrides):
    payload = {
        "participant_id": participant_id, "question_id": "nq-153", "position": 0, "condition": condition,
        "ai_correct": True, "signal_level": "high", "signal_score": 1.0,
        "shown_at": SHOWN.isoformat(), "decided_at": (SHOWN + timedelta(seconds=7.5)).isoformat(),
        "decision": "accept", "self_confidence": 4, "final_correct": True,
    }
    payload.update(overrides)
    return payload


TRUST = {f"trust_{i}": 4 for i in range(1, 6)}


# --- enrollment and assignment ----------------------------------------------------------------------


def test_enrollment_is_closed_without_a_configured_code(client):
    assert enroll(client).status_code == 503


@pytest.mark.parametrize("code", ["wrong-code-entirely", "development-enrollment-secret-change-me"])
def test_enrollment_rejects_other_codes_including_the_extension_secret(study, code):
    assert enroll(study, code=code).status_code == 401


def test_enrollment_requires_the_current_consent_text_and_explicit_consent(study):
    assert enroll(study, version="2020-01-01").status_code == 409
    missing = study.post("/v1/study/enroll", json={"enrollment_code": CODE, "consent_version": "test-consent", "consent": False})
    assert missing.status_code == 422


def test_enrollment_creates_a_consenting_participant_with_a_working_token(study):
    response = enroll(study)
    assert response.status_code == 201
    body = response.json()
    assert body["condition"] in {"baseline", "A", "C"} and body["consent_version"] == "test-consent"
    headers = {"Authorization": f"Bearer {body['access_token']}"}
    config = study.get(f"/v1/config?participant_id={body['participant_id']}", headers=headers)
    assert config.status_code == 200
    assert config.json()["condition"] == body["condition"]
    # consent was recorded in the same call: consent-gated endpoints accept the participant at once
    event = study.post("/v1/events", json={"participant_id": body["participant_id"], "event_type": "signal_shown"}, headers=headers)
    assert event.status_code == 200


def test_assignment_is_balanced_across_the_three_conditions(study):
    conditions = [enroll(study).json()["condition"] for _ in range(9)]
    assert sorted(conditions) == sorted(["baseline", "A", "C"] * 3)
    # each block of three fills every condition once
    for block in range(3):
        assert set(conditions[block * 3:block * 3 + 3]) == {"baseline", "A", "C"}


def test_ties_are_broken_at_random_among_the_least_filled(monkeypatch):
    class FakeDb:
        def execute(self, _):
            class Rows:
                def all(self):
                    return [("baseline", 2), ("A", 1)]
            return Rows()

    picks = {study_service.assign_condition(FakeDb(), random.Random(seed)) for seed in range(20)}
    assert picks == {"C"}
    monkeypatch.setattr(FakeDb, "execute", lambda self, _: type("R", (), {"all": lambda s: [("baseline", 1)]})())
    picks = {study_service.assign_condition(FakeDb(), random.Random(seed)) for seed in range(40)}
    assert picks == {"A", "C"}


def test_config_flags_come_from_settings(study, monkeypatch):
    participant_id, headers, _ = enrolled(study)
    flags = study.get(f"/v1/config?participant_id={participant_id}", headers=headers).json()["feature_flags"]
    assert flags == {
        "mock_signal": True, "live_signal": False, "fixture_signal": False,
        "study_enrollment_open": True, "raw_conversation_storage": False,
    }
    monkeypatch.setattr(get_settings(), "signal_provider", "selfconsistency")
    flags = study.get(f"/v1/config?participant_id={participant_id}", headers=headers).json()["feature_flags"]
    assert flags["mock_signal"] is False and flags["live_signal"] is True


# --- trials --------------------------------------------------------------------------------------------


def test_trial_is_stored_and_a_retry_is_idempotent(study):
    participant_id, headers, condition = enrolled(study)
    first = study.post("/v1/study/trials", json=trial(participant_id, condition), headers=headers)
    assert first.status_code == 201 and first.json()["created"] is True
    retry = study.post("/v1/study/trials", json=trial(participant_id, condition), headers=headers)
    assert retry.status_code == 200
    assert retry.json() == {"id": first.json()["id"], "created": False}
    changed = study.post("/v1/study/trials", json=trial(participant_id, condition, decision="reject", final_correct=False), headers=headers)
    assert changed.status_code == 409


@pytest.mark.parametrize(
    "overrides",
    [
        {"final_correct": False},  # accept + ai_correct means the final answer was correct
        {"decided_at": (SHOWN - timedelta(seconds=1)).isoformat()},
        {"self_confidence": 6},
        {"self_confidence": 0},
        {"decision": "maybe"},
        {"signal_score": 1.5},
        {"shown_at": "2026-11-26T10:00:00"},  # no timezone
        {"question_id": "../etc"},
        {"prompt": "raw text is not accepted"},
    ],
)
def test_invalid_trials_are_rejected(study, overrides):
    participant_id, headers, condition = enrolled(study)
    assert study.post("/v1/study/trials", json=trial(participant_id, condition, **overrides), headers=headers).status_code == 422


def test_trial_condition_must_match_the_assignment(study):
    participant_id, headers, condition = enrolled(study)
    other = next(c for c in ("baseline", "A", "C") if c != condition)
    assert study.post("/v1/study/trials", json=trial(participant_id, other), headers=headers).status_code == 409


def test_trials_need_the_matching_session_and_current_consent(study, auth_headers):
    participant_id, headers, condition = enrolled(study)
    other_id, other_headers, _ = enrolled(study)
    assert study.post("/v1/study/trials", json=trial(participant_id, condition), headers=other_headers).status_code == 403
    assert study.post("/v1/study/trials", json=trial(participant_id, condition)).status_code == 401
    withdrawn = study.post(
        "/v1/consent", json={"participant_id": participant_id, "consent_version": "test-consent", "status": "withdrawn"},
        headers=headers,
    )
    assert withdrawn.status_code == 200
    assert study.post("/v1/study/trials", json=trial(participant_id, condition), headers=headers).status_code == 403


# --- questionnaires --------------------------------------------------------------------------------------


def test_questionnaires_are_stored_and_retries_are_idempotent(study):
    participant_id, headers, _ = enrolled(study)
    body = {"participant_id": participant_id, "instrument": "trust", "responses": TRUST}
    assert study.post("/v1/study/questionnaire", json=body, headers=headers).status_code == 201
    assert study.post("/v1/study/questionnaire", json=body, headers=headers).status_code == 200
    changed = {**body, "responses": {**TRUST, "trust_1": 7}}
    assert study.post("/v1/study/questionnaire", json=changed, headers=headers).status_code == 409
    demographics = {"participant_id": participant_id, "instrument": "demographics",
                    "responses": {"age_band": "25-34", "ai_experience": 3}}
    assert study.post("/v1/study/questionnaire", json=demographics, headers=headers).status_code == 201


@pytest.mark.parametrize(
    "instrument,responses",
    [
        ("trust", {**TRUST, "trust_5": 8}),
        ("trust", {**TRUST, "trust_5": True}),
        ("trust", {**TRUST, "trust_5": "4"}),
        ("trust", {k: v for k, v in TRUST.items() if k != "trust_3"}),
        ("trust", {**TRUST, "comment": 4}),
        ("demographics", {"age_band": "17", "ai_experience": 3}),
        ("demographics", {"age_band": "25-34", "ai_experience": 6}),
        ("feedback", TRUST),
    ],
)
def test_invalid_questionnaires_are_rejected(study, instrument, responses):
    participant_id, headers, _ = enrolled(study)
    body = {"participant_id": participant_id, "instrument": instrument, "responses": responses}
    assert study.post("/v1/study/questionnaire", json=body, headers=headers).status_code == 422


def test_questionnaires_need_current_consent(study):
    participant_id, headers, _ = enrolled(study)
    study.post("/v1/consent", json={"participant_id": participant_id, "consent_version": "test-consent", "status": "withdrawn"}, headers=headers)
    body = {"participant_id": participant_id, "instrument": "trust", "responses": TRUST}
    assert study.post("/v1/study/questionnaire", json=body, headers=headers).status_code == 403


def test_tooltip_opened_events_are_accepted(study):
    participant_id, headers, _ = enrolled(study)
    response = study.post(
        "/v1/events",
        json={"participant_id": participant_id, "event_type": "tooltip_opened",
              "metadata": {"question_id": "nq-153", "condition": "C", "phase": "main", "sentence_index": "0"}},
        headers=headers,
    )
    assert response.status_code == 200


# --- CORS and production guards ---------------------------------------------------------------------------


def test_study_origin_is_configurable_through_the_environment(monkeypatch):
    monkeypatch.setenv("CALIBRAI_STUDY_ORIGINS", "https://study.example.org, http://localhost:4173")
    assert Settings().study_origins == ["https://study.example.org", "http://localhost:4173"]
    monkeypatch.setattr(get_settings(), "study_origins", ["https://study.example.org"])
    preflight = TestClient(create_app()).options(
        "/v1/study/enroll",
        headers={"Origin": "https://study.example.org", "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "content-type"},
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "https://study.example.org"


def production(**overrides) -> Settings:
    values = {
        "environment": "production",
        "session_signing_secret": "a-production-signing-secret-of-32-chars!",
        "enrollment_secret": "a-production-extension-secret",
    }
    values.update(overrides)
    return Settings(**values)


def test_production_guards_still_pass_with_a_sound_study_setup():
    production().validate_deployment_security()
    production(study_enrollment_code="a-long-study-code", study_origins=["https://study.example.org"]).validate_deployment_security()


@pytest.mark.parametrize(
    "overrides,message",
    [
        ({"study_enrollment_code": "short"}, "at least 12"),
        ({"study_enrollment_code": "a-production-extension-secret"}, "must differ"),
        ({"study_origins": ["http://study.example.org"]}, "https"),
    ],
)
def test_production_rejects_unsafe_study_settings(overrides, message):
    with pytest.raises(RuntimeError, match=message):
        production(**overrides).validate_deployment_security()


# --- export --------------------------------------------------------------------------------------------


def _load_export_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "export_study.py"
    spec = importlib.util.spec_from_file_location("export_study", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_study"] = module
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_export_writes_study_csvs_without_personal_data(study, auth_headers, tmp_path):
    export_study = _load_export_module()
    participant_id, headers, condition = enrolled(study)
    study.post("/v1/study/trials", json=trial(participant_id, condition), headers=headers)
    study.post("/v1/study/trials", json=trial(participant_id, condition, question_id="nq-38", position=1,
                                              decision="reject", final_correct=False), headers=headers)
    study.post("/v1/study/questionnaire", json={"participant_id": participant_id, "instrument": "trust", "responses": TRUST}, headers=headers)
    study.post("/v1/events", json={"participant_id": participant_id, "event_type": "tooltip_opened",
                                   "metadata": {"question_id": "nq-153", "phase": "main", "sentence_index": "0"}}, headers=headers)
    # excluded: a withdrawn study participant and an extension participant (no study condition)
    withdrawn_id, withdrawn_headers, withdrawn_condition = enrolled(study)
    study.post("/v1/study/trials", json=trial(withdrawn_id, withdrawn_condition), headers=withdrawn_headers)
    study.post("/v1/consent", json={"participant_id": withdrawn_id, "consent_version": "test-consent", "status": "withdrawn"}, headers=withdrawn_headers)
    extension_id = uuid4()
    extension_headers = auth_headers(extension_id)
    study.post("/v1/consent", json={"participant_id": str(extension_id), "consent_version": "test-consent", "status": "granted"}, headers=extension_headers)

    db = next(app.dependency_overrides[get_db]())
    counts = export_study.export_study(db, tmp_path)
    assert counts == {"participants": 1, "trials": 2, "events": 1, "questionnaires": 5}

    participants = read_csv(tmp_path / "participants.csv")
    assert participants == [{"participant_id": participant_id, "condition": condition, "consent_version": "test-consent"}]
    trials = read_csv(tmp_path / "trials.csv")
    assert [row["question_id"] for row in trials] == ["nq-153", "nq-38"]
    assert trials[0]["decision_ms"] == "7500" and trials[0]["shown_at"] == SHOWN.isoformat()
    assert trials[1]["final_correct"] == "False"
    events = read_csv(tmp_path / "events.csv")
    assert events[0]["event_type"] == "tooltip_opened" and events[0]["sentence_index"] == "0"
    items = read_csv(tmp_path / "questionnaires.csv")
    assert [row["item"] for row in items] == [f"trust_{i}" for i in range(1, 6)]
