"""Payment flow domain models.

Covers the full 402LXP payment lifecycle:
Quote → PaymentIntent → Payment → Settlement

Each state machine is represented as an enum, and all monetary
values use MonetaryAmount (atomic integers) — never floats.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from paxrelay_domain.types import CapabilitySlug, Currency, MonetaryAmount


# ---------------------------------------------------------------------------
# State machine enumerations
# ---------------------------------------------------------------------------


class RequestState(str, Enum):
    """Lifecycle state of a ToolCall (the top-level request record)."""

    CREATED = "created"
    POLICY_PENDING = "policy_pending"
    APPROVAL_PENDING = "approval_pending"
    PAYMENT_REQUIRED = "payment_required"
    PAYMENT_SUBMITTED = "payment_submitted"
    PAYMENT_VERIFIED = "payment_verified"
    EXECUTION_RESERVED = "execution_reserved"
    EXECUTING = "executing"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class PaymentState(str, Enum):
    """Lifecycle state of a payment associated with a tool call."""

    UNPAID = "unpaid"
    QUOTED = "quoted"
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    SETTLED_LAYERX = "settled_layerx"
    ANCHORED_L1 = "anchored_l1"
    REFUNDED = "refunded"
    DISPUTED = "disputed"
    FAILED = "failed"
    EXPIRED = "expired"


class ExecutionState(str, Enum):
    """Lifecycle state of a single execution attempt at a provider."""

    NOT_STARTED = "not_started"
    RESERVED = "reserved"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PROVIDER_ERROR = "provider_error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Quote
# ---------------------------------------------------------------------------


class Quote(BaseModel):
    """A time-limited, bound payment requirement.

    A quote is immutable after creation — it cannot be modified or extended.
    Per the protocol spec, a quote must be:
      - Bound to exactly one request hash
      - Bound to exactly one provider and service version
      - Bound to exactly one currency and amount
      - Protected against replay via a unique nonce
    """

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    tool_call_id: UUID
    provider_id: UUID
    service_version_id: UUID
    amount: MonetaryAmount
    payment_scheme: str = Field(default="402LXP")
    chain_id: int = Field(default=125)
    settlement_layer: str = Field(default="layerx")
    recipient_address: str
    request_hash: str = Field(description="Keccak256 hash of the canonical request body.")
    nonce: str = Field(description="Unique per-quote nonce for replay protection.")
    quote_signature: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime

    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or datetime.utcnow()) >= self.expires_at

    def is_valid(self, now: datetime | None = None) -> bool:
        return not self.is_expired(now)


# ---------------------------------------------------------------------------
# Payment intent and payment
# ---------------------------------------------------------------------------


class PaymentIntent(BaseModel):
    """A request to authorise a specific payment against a quote."""

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    tool_call_id: UUID
    quote_id: UUID
    agent_id: UUID
    provider_id: UUID
    amount: MonetaryAmount
    state: PaymentState = PaymentState.UNPAID
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Payment(BaseModel):
    """The verified on-chain transfer associated with a payment intent.

    Tracks both the LayerX transaction (fast finality) and the eventual
    Paxeer L1 settlement record (final anchoring).
    """

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    intent_id: UUID
    tool_call_id: UUID
    quote_id: UUID
    agent_id: UUID
    provider_id: UUID
    amount: MonetaryAmount
    state: PaymentState = PaymentState.SUBMITTED
    proof: str | None = Field(default=None, description="Raw payment proof submitted by the agent.")
    layerx_transaction_hash: str | None = None
    layerx_batch_id: str | None = None
    l1_settlement_id: str | None = None
    verified_at: datetime | None = None
    settled_at: datetime | None = None
    anchored_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Tool call — the top-level request record
# ---------------------------------------------------------------------------


class ToolCall(BaseModel):
    """A logical MCP or HTTP service invocation.

    This is the central record that ties together the agent, the policy
    decision, the payment, the execution, and the receipt.

    A single tool call may have multiple execution attempts when failover
    is enabled, but must have at most one active payment per invocation.
    """

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    organisation_id: UUID
    project_id: UUID
    capability: CapabilitySlug
    idempotency_key: str = Field(
        min_length=1,
        max_length=255,
        description=(
            "Client-provided key that prevents duplicate executions. "
            "Repeating a request with the same key must return the "
            "previously completed result."
        ),
    )
    request_state: RequestState = RequestState.CREATED
    payment_state: PaymentState = PaymentState.UNPAID
    execution_state: ExecutionState = ExecutionState.NOT_STARTED
    request_hash: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Execution attempt
# ---------------------------------------------------------------------------


class ExecutionAttempt(BaseModel):
    """One request forwarded to one provider on behalf of a tool call.

    A tool call may have multiple attempts when failover is active.
    Each attempt tracks its own execution state independently.
    """

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    tool_call_id: UUID
    payment_id: UUID | None = None
    provider_id: UUID
    service_version_id: UUID
    attempt_number: int = Field(ge=1)
    execution_state: ExecutionState = ExecutionState.NOT_STARTED
    request_forwarded_at: datetime | None = None
    response_received_at: datetime | None = None
    latency_ms: int | None = None
    http_status_code: int | None = None
    provider_error_code: str | None = None
    is_retryable: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
