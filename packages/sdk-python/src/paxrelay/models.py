"""Typed response models for the PaxRelay control-plane API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class APIModel(BaseModel):
    """Base response model that tolerates fields added by newer API versions."""

    model_config = ConfigDict(extra="ignore")


class Agent(APIModel):
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


class AgentWallet(APIModel):
    id: UUID
    agent_id: UUID
    address: str
    is_primary: bool
    label: str | None


class Provider(APIModel):
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


class Money(APIModel):
    amount_atomic: int
    currency: str
    decimals: int


class ServiceHealth(APIModel):
    endpoint: str = Field(default="/health", min_length=1, max_length=512)
    interval_seconds: int = Field(default=30, ge=5, le=3600)
    timeout_seconds: int = Field(default=5, ge=1, le=30)
    failure_threshold: int = Field(default=3, ge=1, le=20)

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            not value.startswith("/")
            or value.startswith("//")
            or "\\" in value
            or parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)
            or any(segment in {".", ".."} for segment in parsed.path.split("/"))
        ):
            raise ValueError("health endpoint must be a safe absolute path")
        return value


class Service(APIModel):
    id: UUID
    provider_id: UUID
    name: str
    slug: str
    capability: str
    protocols: list[str]
    status: str
    base_url: str | None
    price_per_call: Money | None
    health: ServiceHealth = Field(default_factory=ServiceHealth)
    description: str | None


class Policy(APIModel):
    """Policy metadata returned by the current API routes."""

    id: UUID
    name: str
    description: str | None
    mode: str
    version: int
    is_active: bool


class PolicyAssignment(APIModel):
    """A policy-to-agent assignment record."""

    id: UUID
    agent_id: UUID
    policy_id: UUID
    assigned_at: datetime


class ApprovalRequest(APIModel):
    """A human-review request created by a policy-gated tool call."""

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


class Transaction(APIModel):
    """A tenant-scoped tool-call transaction summary."""

    id: UUID
    agent_id: UUID
    capability: str
    request_state: str
    payment_state: str
    execution_state: str
    created_at: datetime
    updated_at: datetime


class ReceiptSummary(APIModel):
    """A tenant-scoped summary of a signed execution receipt."""

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


class AnalyticsSpend(APIModel):
    """Committed-spend total returned for a requested date window."""

    period: str
    start_date: datetime
    end_date: datetime
    total_amount_atomic: int
    currency: str
    decimals: int
    transaction_count: int


class AnalyticsCapability(APIModel):
    """Committed-spend aggregate for one service capability."""

    capability: str
    total_amount_atomic: int
    currency: str
    decimals: int
    call_count: int


class PaymentRequirement(APIModel):
    """The immutable payment quote returned by the gateway."""

    version: str
    payment_scheme: Literal["402LXP"]
    network: str
    chain_id: int
    settlement_layer: str
    currency: str
    currency_decimals: int = 6
    amount_atomic: str
    recipient: str
    quote_id: UUID
    request_hash: str
    expires_at: datetime
    nonce: str


class PaymentChallenge(APIModel):
    """A gateway response that requires payment proof before execution."""

    tool_call_id: UUID
    payment_requirement: PaymentRequirement


class GatewayCallResult(APIModel):
    """Provider output and signed receipt returned after successful execution."""

    result: Any
    receipt: dict[str, Any]
    replayed: bool = False


class ApprovalPending(APIModel):
    """A gateway response waiting for a human policy approval."""

    decision: str
    explanation: str
    approval_id: UUID
    status: str
    expires_at: datetime
