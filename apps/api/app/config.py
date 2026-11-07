from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
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
    session_ttl_seconds: int = Field(default=900, ge=60, le=86_400)
    enrollment_secret: str = "development-enrollment-secret-change-me"
    signal_provider: Literal["mock", "reliability_fixture"] = "mock"
    evidence_fixture_dir: str = "data/evidence_fixtures"
    evidence_fixture_path: str | None = None
    store_raw_conversation: bool = False

    @field_validator("api_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    def validate_deployment_security(self) -> None:
        if self.environment == "production":
            if self.session_signing_secret == "development-only-change-this-secret-32chars":
                raise RuntimeError("Production requires CALIBRAI_SESSION_SIGNING_SECRET")
            if self.enrollment_secret == "development-enrollment-secret-change-me":
                raise RuntimeError("Production requires CALIBRAI_ENROLLMENT_SECRET")
            if self.signal_provider == "reliability_fixture":
                raise RuntimeError("Production cannot use the reliability fixture provider")
        if self.environment.lower() in {"production", "participant", "study"} and self.store_raw_conversation:
            raise RuntimeError("Raw conversation storage is disabled in participant-facing environments")


@lru_cache
def get_settings() -> Settings:
    return Settings()
