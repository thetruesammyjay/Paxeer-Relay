"""Tenant-scoped audit log lookup routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.schemas import AuditLogOut
from paxrelay_api.security.authorization import require_scope
from paxrelay_db.models.executions import AuditLogModel
from paxrelay_db.repositories._common import sid

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get(
    "",
    response_model=list[AuditLogOut],
    dependencies=[Depends(require_scope("audit-logs:read"))],
)
async def list_audit_logs(
    session: SessionDep,
    tenant: TenantDep,
    event_type: str | None = Query(None, max_length=64),
    resource_type: str | None = Query(None, max_length=64),
    resource_id: str | None = Query(None, max_length=128),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[AuditLogOut]:
    """List recent audit entries for the authenticated tenant."""
    stmt = select(AuditLogModel).where(
        AuditLogModel.organisation_id == sid(tenant.organisation_id),
        AuditLogModel.project_id == sid(tenant.project_id),
        AuditLogModel.environment == tenant.environment,
    )
    if event_type is not None:
        stmt = stmt.where(AuditLogModel.event_type == event_type)
    if resource_type is not None:
        stmt = stmt.where(AuditLogModel.resource_type == resource_type)
    if resource_id is not None:
        stmt = stmt.where(AuditLogModel.resource_id == resource_id)

    rows = (
        await session.execute(
            stmt.order_by(AuditLogModel.created_at.desc(), AuditLogModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return [
        AuditLogOut(
            id=row.id,
            event_type=row.event_type,
            actor_id=row.actor_id,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            details=row.details,
            ip_address=row.ip_address,
            created_at=row.created_at,
        )
        for row in rows
    ]
