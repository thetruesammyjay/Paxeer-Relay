"""Execution receipt domain models.

A receipt proves what PaxRelay observed during a paid service call.
It is NOT proof that the provider's output was factually correct.

The receipt structure matches the JSON specification in the README exactly.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from paxrelay_domain.types import CapabilitySlug, MonetaryAmount
from paxrelay_domain.payments.models import ExecutionState


class ReceiptPaymentSummary(BaseModel):
    """Payment sub-object within a receipt."""

    model_config = {"frozen": True}

    scheme: str = "402LXP"
    currency: str = "USDX"
    amount: MonetaryAmount
    payment_id: UUID
    layerx_transaction: str | None = None
    l1_settlement: str | None = None


class ReceiptExecutionSummary(BaseModel):
    """Execution timing and status sub-object within a receipt."""

    model_config = {"frozen": True}

    started_at: datetime
    completed_at: datetime
    latency_ms: int = Field(ge=0)
    status: ExecutionState


class ReceiptRoutingSummary(BaseModel):
    """Routing decision sub-object within a receipt."""

    model_config = {"frozen": True}

    route_id: UUID
    strategy: str
    score: float = Field(ge=0.0, le=1.0)


class ExecutionReceipt(BaseModel):
    """A signed record of payment, execution and delivery for one tool call.

    This is the canonical receipt format. Before signing, the receipt must be
    canonicalized:
      1. Remove the ``signature`` field.
      2. Sort object keys deterministically.
      3. Encode numbers and timestamps consistently.
      4. Serialise using canonical JSON.
      5. Hash with SHA-256.
      6. Sign using the PaxRelay receipt signer.

    Matches the JSON example in the README exactly.
    """

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    version: str = "1"
    tool_call_id: UUID
    agent_id: UUID
    provider_id: UUID
    service_id: UUID
    service_version: str
    capability: CapabilitySlug
    request_hash: str = Field(description="SHA-256 of the canonical request body.")
    response_hash: str = Field(description="SHA-256 of the canonical response body.")
    payment: ReceiptPaymentSummary
    execution: ReceiptExecutionSummary
    routing: ReceiptRoutingSummary
    issued_at: datetime = Field(default_factory=datetime.utcnow)

    # Set after signing — absent during canonicalization
    receipt_hash: str | None = Field(
        default=None,
        description="SHA-256 of the canonical receipt JSON (without signature).",
    )
    signature: str | None = Field(
        default=None,
        description="ECDSA signature of receipt_hash using the PaxRelay signer.",
    )
    signing_key_id: str | None = None

    def is_signed(self) -> bool:
        return self.signature is not None and self.receipt_hash is not None
