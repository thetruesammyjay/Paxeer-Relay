"""Aggregate recent provider execution results into routing metrics."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, case, func, select
from sqlalchemy.engine import Row
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paxrelay_db import get_engine
from paxrelay_db.models.executions import ExecutionAttemptModel
from paxrelay_db.models.providers import (
    ProviderMetricsModel,
    ProviderModel,
    ServiceModel,
    ServiceVersionModel,
)
from paxrelay_worker.config import WorkerSettings
from paxrelay_worker.jobs import BaseJob

_TERMINAL_ATTEMPT_STATES = (
    "succeeded",
    "provider_error",
    "timeout",
    "cancelled",
    "unknown",
)
_SUCCESS_STATE = "succeeded"


class ProviderIndexJob(BaseJob):
    """Refresh rolling success, latency, and failure metrics per service."""

    interval_seconds = 60

    def __init__(self, settings: WorkerSettings) -> None:
        super().__init__(settings)
        self._sessions = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )

    async def tick(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        cutoff = now - timedelta(days=self.settings.provider_metrics_window_days)

        async with self._sessions() as session:
            totals = await self._load_totals(session, cutoff)
            if not totals:
                return
            trailing_failures = await self._load_trailing_failures(
                session,
                cutoff,
                [row.service_id for row in totals],
            )

            updated = 0
            for row in totals:
                service_id = str(row.service_id)
                total_calls = int(row.total_calls or 0)
                successful_calls = int(row.successful_calls or 0)
                if total_calls:
                    success_rate = successful_calls / total_calls
                else:
                    # No observations are neutral; do not retain stale success data.
                    success_rate = 0.5

                statement = (
                    select(ProviderMetricsModel)
                    .where(
                        ProviderMetricsModel.service_id == service_id,
                        ProviderMetricsModel.provider_id == str(row.provider_id),
                    )
                    .with_for_update()
                )
                metrics = (await session.execute(statement)).scalar_one_or_none()
                if metrics is None:
                    self.log.error(
                        "Provider metrics row missing during indexing service_id=%s",
                        service_id,
                    )
                    continue

                metrics.total_calls = total_calls
                metrics.success_rate = success_rate
                metrics.avg_latency_ms = float(row.avg_latency_ms or 0.0)
                metrics.consecutive_failures = trailing_failures.get(service_id, 0)
                metrics.measured_at = now
                updated += 1

            await session.commit()

        self.log.info(
            "Provider routing metrics refreshed services=%d window_days=%d",
            updated,
            self.settings.provider_metrics_window_days,
        )

    async def _load_totals(
        self, session: AsyncSession, cutoff: datetime
    ) -> Sequence[Row[Any]]:
        attempt_match = and_(
            ExecutionAttemptModel.service_version_id == ServiceVersionModel.id,
            ExecutionAttemptModel.created_at >= cutoff,
            ExecutionAttemptModel.execution_state.in_(_TERMINAL_ATTEMPT_STATES),
        )
        statement = (
            select(
                ServiceModel.id.label("service_id"),
                ServiceModel.provider_id.label("provider_id"),
                func.count(ExecutionAttemptModel.id).label("total_calls"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ExecutionAttemptModel.execution_state == _SUCCESS_STATE,
                                1,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("successful_calls"),
                func.avg(ExecutionAttemptModel.latency_ms).label("avg_latency_ms"),
            )
            .select_from(ServiceModel)
            .join(ProviderModel, ProviderModel.id == ServiceModel.provider_id)
            .outerjoin(
                ServiceVersionModel,
                ServiceVersionModel.service_id == ServiceModel.id,
            )
            .outerjoin(ExecutionAttemptModel, attempt_match)
            .where(
                ServiceModel.environment == self.settings.app_env,
                ServiceModel.status == "active",
                ServiceModel.deleted_at.is_(None),
                ProviderModel.environment == self.settings.app_env,
                ProviderModel.status == "active",
                ProviderModel.deleted_at.is_(None),
            )
            .group_by(ServiceModel.id, ServiceModel.provider_id)
            .order_by(ServiceModel.id.asc())
        )
        return (await session.execute(statement)).all()

    async def _load_trailing_failures(
        self,
        session: AsyncSession,
        cutoff: datetime,
        service_ids: list[str],
    ) -> dict[str, int]:
        ranked = (
            select(
                ServiceVersionModel.service_id.label("service_id"),
                ExecutionAttemptModel.execution_state.label("execution_state"),
                func.row_number()
                .over(
                    partition_by=ServiceVersionModel.service_id,
                    order_by=(
                        ExecutionAttemptModel.created_at.desc(),
                        ExecutionAttemptModel.id.desc(),
                    ),
                )
                .label("attempt_rank"),
            )
            .join(
                ExecutionAttemptModel,
                ExecutionAttemptModel.service_version_id == ServiceVersionModel.id,
            )
            .where(
                ServiceVersionModel.service_id.in_(service_ids),
                ExecutionAttemptModel.created_at >= cutoff,
                ExecutionAttemptModel.execution_state.in_(_TERMINAL_ATTEMPT_STATES),
            )
            .subquery()
        )
        statement = (
            select(ranked.c.service_id, ranked.c.execution_state)
            .where(
                ranked.c.attempt_rank
                <= self.settings.provider_metrics_trailing_attempts
            )
            .order_by(ranked.c.service_id.asc(), ranked.c.attempt_rank.asc())
        )
        rows = (await session.execute(statement)).all()

        states_by_service: dict[str, list[str]] = {}
        for row in rows:
            states_by_service.setdefault(str(row.service_id), []).append(
                row.execution_state
            )
        return {
            service_id: streak
            for service_id, states in states_by_service.items()
            if (streak := _consecutive_failures(states)) > 0
        }


def _consecutive_failures(states: Iterable[str]) -> int:
    """Count newest failures up to the first success in newest-first order."""
    failures = 0
    for state in states:
        if state == _SUCCESS_STATE:
            break
        failures += 1
    return failures
