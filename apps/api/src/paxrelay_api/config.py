"""Control-plane API configuration via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    """Environment-driven settings for the control-plane API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_name: str = "PaxRelay API"
    log_level: str = "INFO"
    api_base_url: str = "http://localhost:8000"

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/paxrelay"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Authentication (reserved for JWT-backed dashboard sessions)
    auth_secret: str = "replace-me-with-a-secure-random-string"
    jwt_issuer: str = "paxrelay"
    jwt_audience: str = "paxrelay-api"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 2_592_000

    # Webhooks
    webhook_signing_secret: str = "replace-me-with-a-secure-random-string"


@lru_cache
def get_settings() -> ApiSettings:
    """Return the process-wide cached API settings."""
    return ApiSettings()
