from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CALIBRAI_", env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./calibrai.db"
    environment: str = "development"
    api_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "https://chatgpt.com",
            "https://claude.ai",
            "https://gemini.google.com",
            "http://localhost:5173",
        ]
    )
    consent_version: str = "2026-11-04"
    rate_limit_requests: int = Field(default=60, ge=1, le=10_000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=86_400)
    max_request_bytes: int = Field(default=65_536, ge=1_024, le=10_485_760)
    session_signing_secret: str = "development-only-change-this-secret-32chars"
    # 24h for the pilot: the extension has no token refresh flow yet, so a short
    # lifetime would force participants to paste a new token every 15 minutes.
    session_ttl_seconds: int = Field(default=86_400, ge=60, le=86_400)
    enrollment_secret: str = "development-enrollment-secret-change-me"
    signal_provider: Literal["mock", "reliability_fixture", "selfconsistency"] = "mock"
    # LLM used by the selfconsistency provider. The key is read from LLM_API_KEY (no prefix).
    llm_api_key: SecretStr | None = Field(default=None, validation_alias=AliasChoices("LLM_API_KEY"))
    llm_model: str = "claude-opus-5-5"
    llm_effort: Literal["low", "medium", "high", "max"] = "low"
    selfconsistency_samples: int = Field(default=5, ge=2, le=10)
    selfconsistency_temperature: float = Field(default=0.7, ge=0, le=2)
    selfconsistency_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    selfconsistency_high_threshold: float = Field(default=0.80, ge=0, le=1)
    selfconsistency_medium_threshold: float = Field(default=0.60, ge=0, le=1)
    evidence_fixture_dir: str = "data/evidence_fixtures"
    evidence_fixture_path: str | None = None
    store_raw_conversation: bool = False

    @field_validator("api_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_selfconsistency_thresholds(self) -> "Settings":
        if self.selfconsistency_medium_threshold > self.selfconsistency_high_threshold:
            raise ValueError("selfconsistency_medium_threshold cannot exceed selfconsistency_high_threshold")
        return self

    def validate_deployment_security(self) -> None:
        if self.environment == "production":
            if self.session_signing_secret == "development-only-change-this-secret-32chars":
                raise RuntimeError("Production requires CALIBRAI_SESSION_SIGNING_SECRET")
            if self.enrollment_secret == "development-enrollment-secret-change-me":
                raise RuntimeError("Production requires CALIBRAI_ENROLLMENT_SECRET")
            if self.signal_provider == "reliability_fixture":
                raise RuntimeError("Production cannot use the reliability fixture provider")
            if self.signal_provider == "selfconsistency" and (
                self.llm_api_key is None or not self.llm_api_key.get_secret_value()
            ):
                raise RuntimeError("Production requires LLM_API_KEY for the selfconsistency provider")
        if self.environment.lower() in {"production", "participant", "study"} and self.store_raw_conversation:
            raise RuntimeError("Raw conversation storage is disabled in participant-facing environments")


@lru_cache
def get_settings() -> Settings:
    return Settings()
