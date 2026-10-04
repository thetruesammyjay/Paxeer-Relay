"""Tool-call transaction history route — browse ToolCall records.

Filters are applied in SQL (before pagination) so ``limit``/``offset`` page
over the filtered set, not the raw table.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from paxrelay_db.models.executions import ExecutionAttemptModel
from paxrelay_db.models.payments import ToolCallModel
from paxrelay_db.repositories._common import sid

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.exceptions import NotFoundError
from paxrelay_api.schemas import ExecutionAttemptOut, TransactionOut
from paxrelay_api.security.authorization import require_scope

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _transaction_out(m: ToolCallModel) -> TransactionOut:
    """Map a ToolCall ORM row to the wire TransactionOut schema."""
    return TransactionOut(
        id=m.id,
        agent_id=m.agent_id,
        capability=m.capability,
        request_state=m.request_state,
        payment_state=m.payment_state,
        execution_state=m.execution_state,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


@router.get(
    "",
    response_model=list[TransactionOut],
    dependencies=[Depends(require_scope("transactions:read"))],
)
async def list_transactions(
    session: SessionDep,
    tenant: TenantDep,
    agent_id: UUID | None = Query(None, description="Filter by agent ID"),
    request_state: str | None = Query(None, description="Filter by request state"),
    payment_state: str | None = Query(None, description="Filter by payment state"),
    created_after: datetime | None = Query(None, description="Created at/after (ISO 8601)"),
    created_before: datetime | None = Query(None, description="Created at/before (ISO 8601)"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[TransactionOut]:
    """List tool-call transactions for the current tenant with optional filters."""
    stmt = (
        select(ToolCallModel)
        .where(
            ToolCallModel.organisation_id == sid(tenant.organisation_id),
            ToolCallModel.project_id == sid(tenant.project_id),
            ToolCallModel.environment == tenant.environment,
        )
        .order_by(ToolCallModel.created_at.desc())
    )
    if agent_id is not None:
        stmt = stmt.where(ToolCallModel.agent_id == sid(agent_id))
    if request_state is not None:
        stmt = stmt.where(ToolCallModel.request_state == request_state)
    if payment_state is not None:
        stmt = stmt.where(ToolCallModel.payment_state == payment_state)
    if created_after is not None:
        stmt = stmt.where(ToolCallModel.created_at >= created_after)
    if created_before is not None:
        stmt = stmt.where(ToolCallModel.created_at <= created_before)

    stmt = stmt.limit(limit).offset(offset)
    rows = (await session.execute(stmt)).scalars().all()
    return [_transaction_out(m) for m in rows]


@router.get(
    "/{tool_call_id}/execution-attempts",
    response_model=list[ExecutionAttemptOut],
    dependencies=[Depends(require_scope("transactions:read"))],
)
async def list_execution_attempts(
    tool_call_id: UUID,
    session: SessionDep,
    tenant: TenantDep,
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[ExecutionAttemptOut]:
    """List safe attempt metadata for a transaction owned by this tenant."""
    transaction_id = await session.scalar(
        select(ToolCallModel.id).where(
            ToolCallModel.id == sid(tool_call_id),
            ToolCallModel.organisation_id == sid(tenant.organisation_id),
            ToolCallModel.project_id == sid(tenant.project_id),
            ToolCallModel.environment == tenant.environment,
        )
    )
    if transaction_id is None:
        # Keep missing and cross-tenant identifiers indistinguishable.
        raise NotFoundError("Transaction not found.")

    stmt = (
        select(ExecutionAttemptModel)
        .where(ExecutionAttemptModel.tool_call_id == sid(tool_call_id))
        .order_by(
            ExecutionAttemptModel.attempt_number.asc(),
            ExecutionAttemptModel.created_at.asc(),
            ExecutionAttemptModel.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    )
    attempts = (await session.execute(stmt)).scalars().all()
    return [
        ExecutionAttemptOut(
            id=attempt.id,
            tool_call_id=attempt.tool_call_id,
            provider_id=attempt.provider_id,
            service_version_id=attempt.service_version_id,
            attempt_number=attempt.attempt_number,
            execution_state=attempt.execution_state,
            request_forwarded_at=attempt.request_forwarded_at,
            response_received_at=attempt.response_received_at,
            latency_ms=attempt.latency_ms,
            http_status_code=attempt.http_status_code,
            provider_error_code=attempt.provider_error_code,
            created_at=attempt.created_at,
            updated_at=attempt.updated_at,
        )
        for attempt in attempts
    ]
