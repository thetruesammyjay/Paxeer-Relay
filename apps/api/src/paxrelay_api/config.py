"""Control-plane API configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_API_DIRECTORY = _REPOSITORY_ROOT / "apps" / "api"


class ApiSettings(BaseSettings):
    """Environment-driven settings for the control-plane API."""

    model_config = SettingsConfigDict(
        # Support both the repository's shared .env and a service-local file
        # when uvicorn is started from apps/api. Environment variables still
        # take precedence over values loaded from either file.
        env_file=(_REPOSITORY_ROOT / ".env", _API_DIRECTORY / ".env"),
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

    # Authentication (reserved for JWT-backed dashboard sessions).
    # No default — the process must supply these via environment or .env;
    # a missing value raises a startup error rather than shipping insecure defaults.
    auth_secret: str
    jwt_issuer: str = "paxrelay"
    jwt_audience: str = "paxrelay-api"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 2_592_000

    # Webhooks — no default, same reasoning as auth_secret.
    webhook_signing_secret: str


def get_settings() -> ApiSettings:
    """Return a fresh :class:`ApiSettings` instance from the environment.

    Caching is intentionally omitted: pydantic-settings re-reads the
    environment (and .env file) on each call, which keeps tests and
    hot-reload predictable.  If startup performance becomes a concern,
    cache at the caller's discretion rather than here.
    """
    return ApiSettings()
