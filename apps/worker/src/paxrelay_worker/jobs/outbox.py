"""Fan transactional outbox events into durable webhook delivery rows."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from paxrelay_db import get_engine
from paxrelay_db.models.executions import (
    OutboxEventModel,
    WebhookDeliveryModel,
    WebhookEndpointModel,
)
from paxrelay_worker.jobs import BaseJob


class OutboxJob(BaseJob):
    """Create durable webhook deliveries for matching active endpoints."""

    interval_seconds = 5  # drain frequently to keep latency low
    batch_size = 100

    async def tick(self) -> None:
        session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
        async with session_factory() as session:
            stmt = (
                select(OutboxEventModel)
                .where(OutboxEventModel.status == "pending")
                .order_by(OutboxEventModel.created_at.asc(), OutboxEventModel.id.asc())
                .limit(self.batch_size)
                .with_for_update(skip_locked=True)
            )
            events = (await session.execute(stmt)).scalars().all()
            if not events:
                return

            tenant_filters = [
                and_(
                    WebhookEndpointModel.organisation_id == event.organisation_id,
                    WebhookEndpointModel.project_id == event.project_id,
                    WebhookEndpointModel.environment == event.environment,
                )
                for event in events
            ]
            endpoints_result = await session.execute(
                select(WebhookEndpointModel).where(
                    WebhookEndpointModel.is_active.is_(True),
                    or_(*tenant_filters),
                )
            )
            endpoints_by_tenant: dict[
                tuple[str, str, str], list[WebhookEndpointModel]
            ] = {}
            for endpoint in endpoints_result.scalars().all():
                key = (
                    endpoint.organisation_id,
                    endpoint.project_id,
                    endpoint.environment,
                )
                endpoints_by_tenant.setdefault(key, []).append(endpoint)

            now = datetime.now(UTC).replace(tzinfo=None)
            delivery_count = 0
            for event in events:
                tenant_key = (
                    event.organisation_id,
                    event.project_id,
                    event.environment,
                )
                for endpoint in endpoints_by_tenant.get(tenant_key, []):
                    if event.event_type not in (endpoint.event_types or []):
                        continue
                    session.add(
                        WebhookDeliveryModel(
                            endpoint_id=endpoint.id,
                            event_type=event.event_type,
                            payload_json=event.payload_json,
                            status="pending",
                            next_attempt_at=now,
                        )
                    )
                    delivery_count += 1

                # Fan-out and this state transition commit together. If the
                # transaction rolls back, the event stays pending for retry.
                event.status = "processed"
                event.processed_at = now
                event.attempts += 1
                event.error = None

            await session.commit()

        self.log.info(
            "Fanned out %d outbox event(s) into %d webhook delivery row(s)",
            len(events),
            delivery_count,
        )
