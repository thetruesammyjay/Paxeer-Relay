"""Pydantic request/response schemas for the control-plane API.

These are the wire contracts for the dashboard and SDKs. They deliberately
mirror the domain models but stay separate so the HTTP surface can evolve
independently of the internal domain layer.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, field_validator

from paxrelay_api.security.scopes import parse_scopes


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class MoneyIn(BaseModel):
    """A human-friendly monetary amount accepted on input."""

    amount_atomic: int = Field(ge=0)
    currency: Literal["USDX"] = "USDX"
    decimals: Literal[6] = 6


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    # EVM checksummed or lowercase 20-byte hex address, or omitted.
    wallet_address: str | None = Field(
        default=None, max_length=42, pattern=r"^0x[0-9a-fA-F]{40}$"
    )
    description: str | None = None


class AgentOut(BaseModel):
    id: UUID
    name: str
    slug: str
    organisation_id: UUID
    project_id: UUID
    environment: str
    wallet_address: str | None
    status: str
    description: str | None
    created_at: datetime


class WalletOut(BaseModel):
    id: UUID
    agent_id: UUID
    address: str
    is_primary: bool
    label: str | None


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    # EVM checksummed or lowercase 20-byte hex address, or omitted.
    wallet_address: str | None = Field(
        default=None, max_length=42, pattern=r"^0x[0-9a-fA-F]{40}$"
    )
    description: str | None = None
    website_url: str | None = None


class ProviderOut(BaseModel):
    id: UUID
    name: str
    slug: str
    organisation_id: UUID
    project_id: UUID
    environment: str
    wallet_address: str | None
    status: str
    is_verified: bool
    description: str | None


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    capability: str = Field(pattern=r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)*(\.\*)?$")
    protocols: list[Literal["http", "mcp", "grpc"]] = Field(
        default_factory=lambda: ["http"], min_length=1, max_length=3
    )
    price_per_call: MoneyIn
    base_url: str = Field(min_length=8, max_length=2048, pattern=r"^https?://")
    endpoint_url: str = Field(min_length=8, max_length=2048, pattern=r"^https?://")
    version: str = Field(default="1.0.0", min_length=1, max_length=32)
    description: str | None = None


class ServiceOut(BaseModel):
    id: UUID
    provider_id: UUID
    name: str
    slug: str
    capability: str
    protocols: list[str]
    status: str
    base_url: str | None
    price_per_call: MoneyIn | None
    description: str | None


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    mode: Literal["observe", "warn", "enforce"] = "enforce"
    maximum_per_call: MoneyIn | None = None
    daily_budget: MoneyIn | None = None
    monthly_budget: MoneyIn | None = None
    allowed_capabilities: list[str] = Field(default_factory=list, max_length=100)
    allowed_providers: list[str] = Field(default_factory=list, max_length=100)
    blocked_providers: list[str] = Field(default_factory=list, max_length=100)
    approval_threshold: MoneyIn | None = None


class PolicyOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    mode: str
    version: int
    is_active: bool


class PolicyAssignIn(BaseModel):
    agent_id: UUID


class PolicyAssignmentOut(BaseModel):
    id: UUID
    agent_id: UUID
    policy_id: UUID
    assigned_at: datetime


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    key_type: str = Field(default="test", pattern=r"^(test|live)$")
    # Colon-paired grants, e.g. "agents:read:agents:write".
    scopes: str = Field(
        min_length=1,
        max_length=512,
        pattern=r"^(?:[a-z][a-z0-9-]*:(?:read|write)|gateway:invoke)(?::(?:[a-z][a-z0-9-]*:(?:read|write)|gateway:invoke))*$",
    )
    expires_in_days: int = Field(default=90, ge=1, le=365)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: str) -> str:
        parse_scopes(value)
        return value


class ApiKeyOut(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    key_type: str
    scopes: str = ""
    expires_at: datetime | None = None
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    is_active: bool = True
    # The raw key is returned exactly once, at creation time.
    raw_key: str | None = None


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------


class ReceiptOut(BaseModel):
    id: UUID
    tool_call_id: UUID
    agent_id: UUID
    provider_id: UUID
    service_id: UUID
    service_version: str
    capability: str
    request_hash: str
    response_hash: str
    payment_amount: int
    payment_currency: str
    layerx_transaction: str | None
    execution_latency_ms: int
    execution_status: str
    receipt_hash: str | None
    signature: str | None
    signing_key_id: str | None
    issued_at: datetime


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


class TransactionOut(BaseModel):
    id: UUID
    agent_id: UUID
    capability: str
    request_state: str
    payment_state: str
    execution_state: str
    created_at: datetime
    updated_at: datetime


class ApprovalDecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=512)


class ApprovalOut(BaseModel):
    id: UUID
    tool_call_id: UUID
    agent_id: UUID
    capability: str
    provider_id: UUID | None
    service_version_id: UUID | None
    amount_atomic: int
    currency: str
    decimals: int
    recipient_address: str | None
    request_hash: str | None
    policy_id: UUID | None
    policy_version: int | None
    status: str
    reason: str | None
    decision_reason: str | None
    expires_at: datetime | None
    decided_at: datetime | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class AnalyticsSpendOut(BaseModel):
    period: str
    start_date: datetime
    end_date: datetime
    total_amount_atomic: int
    currency: str
    decimals: int
    transaction_count: int


class AnalyticsCapabilityOut(BaseModel):
    capability: str
    total_amount_atomic: int
    currency: str
    decimals: int
    call_count: int


class AuditLogOut(BaseModel):
    id: UUID
    event_type: str
    actor_id: str
    resource_type: str
    resource_id: str
    details: dict[str, object] | None
    ip_address: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


class WebhookCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2048, pattern=r"^https?://")
    event_types: list[str] = Field(min_length=1, max_length=100)
    secret: SecretStr = Field(min_length=32, max_length=128)
    description: str | None = Field(default=None, max_length=256)


class WebhookUpdate(BaseModel):
    url: str | None = Field(None, min_length=1, max_length=2048, pattern=r"^https?://")
    event_types: list[str] | None = Field(None, min_length=1)
    secret: SecretStr | None = Field(None, min_length=32, max_length=128)
    is_active: bool | None = None
    description: str | None = Field(default=None, max_length=256)


class WebhookOut(BaseModel):
    id: UUID
    url: str
    event_types: list[str]
    secret_configured: bool
    is_active: bool
    description: str | None
    created_at: datetime


class WebhookDeliveryOut(BaseModel):
    id: UUID
    event_type: str
    status: str
    attempt_count: int
    http_status_code: int | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    next_attempt_at: datetime | None
    delivered_at: datetime | None


class WebhookDeliveryPageOut(BaseModel):
    items: list[WebhookDeliveryOut]
    next_cursor_created_at: datetime | None = None
    next_cursor_id: UUID | None = None


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------


class BatchAgentCreate(BaseModel):
    agents: list[AgentCreate] = Field(min_length=1, max_length=100)


class BatchAgentResult(BaseModel):
    success: bool
    agent: AgentOut | None = None
    error: str | None = None


class BatchAgentResponse(BaseModel):
    results: list[BatchAgentResult]
    success_count: int
    failure_count: int


class BatchProviderCreate(BaseModel):
    providers: list[ProviderCreate] = Field(min_length=1, max_length=100)


class BatchProviderResult(BaseModel):
    success: bool
    provider: ProviderOut | None = None
    error: str | None = None


class BatchProviderResponse(BaseModel):
    results: list[BatchProviderResult]
    success_count: int
    failure_count: int
