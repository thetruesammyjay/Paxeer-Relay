"""Gateway configuration via pydantic-settings.

All runtime configuration is read from environment variables (or a local
``.env`` file) exactly once at startup and injected into the adapters and
session factory. No module in the gateway reads ``os.environ`` directly.
"""

from __future__ import annotations

import ipaddress
import re
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_MAINNET_PAXEER_RPC_URL = "https://public-rpc.paxeer.app/rpc"


class GatewaySettings(BaseSettings):
    """Environment-driven settings for the 402LXP gateway."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_name: str = "PaxRelay Gateway"
    log_level: str = "INFO"
    readiness_timeout_seconds: float = Field(default=3.0, gt=0, le=15)

    # Shared Redis request limits are enabled by default outside development.
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
    gateway_rate_limit_enabled: bool | None = None
    gateway_rate_limit_max_requests: int = Field(default=120, ge=1, le=100_000)
    gateway_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)

    # Comma-separated exact hostnames trusted as provider destinations.
    provider_endpoint_host_allowlist: str = Field(default="", max_length=4096)

    @field_validator("provider_endpoint_host_allowlist")
    @classmethod
    def validate_provider_endpoint_host_allowlist(cls, value: str) -> str:
        for raw_host in value.split(","):
            host = raw_host.strip().rstrip(".")
            if not host:
                continue
            try:
                ipaddress.ip_address(host)
                continue
            except ValueError:
                pass
            try:
                ascii_host = host.encode("idna").decode("ascii")
            except UnicodeError as exc:
                raise ValueError(
                    "provider allowlist contains an invalid hostname"
                ) from exc
            labels = ascii_host.split(".")
            if len(ascii_host) > 253 or any(
                len(label) > 63
                or re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
                is None
                for label in labels
            ):
                raise ValueError("provider allowlist contains an invalid hostname")
        return value

    # Database
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/paxrelay"
    )
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Paxeer adapter selection
    use_mock_adapter: bool = True
    paxeer_network_environment: Literal[
        "mainnet", "testnet", "staging"
    ] = "mainnet"
    paxeer_chain_id: int = Field(default=125, ge=1)
    paxeer_rpc_url: str = _MAINNET_PAXEER_RPC_URL
    layerx_api_url: str = ""

    # 402LXP
    lxp402_enabled: bool = True
    lxp402_quote_ttl_seconds: int = 300
    policy_approval_ttl_seconds: int = Field(default=900, ge=60, le=86_400)
    lxp402_max_clock_skew_seconds: int = 30
    lxp402_require_request_hash: bool = True

    # Gateway proxy limits
    gateway_request_timeout_seconds: int = Field(default=30, ge=1, le=120)
    gateway_connect_timeout_seconds: int = Field(default=5, ge=1, le=30)
    gateway_max_request_bytes: int = Field(
        default=1_048_576, ge=1_024, le=10_485_760
    )
    gateway_max_response_bytes: int = Field(
        default=10_485_760, ge=1_024, le=104_857_600
    )

    # Provider routing
    router_default_strategy: str = "balanced"
    router_max_provider_attempts: int = 2

    # Receipt signing
    receipt_signing_backend: str = "local"
    receipt_signing_private_key: str = ""
    receipt_signing_key_id: str = "local-development"

    @model_validator(mode="after")
    def require_production_integrations(self) -> "GatewaySettings":
        """Require explicit staging endpoints and production integrations."""
        if self.app_env in {"staging", "production"}:
            if not self.provider_endpoint_hosts:
                raise ValueError(
                    "PROVIDER_ENDPOINT_HOST_ALLOWLIST is required in staging "
                    "and production"
                )
            if self.use_mock_adapter:
                raise ValueError(
                    "USE_MOCK_ADAPTER must be false in staging and production"
                )
        if (
            self.app_env == "staging"
            and self.paxeer_network_environment == "mainnet"
        ):
            raise ValueError(
                "PAXEER_NETWORK_ENVIRONMENT must not be mainnet in staging"
            )
        if self.app_env == "staging":
            if not _is_secure_url(self.layerx_api_url):
                raise ValueError("LAYERX_API_URL must be an HTTPS URL in staging")
            if not _is_secure_url(self.paxeer_rpc_url):
                raise ValueError("PAXEER_RPC_URL must be an HTTPS URL in staging")
            if self.paxeer_rpc_url.rstrip("/") == _MAINNET_PAXEER_RPC_URL:
                raise ValueError(
                    "PAXEER_RPC_URL must point to the staging network in staging"
                )
        if self.app_env == "production":
            if self.paxeer_network_environment != "mainnet":
                raise ValueError(
                    "PAXEER_NETWORK_ENVIRONMENT must be mainnet in production"
                )
            if self.gateway_rate_limit_enabled is False:
                raise ValueError("Gateway rate limiting cannot be disabled in production")
            if self.receipt_signing_backend != "local":
                raise ValueError(
                    "RECEIPT_SIGNING_BACKEND must be 'local'; other backends are not implemented"
                )
            if not _is_secure_url(self.layerx_api_url):
                raise ValueError("LAYERX_API_URL must be an HTTPS URL in production")
            if not _is_secure_url(self.paxeer_rpc_url):
                raise ValueError("PAXEER_RPC_URL must be an HTTPS URL in production")
            if self.paxeer_chain_id != 125:
                raise ValueError("PAXEER_CHAIN_ID must be 125 in production")
            if "-----BEGIN" not in self.receipt_signing_private_key:
                raise ValueError("RECEIPT_SIGNING_PRIVATE_KEY is required in production")
            if (
                not self.receipt_signing_key_id.strip()
                or self.receipt_signing_key_id == "local-development"
            ):
                raise ValueError("RECEIPT_SIGNING_KEY_ID must identify the production key")
        return self

    @property
    def rate_limiting_enabled(self) -> bool:
        """Default to shared gateway limits in staging and production."""
        if self.gateway_rate_limit_enabled is not None:
            return self.gateway_rate_limit_enabled
        return self.app_env in {"staging", "production"}

    @property
    def provider_endpoint_hosts(self) -> frozenset[str]:
        """Return the configured exact provider hostnames."""
        return frozenset(
            value.strip().rstrip(".").lower()
            for value in self.provider_endpoint_host_allowlist.split(",")
            if value.strip()
        )


def _is_secure_url(value: str) -> bool:
    """Return true only for absolute HTTPS URLs with a hostname and no userinfo."""
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and bool(parsed.hostname)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        return False


@lru_cache
def get_settings() -> GatewaySettings:
    """Return the process-wide cached gateway settings."""
    return GatewaySettings()
