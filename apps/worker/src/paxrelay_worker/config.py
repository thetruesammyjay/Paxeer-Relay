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

    # Paxeer and LayerX adapters. Keep names aligned with the API and gateway.
    use_mock_adapter: bool = True
    paxeer_chain_id: int = Field(default=125, ge=1)
    paxeer_rpc_url: str = "https://public-rpc.paxeer.app/rpc"
    layerx_api_url: str | None = None
    paxeer_settlement_api_url: str | None = None
    paxeer_l1_settlement_contract_address: str | None = Field(
        default=None, pattern=r"^0x[a-fA-F0-9]{40}$"
    )
    paxeer_l1_commitment_event_topic: str | None = Field(
        default=None, pattern=r"^0x[a-fA-F0-9]{64}$"
    )
    paxeer_l1_confirmation_blocks: int | None = Field(default=None, ge=1, le=100_000)
    paxeer_adapter_timeout_seconds: float = Field(default=15, gt=0, le=60)

    # Reconciliation
    settlement_poll_interval_seconds: int = 30
    reconciliation_lookback_hours: int = 24
    reconciliation_batch_size: int = Field(default=50, ge=1, le=500)
    reconciliation_concurrency: int = Field(default=10, ge=1, le=50)
    reconciliation_claim_lease_seconds: int = Field(default=120, ge=30, le=600)
    reconciliation_retry_initial_seconds: int = Field(default=30, ge=1, le=3600)
    reconciliation_retry_max_seconds: int = Field(default=3600, ge=30, le=86400)

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
        if self.reconciliation_claim_lease_seconds <= self.paxeer_adapter_timeout_seconds * 5:
            raise ValueError(
                "RECONCILIATION_CLAIM_LEASE_SECONDS must exceed five adapter timeouts"
            )
        if self.reconciliation_retry_max_seconds < self.reconciliation_retry_initial_seconds:
            raise ValueError(
                "RECONCILIATION_RETRY_MAX_SECONDS must be at least the initial retry delay"
            )
        if not self.use_mock_adapter:
            if not self.layerx_api_url or not self.paxeer_settlement_api_url:
                raise ValueError(
                    "LAYERX_API_URL and PAXEER_SETTLEMENT_API_URL are required when USE_MOCK_ADAPTER is false"
                )
            if not self.layerx_api_url.startswith("https://"):
                raise ValueError("LAYERX_API_URL must use HTTPS when using the official adapter")
            if not self.paxeer_settlement_api_url.startswith("https://"):
                raise ValueError(
                    "PAXEER_SETTLEMENT_API_URL must use HTTPS when using the official adapter"
                )
        if self.app_env == "production":
            if self.use_mock_adapter:
                raise ValueError("USE_MOCK_ADAPTER must be false in production")
            if self.paxeer_chain_id != 125:
                raise ValueError("PAXEER_CHAIN_ID must be 125 in production")
            if not self.paxeer_rpc_url.startswith("https://"):
                raise ValueError("PAXEER_RPC_URL must use HTTPS in production")
            if not self.layerx_api_url or not self.layerx_api_url.startswith("https://"):
                raise ValueError("LAYERX_API_URL must use HTTPS in production")
            if (
                not self.paxeer_settlement_api_url
                or not self.paxeer_settlement_api_url.startswith("https://")
            ):
                raise ValueError(
                    "PAXEER_SETTLEMENT_API_URL must use HTTPS in production"
                )
            if not self.paxeer_l1_settlement_contract_address:
                raise ValueError(
                    "PAXEER_L1_SETTLEMENT_CONTRACT_ADDRESS is required in production"
                )
            if not self.paxeer_l1_commitment_event_topic:
                raise ValueError(
                    "PAXEER_L1_COMMITMENT_EVENT_TOPIC is required in production"
                )
            if self.paxeer_l1_confirmation_blocks is None:
                raise ValueError(
                    "PAXEER_L1_CONFIRMATION_BLOCKS is required in production"
                )
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
