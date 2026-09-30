"""Worker configuration via pydantic-settings."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """Environment-driven settings for the background worker."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/paxrelay"
    )
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Webhook delivery
    auth_secret: str | None = Field(default=None, repr=False)
    webhook_encryption_key: str | None = Field(default=None, repr=False)
    webhook_max_attempts: int = Field(default=8, ge=1, le=20)
    webhook_initial_retry_seconds: int = Field(default=30, ge=1, le=3600)
    webhook_request_timeout_seconds: float = Field(default=10, gt=0, le=60)
    webhook_max_request_bytes: int = Field(default=1_048_576, ge=1024, le=10_485_760)
    webhook_max_response_bytes: int = Field(default=65_536, ge=1024, le=1_048_576)
    webhook_delivery_batch_size: int = Field(default=50, ge=1, le=500)
    webhook_delivery_concurrency: int = Field(default=10, ge=1, le=50)
    webhook_delivery_lease_seconds: int = Field(default=120, ge=30, le=600)

    # Redis — job queues and pub/sub
    redis_url: str = "redis://localhost:6379/0"

    # Upstream
    layerx_rpc_url: str = "http://localhost:9545"
    paxeer_api_url: str = "https://api.paxeer.network"

    # Reconciliation
    settlement_poll_interval_seconds: int = 30
    reconciliation_lookback_hours: int = 24

    # Analytics aggregation
    analytics_flush_interval_seconds: int = 60

    @model_validator(mode="after")
    def require_production_webhook_key(self) -> "WorkerSettings":
        if (
            self.webhook_delivery_lease_seconds
            <= self.webhook_request_timeout_seconds + 30
        ):
            raise ValueError(
                "WEBHOOK_DELIVERY_LEASE_SECONDS must exceed the webhook request timeout"
            )
        if self.app_env == "production":
            key = self.webhook_encryption_key or ""
            invalid_markers = (
                "replace-me",
                "change-me",
                "changeme",
                "example",
                "placeholder",
            )
            if len(key) < 40 or any(
                marker in key.lower() for marker in invalid_markers
            ):
                raise ValueError(
                    "WEBHOOK_ENCRYPTION_KEY must be at least 40 characters and not a template value"
                )
            if self.auth_secret and key == self.auth_secret:
                raise ValueError("WEBHOOK_ENCRYPTION_KEY must differ from AUTH_SECRET")
        return self


def get_settings() -> WorkerSettings:
    """Return a fresh settings instance from the environment."""
    return WorkerSettings()
