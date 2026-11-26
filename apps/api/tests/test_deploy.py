"""The deploy configs must describe a deployment that passes the production guards."""

from pathlib import Path

import pytest

from app.config import Settings

API_DIR = Path(__file__).resolve().parents[1]
REPO = API_DIR.parents[1]
yaml = pytest.importorskip("yaml")

# What an operator enters for the `sync: false` and generated values.
OPERATOR_VALUES = {
    "CALIBRAI_DATABASE_URL": "postgresql://calibrai:secret@db.internal/calibrai",
    "CALIBRAI_SESSION_SIGNING_SECRET": "x" * 44,
    "CALIBRAI_ENROLLMENT_SECRET": "y" * 44,
    "LLM_API_KEY": "sk-ant-test",
    "CALIBRAI_LLM_EXTRACTION_MODEL": "",
    "CALIBRAI_STUDY_ENROLLMENT_CODE": "a-long-study-code",
    "CALIBRAI_STUDY_ORIGINS": "https://calibrai-study.vercel.app",
    "CALIBRAI_API_ORIGINS": "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
}


def blueprint_env() -> dict:
    blueprint = yaml.safe_load((API_DIR / "render.yaml").read_text(encoding="utf-8"))
    (service,) = blueprint["services"]
    return {item["key"]: item for item in service["envVars"]}


def test_render_blueprint_passes_the_production_guards(monkeypatch):
    env = blueprint_env()
    for key, item in env.items():
        monkeypatch.setenv(key, str(item["value"]) if "value" in item else OPERATOR_VALUES[key])
    settings = Settings(_env_file=None)
    assert settings.environment == "production"
    assert settings.signal_provider == "selfconsistency" and settings.llm_model == "claude-haiku-5-5"
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.llm_extraction_model is None
    settings.validate_deployment_security()


def test_render_blueprint_keeps_secrets_out_of_the_repository():
    env = blueprint_env()
    for key in ("LLM_API_KEY", "CALIBRAI_SESSION_SIGNING_SECRET", "CALIBRAI_ENROLLMENT_SECRET", "CALIBRAI_STUDY_ENROLLMENT_CODE"):
        assert "value" not in env[key], key


def test_start_commands_migrate_before_serving():
    procfile = (API_DIR / "Procfile").read_text(encoding="utf-8")
    blueprint = yaml.safe_load((API_DIR / "render.yaml").read_text(encoding="utf-8"))
    for command in (procfile.split(":", 1)[1].strip(), blueprint["services"][0]["startCommand"]):
        assert command.startswith("alembic upgrade head && uvicorn app.main:app")


def test_every_deploy_variable_is_documented():
    documented = (REPO / "docs" / "DEPLOY.md").read_text(encoding="utf-8")
    for key in blueprint_env():
        assert f"`{key}`" in documented, key
    for key in ("WXT_API_ORIGIN", "WXT_EXTENSION_KEY", "VITE_API_BASE_URL", "VITE_CONSENT_VERSION", "VITE_DEMO"):
        assert f"`{key}`" in documented, key
