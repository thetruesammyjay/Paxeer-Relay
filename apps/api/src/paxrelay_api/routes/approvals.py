"""Tenant-scoped human approval queue for policy-gated paid calls."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from paxrelay_api.audit import record_change
from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.exceptions import ConflictError, NotFoundError
from paxrelay_api.schemas import ApprovalDecisionIn, ApprovalOut
from paxrelay_api.security.authorization import require_scope
from paxrelay_db.models.executions import ApprovalRequestModel
from paxrelay_db.models.payments import ToolCallModel
from paxrelay_db.repositories._common import sid

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _approval_out(row: ApprovalRequestModel) -> ApprovalOut:
    return ApprovalOut(
        id=row.id,
        tool_call_id=row.tool_call_id,
        agent_id=row.agent_id,
        capability=row.capability,
        provider_id=row.provider_id,
        service_version_id=row.service_version_id,
        amount_atomic=int(row.amount_atomic),
        currency=row.currency,
        decimals=row.currency_decimals,
        recipient_address=row.recipient_address,
        request_hash=row.request_hash,
        policy_id=row.policy_id,
        policy_version=row.policy_version,
        status=row.status,
        reason=row.reason,
        decision_reason=row.decision_reason,
        expires_at=row.expires_at,
        decided_at=row.decided_at,
        created_at=row.created_at,
    )


@router.get(
    "",
    response_model=list[ApprovalOut],
    dependencies=[Depends(require_scope("approvals:read"))],
)
async def list_approvals(
    session: SessionDep,
    tenant: TenantDep,
    status: str | None = Query(
        None,
        pattern=r"^(pending|approved|rejected|expired|consumed|invalidated)$",
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[ApprovalOut]:
    stmt = select(ApprovalRequestModel).where(
        ApprovalRequestModel.organisation_id == sid(tenant.organisation_id),
        ApprovalRequestModel.project_id == sid(tenant.project_id),
        ApprovalRequestModel.environment == tenant.environment,
    )
    if status is not None:
        stmt = stmt.where(ApprovalRequestModel.status == status)
    rows = (
        await session.execute(
            stmt.order_by(
                ApprovalRequestModel.created_at.desc(), ApprovalRequestModel.id.desc()
            )
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return [_approval_out(row) for row in rows]


@router.get(
    "/{approval_id}",
    response_model=ApprovalOut,
    dependencies=[Depends(require_scope("approvals:read"))],
)
async def get_approval(
    approval_id: UUID,
    session: SessionDep,
    tenant: TenantDep,
) -> ApprovalOut:
    stmt = select(ApprovalRequestModel).where(
        ApprovalRequestModel.id == sid(approval_id),
        ApprovalRequestModel.organisation_id == sid(tenant.organisation_id),
        ApprovalRequestModel.project_id == sid(tenant.project_id),
        ApprovalRequestModel.environment == tenant.environment,
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Approval request not found.")
    return _approval_out(row)


@router.post(
    "/{approval_id}/decision",
    response_model=ApprovalOut,
    dependencies=[Depends(require_scope("approvals:write"))],
)
async def decide_approval(
    approval_id: UUID,
    body: ApprovalDecisionIn,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> ApprovalOut:
    stmt = (
        select(ApprovalRequestModel)
        .where(
            ApprovalRequestModel.id == sid(approval_id),
            ApprovalRequestModel.organisation_id == sid(tenant.organisation_id),
            ApprovalRequestModel.project_id == sid(tenant.project_id),
            ApprovalRequestModel.environment == tenant.environment,
        )
        .with_for_update()
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise NotFoundError("Approval request not found.")

    now = datetime.now(UTC).replace(tzinfo=None)
    if (
        row.status in {"pending", "approved"}
        and row.expires_at is not None
        and row.expires_at <= now
    ):
        row.status = "expired"
        row.decided_at = now
        call = await session.get(ToolCallModel, row.tool_call_id)
        if call is not None and call.request_state == "approval_pending":
            call.request_state = "expired"
        await session.flush()
        await record_change(
            request=request,
            session=session,
            tenant=tenant,
            event_type="approval.expired",
            resource_type="approval_request",
            resource_id=row.id,
            details={"tool_call_id": row.tool_call_id},
        )
        return _approval_out(row)

    if row.status in {"approved", "rejected"}:
        if row.status == body.decision:
            return _approval_out(row)
        raise ConflictError("This approval request already has a different decision.")
    if row.status != "pending":
        raise ConflictError("This approval request is no longer actionable.")

    row.status = body.decision
    row.decided_by = sid(tenant.user_id or tenant.api_key_id) if (tenant.user_id or tenant.api_key_id) else None
    row.decided_at = now
    row.decision_reason = body.reason
    if body.decision == "rejected":
        call = await session.get(ToolCallModel, row.tool_call_id)
        if call is not None and call.request_state == "approval_pending":
            call.request_state = "failed"
    await session.flush()
    await record_change(
        request=request,
        session=session,
        tenant=tenant,
        event_type=f"approval.{body.decision}",
        resource_type="approval_request",
        resource_id=row.id,
        details={"tool_call_id": row.tool_call_id},
    )
    return _approval_out(row)
