"""Helpers for recording tenant-scoped control-plane changes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_api.tenant import TenantContext
from paxrelay_db.models.executions import OutboxEventModel
from paxrelay_db.repositories import SqlAlchemyAuditRepository
from paxrelay_domain import EventType


async def record_change(
    *,
    request: Request,
    session: AsyncSession,
    tenant: TenantContext,
    event_type: str,
    resource_type: str,
    resource_id: UUID | str,
    details: dict[str, Any] | None = None,
) -> None:
    """Append a successful authenticated change in the same transaction.

    Callers must keep details free of credentials, request bodies, and secrets.
    The address is taken from the ASGI peer rather than an untrusted forwarded
    header and omitted if it cannot fit the database column.
    """
    peer = request.client.host if request.client is not None else None
    ip_address = peer if peer is not None and len(peer) <= 45 else None
    actor_id = (
        f"user:{tenant.user_id}"
        if tenant.user_id
        else f"api_key:{tenant.api_key_id}"
        if tenant.api_key_id
        else "system:unknown"
    )
    safe_details = dict(details or {})
    request_id = getattr(request.state, "request_id", None)
    if request_id is not None:
        safe_details["request_id"] = request_id

    await SqlAlchemyAuditRepository(session).record(
        event_type=event_type,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=str(resource_id),
        organisation_id=tenant.organisation_id,
        project_id=tenant.project_id,
        environment=tenant.environment,
        details=safe_details,
        ip_address=ip_address,
    )

    # Keep the event in the same transaction as the audited change. Webhook
    # subscriptions accept only domain EventType values; audit-only changes
    # outside that public event contract remain in the audit log only.
    try:
        public_event_type = EventType(event_type).value
    except (TypeError, ValueError):
        return

    event_id = str(uuid4())
    occurred_at = datetime.now(UTC).replace(tzinfo=None)
    event_data = {
        **safe_details,
        "resource_type": resource_type,
        "resource_id": str(resource_id),
    }
    session.add(
        OutboxEventModel(
            id=event_id,
            organisation_id=str(tenant.organisation_id),
            project_id=str(tenant.project_id),
            environment=tenant.environment,
            event_type=public_event_type,
            payload_json={
                "event_id": event_id,
                "event_type": public_event_type,
                "occurred_at": f"{occurred_at.isoformat()}Z",
                "organisation_id": str(tenant.organisation_id),
                "project_id": str(tenant.project_id),
                "environment": tenant.environment,
                "data": event_data,
            },
            status="pending",
        )
    )
