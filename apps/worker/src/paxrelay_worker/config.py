"""Worker configuration via pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    """Environment-driven settings for the background worker."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/paxrelay"
    )
    database_pool_size: int = 5
    database_max_overflow: int = 10

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


def get_settings() -> WorkerSettings:
    """Return a fresh settings instance from the environment."""
    return WorkerSettings()
