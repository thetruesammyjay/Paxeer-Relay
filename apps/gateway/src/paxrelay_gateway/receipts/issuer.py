"""Signed execution receipt issuance.

Builds the canonical :class:`ExecutionReceipt` for a completed tool call, then
hashes and signs it via the pluggable receipt signer. The receipt proves what
PaxRelay observed — payment, routing, and execution — not that the provider's
output was correct.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from paxrelay_domain import (
    ExecutionReceipt,
    ExecutionState,
    MonetaryAmount,
    ReceiptExecutionSummary,
    ReceiptPaymentSummary,
    ReceiptRoutingSummary,
)
from paxrelay_receipts import ReceiptSigner


def build_and_sign_receipt(
    *,
    tool_call_id: UUID,
    agent_id: UUID,
    provider_id: UUID,
    service_id: UUID,
    service_version: str,
    capability: str,
    request_hash: str,
    response_hash: str,
    amount: MonetaryAmount,
    payment_id: UUID,
    layerx_transaction_hash: str | None,
    payment_scheme: str = "402LXP",
    payment_network: str | None = None,
    payment_asset: str | None = None,
    payment_transaction: str | None = None,
    route_id: UUID,
    strategy: str,
    route_score: float,
    execution_started_at: datetime,
    execution_completed_at: datetime,
    latency_ms: int,
    execution_status: ExecutionState,
    signer: ReceiptSigner,
) -> ExecutionReceipt:
    """Assemble, hash, and sign an execution receipt."""
    unsigned = ExecutionReceipt(
        tool_call_id=tool_call_id,
        agent_id=agent_id,
        provider_id=provider_id,
        service_id=service_id,
        service_version=service_version,
        capability=capability,
        request_hash=request_hash,
        response_hash=response_hash,
        payment=ReceiptPaymentSummary(
            scheme=payment_scheme,
            amount=amount,
            payment_id=payment_id,
            network=payment_network,
            asset=payment_asset,
            transaction=payment_transaction,
            layerx_transaction=layerx_transaction_hash,
        ),
        execution=ReceiptExecutionSummary(
            started_at=execution_started_at,
            completed_at=execution_completed_at,
            latency_ms=latency_ms,
            status=execution_status,
        ),
        routing=ReceiptRoutingSummary(
            route_id=route_id,
            strategy=strategy,
            score=route_score,
        ),
    )

    receipt_hash, signature = signer.sign(unsigned.model_dump())
    return unsigned.model_copy(
        update={
            "receipt_hash": receipt_hash,
            "signature": signature,
            "signing_key_id": signer.key_id,
        }
    )
