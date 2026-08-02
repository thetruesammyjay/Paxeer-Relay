"""Gateway configuration via pydantic-settings.

All runtime configuration is read from environment variables (or a local
``.env`` file) exactly once at startup and injected into the adapters and
session factory. No module in the gateway reads ``os.environ`` directly.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):
    """Environment-driven settings for the 402LXP gateway."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    app_name: str = "PaxRelay Gateway"
    log_level: str = "INFO"

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/paxrelay"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Paxeer adapter selection
    use_mock_adapter: bool = True
    paxeer_chain_id: int = 125
    paxeer_rpc_url: str = "https://public-rpc.paxeer.app/rpc"
    layerx_api_url: str = ""

    # 402LXP
    lxp402_enabled: bool = True
    lxp402_quote_ttl_seconds: int = 300
    lxp402_max_clock_skew_seconds: int = 30
    lxp402_require_request_hash: bool = True

    # Gateway proxy limits
    gateway_request_timeout_seconds: int = 30
    gateway_connect_timeout_seconds: int = 5
    gateway_max_request_bytes: int = 1_048_576
    gateway_max_response_bytes: int = 10_485_760

    # Provider routing
    router_default_strategy: str = "balanced"
    router_max_provider_attempts: int = 2

    # Receipt signing
    receipt_signing_backend: str = "local"
    receipt_signing_private_key: str = ""
    receipt_signing_key_id: str = "local-development"


@lru_cache
def get_settings() -> GatewaySettings:
    """Return the process-wide cached gateway settings."""
    return GatewaySettings()
