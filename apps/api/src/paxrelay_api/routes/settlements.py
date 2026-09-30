"""Tenant-scoped settlement reconciliation review endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, or_, select

from paxrelay_db.models.executions import SettlementRecordModel
from paxrelay_db.models.payments import PaymentModel, ToolCallModel
from paxrelay_db.repositories._common import sid

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.exceptions import InvalidRequestError
from paxrelay_api.schemas import (
    SettlementReconciliationOut,
    SettlementReconciliationPageOut,
)
from paxrelay_api.security.authorization import require_scope

router = APIRouter(prefix="/settlements", tags=["settlements"])


def _review_out(
    record: SettlementRecordModel,
    payment: PaymentModel,
) -> SettlementReconciliationOut:
    return SettlementReconciliationOut(
        id=record.id,
        payment_id=payment.id,
        payment_state=payment.state,
        reconciliation_status=record.reconciliation_status,
        layerx_transaction_hash=record.layerx_transaction_hash,
        layerx_batch_id=record.layerx_batch_id,
        l1_settlement_id=record.l1_settlement_id,
        l1_block_number=record.l1_block_number,
        l1_transaction_hash=record.l1_transaction_hash,
        l1_commitment_hash=record.l1_commitment_hash,
        internal_checked_at=record.internal_checked_at,
        last_checked_at=record.last_checked_at,
        attempt_count=record.attempt_count,
        next_attempt_at=record.next_attempt_at,
        last_error=record.last_error,
        reconciled_at=record.reconciled_at,
        mismatch_details=record.mismatch_details,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get(
    "/reconciliation",
    response_model=SettlementReconciliationPageOut,
    dependencies=[Depends(require_scope("settlements:read"))],
)
async def list_reconciliation_records(
    session: SessionDep,
    tenant: TenantDep,
    status_filter: str = Query(
        "mismatch",
        alias="status",
        pattern=r"^(awaiting_external|layerx_confirmed|mismatch|reconciled|anchored)$",
    ),
    limit: int = Query(50, ge=1, le=100),
    before_created_at: datetime | None = Query(None),
    before_id: UUID | None = Query(None),
) -> SettlementReconciliationPageOut:
    """List review records for the authenticated organisation and project."""
    if (before_created_at is None) != (before_id is None):
        raise InvalidRequestError(
            "Both before_created_at and before_id are required for pagination."
        )

    statement = (
        select(SettlementRecordModel, PaymentModel)
        .join(PaymentModel, PaymentModel.id == SettlementRecordModel.payment_id)
        .join(ToolCallModel, ToolCallModel.id == PaymentModel.tool_call_id)
        .where(
            ToolCallModel.organisation_id == sid(tenant.organisation_id),
            ToolCallModel.project_id == sid(tenant.project_id),
            ToolCallModel.environment == tenant.environment,
            SettlementRecordModel.reconciliation_status == status_filter,
        )
    )
    if before_created_at is not None and before_id is not None:
        cursor_time = before_created_at
        if cursor_time.tzinfo is not None:
            cursor_time = cursor_time.astimezone(UTC).replace(tzinfo=None)
        statement = statement.where(
            or_(
                SettlementRecordModel.created_at < cursor_time,
                and_(
                    SettlementRecordModel.created_at == cursor_time,
                    SettlementRecordModel.id < sid(before_id),
                ),
            )
        )

    rows = (
        await session.execute(
            statement.order_by(
                SettlementRecordModel.created_at.desc(),
                SettlementRecordModel.id.desc(),
            ).limit(limit + 1)
        )
    ).all()
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    last_record = page_rows[-1][0] if has_more and page_rows else None
    return SettlementReconciliationPageOut(
        items=[_review_out(record, payment) for record, payment in page_rows],
        next_cursor_created_at=(
            last_record.created_at if last_record is not None else None
        ),
        next_cursor_id=last_record.id if last_record is not None else None,
    )
