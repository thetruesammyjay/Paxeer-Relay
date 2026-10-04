"""Mark paid provider attempts abandoned by a stopped gateway as unknown."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm import load_only

from paxrelay_db import get_engine
from paxrelay_db.models.executions import (
    AuditLogModel,
    ExecutionAttemptModel,
    OutboxEventModel,
)
from paxrelay_db.models.payments import PaymentModel, ToolCallModel
from paxrelay_domain import EventType, ExecutionState, RequestState
from paxrelay_worker.config import WorkerSettings
from paxrelay_worker.jobs import BaseJob


class ExecutionRecoveryJob(BaseJob):
    """Close stale execution reservations without replaying paid requests."""

    def __init__(self, settings: WorkerSettings) -> None:
        super().__init__(settings)
        self.interval_seconds = settings.execution_recovery_interval_seconds
        self.batch_size = settings.execution_recovery_batch_size

    async def tick(self) -> None:
        now = datetime.utcnow()
        stale_before = now - timedelta(
            seconds=self.settings.execution_recovery_stale_seconds
        )
        session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
        recovered = 0
        async with session_factory() as session:
            stmt = (
                select(ExecutionAttemptModel, ToolCallModel)
                .join(
                    ToolCallModel,
                    ToolCallModel.id == ExecutionAttemptModel.tool_call_id,
                )
                .join(
                    PaymentModel,
                    PaymentModel.id == ExecutionAttemptModel.payment_id,
                )
                .where(
                    PaymentModel.state.in_(
                        ("verified", "settled_layerx", "anchored_l1")
                    ),
                    ExecutionAttemptModel.execution_state.in_(
                        (
                            ExecutionState.RESERVED.value,
                            ExecutionState.RUNNING.value,
                        )
                    ),
                    ExecutionAttemptModel.created_at <= stale_before,
                    ToolCallModel.request_state.in_(
                        (
                            RequestState.EXECUTION_RESERVED.value,
                            RequestState.EXECUTING.value,
                        )
                    ),
                    ToolCallModel.execution_state.in_(
                        (
                            ExecutionState.RESERVED.value,
                            ExecutionState.RUNNING.value,
                        )
                    ),
                )
                .order_by(
                    ExecutionAttemptModel.created_at.asc(),
                    ExecutionAttemptModel.id.asc(),
                )
                .options(
                    load_only(
                        ToolCallModel.id,
                        ToolCallModel.organisation_id,
                        ToolCallModel.project_id,
                        ToolCallModel.environment,
                        ToolCallModel.payment_state,
                        ToolCallModel.request_state,
                        ToolCallModel.execution_state,
                    )
                )
                .limit(self.batch_size)
                .with_for_update(
                    skip_locked=True,
                    of=(ExecutionAttemptModel, ToolCallModel),
                )
            )
            rows = (await session.execute(stmt)).all()
            event_type = EventType.CALL_RECOVERY_REQUIRED.value
            for attempt, call in rows:
                attempt.execution_state = ExecutionState.UNKNOWN.value
                call.execution_state = ExecutionState.UNKNOWN.value
                call.request_state = RequestState.FAILED.value

                event_id = str(uuid4())
                details = {
                    "tool_call_id": call.id,
                    "execution_attempt_id": attempt.id,
                    "payment_state": call.payment_state,
                    "execution_state": ExecutionState.UNKNOWN.value,
                }
                session.add(
                    AuditLogModel(
                        organisation_id=call.organisation_id,
                        project_id=call.project_id,
                        environment=call.environment,
                        event_type=event_type,
                        actor_id="system:execution-recovery",
                        resource_type="tool_call",
                        resource_id=call.id,
                        details=details,
                    )
                )
                session.add(
                    OutboxEventModel(
                        id=event_id,
                        organisation_id=call.organisation_id,
                        project_id=call.project_id,
                        environment=call.environment,
                        event_type=event_type,
                        payload_json={
                            "event_id": event_id,
                            "event_type": event_type,
                            "occurred_at": f"{now.isoformat()}Z",
                            "organisation_id": call.organisation_id,
                            "project_id": call.project_id,
                            "environment": call.environment,
                            "data": details,
                        },
                        status="pending",
                    )
                )
                recovered += 1

            if recovered:
                await session.commit()

        if recovered:
            self.log.warning(
                "Marked %d stale paid execution(s) unknown; no provider retry was sent",
                recovered,
            )
