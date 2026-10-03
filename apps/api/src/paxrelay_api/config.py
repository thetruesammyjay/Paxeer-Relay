"""Control-plane API configuration via pydantic-settings."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from paxrelay_db import normalize_async_database_url


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
        hide_input_in_errors=True,
    )

    # Application
    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = "PaxRelay API"
    log_level: str = "INFO"
    api_base_url: str = "http://localhost:8000"
    api_cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias="API_CORS_ORIGINS",
    )
    readiness_timeout_seconds: float = Field(default=3.0, gt=0, le=15)
    api_max_request_bytes: int = Field(default=1_048_576, ge=1_024, le=10_485_760)
    # Public manifest used by clients to verify signed execution receipts.
    # The endpoint reads it for each request so key rotation and revocation
    # updates become visible without restarting the API.
    receipt_public_keyring_file: Path | None = None

    # Redis-backed request limits are on by default in staging/production.
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        validation_alias=AliasChoices("REDIS_URL", "RAILWAY_REDIS_URL"),
        repr=False,
    )
    redis_key_prefix: str = Field(
        default="paxrelay",
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9:_-]+$",
    )
    api_rate_limit_enabled: bool | None = None
    api_rate_limit_max_requests: int = Field(default=300, ge=1, le=100_000)
    api_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    analytics_rollup_max_age_seconds: int = Field(default=180, ge=30, le=3600)

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/paxrelay",
        repr=False,
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Authentication (reserved for JWT-backed dashboard sessions).
    # No default — the process must supply these via environment or .env;
    # a missing value raises a startup error rather than shipping insecure defaults.
    auth_secret: str = Field(repr=False)
    jwt_issuer: str = "paxrelay"
    jwt_audience: str = "paxrelay-api"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 2_592_000

    # Used to encrypt per-endpoint secrets so workers can sign deliveries.
    # Non-production can use AUTH_SECRET; production must set a separate,
    # stable key and retain it while encrypted values are stored.
    webhook_encryption_key: str | None = Field(default=None, repr=False)

    @field_validator("database_url", mode="before")
    @classmethod
    def use_async_postgres_driver(cls, value: object) -> object:
        """Accept common provider URLs but configure SQLAlchemy with asyncpg."""
        if not isinstance(value, str):
            return value
        return normalize_async_database_url(value)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}:
            raise ValueError("log_level must be CRITICAL, ERROR, WARNING, INFO, or DEBUG")
        return normalized

    @field_validator("api_cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        """Accept exact browser origins only; paths and wildcard hosts are unsafe."""
        normalized: list[str] = []
        for origin in origins:
            origin = origin.strip().rstrip("/")
            try:
                parsed = urlsplit(origin)
                _ = parsed.port
            except ValueError as exc:
                raise ValueError("API_CORS_ORIGINS must contain valid origins") from exc
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or parsed.path
                or parsed.query
                or parsed.fragment
                or "*" in parsed.netloc
            ):
                raise ValueError(
                    "API_CORS_ORIGINS entries must be exact HTTP or HTTPS origins"
                )
            normalized.append(origin.lower())
        if len(normalized) != len(set(normalized)):
            raise ValueError("API_CORS_ORIGINS cannot contain duplicates")
        return normalized

    @model_validator(mode="after")
    def require_production_secrets(self) -> "ApiSettings":
        if self.app_env in {"staging", "production"} and not self.api_cors_origins:
            raise ValueError("Set at least one HTTPS origin in API_CORS_ORIGINS")
        if self.app_env in {"staging", "production"} and any(
            not origin.startswith("https://") for origin in self.api_cors_origins
        ):
            raise ValueError("Staging and production API_CORS_ORIGINS must use HTTPS")
        if self.app_env == "production":
            if self.api_rate_limit_enabled is False:
                raise ValueError("API rate limiting cannot be disabled in production")
            secrets_to_check = {
                "AUTH_SECRET": self.auth_secret,
                "WEBHOOK_ENCRYPTION_KEY": self.webhook_encryption_key or "",
            }
            for name, secret in secrets_to_check.items():
                lowered = secret.lower()
                if len(secret) < 40 or any(
                    marker in lowered
                    for marker in (
                        "replace-me",
                        "change-me",
                        "changeme",
                        "example",
                        "placeholder",
                    )
                ):
                    raise ValueError(
                        f"{name} must be at least 40 characters and not a template value"
                    )
            if self.webhook_encryption_key == self.auth_secret:
                raise ValueError("WEBHOOK_ENCRYPTION_KEY must differ from AUTH_SECRET")
        return self

    @property
    def rate_limiting_enabled(self) -> bool:
        """Default to shared rate limiting in staging and production."""
        if self.api_rate_limit_enabled is not None:
            return self.api_rate_limit_enabled
        return self.app_env in {"staging", "production"}


def get_settings() -> ApiSettings:
    """Return a fresh :class:`ApiSettings` instance from the environment.

    Caching is intentionally omitted: pydantic-settings re-reads the
    environment (and .env file) on each call, which keeps tests and
    hot-reload predictable.  If startup performance becomes a concern,
    cache at the caller's discretion rather than here.
    """
    return ApiSettings()
