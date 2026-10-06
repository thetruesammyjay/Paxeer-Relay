"""Provider, Service, and ServiceVersion domain models."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from paxrelay_domain.types import (
    CapabilitySlug,
    Currency,
    Environment,
    MonetaryAmount,
    WalletAddress,
)


class ProviderStatus(str, Enum):
    """Lifecycle state of a registered provider."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class PricingModel(str, Enum):
    """Supported pricing models for a service."""

    PER_CALL = "per_call"
    METERED = "metered"
    STREAMING = "streaming"


class ServiceProtocol(str, Enum):
    """Supported invocation protocols."""

    HTTP = "http"
    MCP = "mcp"
    GRPC = "grpc"


class ServiceStatus(str, Enum):
    """Operational state of a published service."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


class ServicePricing(BaseModel):
    """Pricing configuration for a service."""

    model_config = {"frozen": True}

    model: PricingModel = PricingModel.PER_CALL
    price_per_call: MonetaryAmount | None = None
    price_per_unit: MonetaryAmount | None = None
    unit: str | None = Field(
        default=None,
        description="Metering unit (e.g. 'token', 'byte', 'second').",
    )
    currency: Currency = Currency.USDX


class ServiceDelivery(BaseModel):
    """Delivery and reliability settings for a service."""

    model_config = {"frozen": True}

    timeout_seconds: int = Field(default=30, ge=1, le=300)
    maximum_request_bytes: int = Field(default=32_768)
    maximum_response_bytes: int = Field(default=10_485_760)
    idempotent: bool = True
    concurrency_limit: int | None = None


class ServiceHealth(BaseModel):
    """Configured health checks and the latest persisted worker observation."""

    model_config = {"frozen": True}

    endpoint: str = "/health"
    interval_seconds: int = Field(default=30, ge=5)
    timeout_seconds: int = Field(default=5, ge=1)
    failure_threshold: int = Field(default=3, ge=1)
    last_check_at: datetime | None = None
    last_check_passing: bool | None = None
    consecutive_health_failures: int = Field(default=0, ge=0)
    last_check_status_code: int | None = Field(default=None, ge=100, le=599)
    last_check_error: str | None = Field(default=None, max_length=128)

    @field_validator("last_check_at")
    @classmethod
    def normalise_last_check_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Provider(BaseModel):
    """An organisation or wallet that sells machine services via PaxRelay."""

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
    )
    organisation_id: UUID
    project_id: UUID
    environment: Environment = Environment.DEVELOPMENT
    wallet_address: WalletAddress | None = None
    layerx_account_id: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
        description="LayerX 32-byte account identifier in lowercase hexadecimal.",
    )
    status: ProviderStatus = ProviderStatus.ACTIVE
    description: str | None = None
    website_url: str | None = None
    is_verified: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("layerx_account_id")
    @classmethod
    def normalise_layerx_account_id(cls, value: str | None) -> str | None:
        return value.lower() if value is not None else None

    def is_operable(self) -> bool:
        return self.status == ProviderStatus.ACTIVE


class Service(BaseModel):
    """A callable capability published by a provider."""

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    provider_id: UUID
    organisation_id: UUID
    project_id: UUID
    environment: Environment = Environment.DEVELOPMENT
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    capability: CapabilitySlug
    protocols: list[ServiceProtocol] = Field(default_factory=lambda: [ServiceProtocol.HTTP])
    pricing: ServicePricing
    delivery: ServiceDelivery = Field(default_factory=ServiceDelivery)
    health: ServiceHealth = Field(default_factory=ServiceHealth)
    status: ServiceStatus = ServiceStatus.ACTIVE
    base_url: str | None = None
    description: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ServiceVersion(BaseModel):
    """An immutable version snapshot of a service definition.

    Once created, a service version must not be mutated. Any change
    to a service requires publishing a new version.
    """

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    service_id: UUID
    provider_id: UUID
    version: str = Field(
        min_length=1,
        max_length=32,
        description="SemVer string, e.g. '1.0.0'.",
    )
    capability: CapabilitySlug
    pricing: ServicePricing
    delivery: ServiceDelivery
    endpoint_url: str
    protocol: ServiceProtocol = ServiceProtocol.HTTP
    mcp_tool_name: str | None = Field(default=None, min_length=1, max_length=128)
    mcp_input_schema: dict[str, Any] | None = None
    openapi_schema: dict[str, Any] | None = None
    is_active: bool = True
    published_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def validate_protocol_contract(self) -> "ServiceVersion":
        if self.protocol == ServiceProtocol.GRPC:
            raise ValueError("gRPC service versions are not supported.")
        if self.protocol == ServiceProtocol.MCP:
            if not self.mcp_tool_name or self.mcp_input_schema is None:
                raise ValueError("MCP service versions require a tool name and input schema.")
            if self.mcp_input_schema.get("type") != "object":
                raise ValueError("MCP input schema must have type 'object'.")
        elif self.mcp_tool_name is not None or self.mcp_input_schema is not None:
            raise ValueError("MCP metadata is only valid for MCP service versions.")
        return self


class ProviderMetrics(BaseModel):
    """Aggregated performance and reputation metrics for a service.

    These values drive the provider routing scoring algorithm.
    All scores are normalised to the range [0.0, 1.0].
    """

    model_config = {"frozen": True}

    service_id: UUID
    provider_id: UUID

    # Reputation — based on community ratings and historical reliability
    reputation_score: float = Field(default=0.5, ge=0.0, le=1.0)

    # Delivery success rate over rolling window
    success_rate: float = Field(default=0.5, ge=0.0, le=1.0)

    # P50 response latency in milliseconds
    avg_latency_ms: float = Field(default=0.0, ge=0.0)

    # Fraction of time the service responds to health checks
    availability_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Total completed calls in the measurement window
    total_calls: int = Field(default=0, ge=0)

    # Rolling window failure count
    consecutive_failures: int = Field(default=0, ge=0)

    # Whether the health check is currently passing
    health_check_passing: bool = False

    measured_at: datetime = Field(default_factory=datetime.utcnow)
