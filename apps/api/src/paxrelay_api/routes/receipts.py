"""Receipts listing route — browse signed execution receipts.

Tenant scoping note: ``ExecutionReceiptModel`` has no organisation/project
columns, so tenant isolation is enforced by joining through ``ToolCallModel``
(which carries the tenant columns via ``TenantMixin``) on ``tool_call_id``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from paxrelay_domain import ExecutionReceipt
from paxrelay_db.models.executions import ExecutionReceiptModel
from paxrelay_db.models.payments import ToolCallModel
from paxrelay_db.repositories._common import sid

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.schemas import ReceiptOut

router = APIRouter(prefix="/receipts", tags=["receipts"])


def _receipt_out(receipt: ExecutionReceipt) -> ReceiptOut:
    """Map domain ExecutionReceipt to wire ReceiptOut schema."""
    return ReceiptOut(
        id=receipt.id,
        tool_call_id=receipt.tool_call_id,
        agent_id=receipt.agent_id,
        provider_id=receipt.provider_id,
        service_id=receipt.service_id,
        service_version=receipt.service_version,
        capability=receipt.capability,
        request_hash=receipt.request_hash,
        response_hash=receipt.response_hash,
        payment_amount=receipt.payment.amount.amount_atomic,
        payment_currency=receipt.payment.amount.currency.value,
        layerx_transaction=receipt.payment.layerx_transaction,
        execution_latency_ms=receipt.execution.latency_ms,
        execution_status=receipt.execution.status.value,
        receipt_hash=receipt.receipt_hash,
        signature=receipt.signature,
        signing_key_id=receipt.signing_key_id,
        issued_at=receipt.issued_at,
    )


@router.get("", response_model=list[ReceiptOut])
async def list_receipts(
    session: SessionDep,
    tenant: TenantDep,
    agent_id: UUID | None = Query(None, description="Filter by agent ID"),
    tool_call_id: UUID | None = Query(None, description="Filter by tool call ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[ReceiptOut]:
    """List execution receipts for the current tenant with optional filters.

    Results are constrained to the caller's organisation/project by the join
    with ``tool_calls``; a receipt whose tool call belongs to another tenant is
    never returned.
    """
    stmt = (
        select(ExecutionReceiptModel)
        .join(ToolCallModel, ToolCallModel.id == ExecutionReceiptModel.tool_call_id)
        .where(
            ToolCallModel.organisation_id == sid(tenant.organisation_id),
            ToolCallModel.project_id == sid(tenant.project_id),
        )
        .order_by(ExecutionReceiptModel.issued_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if agent_id is not None:
        stmt = stmt.where(ExecutionReceiptModel.agent_id == sid(agent_id))
    if tool_call_id is not None:
        stmt = stmt.where(ExecutionReceiptModel.tool_call_id == sid(tool_call_id))

    rows = (await session.execute(stmt)).scalars().all()
    return [_receipt_out(ExecutionReceipt.model_validate(m.receipt_json)) for m in rows]
