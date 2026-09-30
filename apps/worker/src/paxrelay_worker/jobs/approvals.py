"""Expire policy approvals that were not acted on before their deadline."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from paxrelay_db import get_engine
from paxrelay_db.models.executions import (
    ApprovalRequestModel,
    AuditLogModel,
    OutboxEventModel,
)
from paxrelay_db.models.payments import ToolCallModel
from paxrelay_worker.jobs import BaseJob


class ApprovalExpirationJob(BaseJob):
    """Expire stale approval rows and their pending tool calls atomically."""

    interval_seconds = 30
    batch_size = 500

    async def tick(self) -> None:
        now = datetime.utcnow()
        session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
        async with session_factory() as session:
            stmt = (
                select(ApprovalRequestModel)
                .where(
                    ApprovalRequestModel.status.in_(("pending", "approved")),
                    ApprovalRequestModel.expires_at.is_not(None),
                    ApprovalRequestModel.expires_at <= now,
                )
                .order_by(
                    ApprovalRequestModel.expires_at.asc(),
                    ApprovalRequestModel.id.asc(),
                )
                .limit(self.batch_size)
                .with_for_update(skip_locked=True)
            )
            rows = (await session.execute(stmt)).scalars().all()
            if not rows:
                return

            for row in rows:
                row.status = "expired"
                row.decided_at = now
                event_id = str(uuid4())
                session.add(
                    AuditLogModel(
                        organisation_id=row.organisation_id,
                        project_id=row.project_id,
                        environment=row.environment,
                        event_type="approval.expired",
                        actor_id="system:approval-expiration",
                        resource_type="approval_request",
                        resource_id=row.id,
                        details={"tool_call_id": row.tool_call_id},
                    )
                )
                session.add(
                    OutboxEventModel(
                        id=event_id,
                        organisation_id=row.organisation_id,
                        project_id=row.project_id,
                        environment=row.environment,
                        event_type="approval.expired",
                        payload_json={
                            "event_id": event_id,
                            "event_type": "approval.expired",
                            "occurred_at": f"{now.isoformat()}Z",
                            "organisation_id": row.organisation_id,
                            "project_id": row.project_id,
                            "environment": row.environment,
                            "data": {
                                "resource_type": "approval_request",
                                "resource_id": row.id,
                                "tool_call_id": row.tool_call_id,
                            },
                        },
                        status="pending",
                    )
                )

            tool_call_ids = [row.tool_call_id for row in rows]
            await session.execute(
                update(ToolCallModel)
                .where(
                    ToolCallModel.id.in_(tool_call_ids),
                    ToolCallModel.request_state == "approval_pending",
                )
                .values(request_state="expired", updated_at=now)
            )
            await session.commit()

        self.log.info("Expired %d policy approval request(s)", len(rows))
