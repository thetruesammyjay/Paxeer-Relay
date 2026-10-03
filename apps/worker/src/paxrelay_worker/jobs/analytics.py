"""Refresh bounded hourly and daily committed-spend rollups."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, func, literal, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paxrelay_db import get_engine
from paxrelay_db.models.analytics import (
    AnalyticsRefreshStateModel,
    AnalyticsSpendRollupModel,
)
from paxrelay_db.models.payments import PaymentModel, ToolCallModel
from paxrelay_worker.config import WorkerSettings
from paxrelay_worker.jobs import BaseJob

_SPENT_STATES = ("verified", "settled_layerx", "anchored_l1")
_ADVISORY_LOCK_KEY = 0x5052584C595F414E  # "PRXLY_AN", reserved for this worker job.
_DIMENSIONS = (
    "organisation_id",
    "project_id",
    "environment",
    "period",
    "bucket_start",
    "agent_id",
    "capability",
    "currency",
    "currency_decimals",
)


class AnalyticsJob(BaseJob):
    """Rebuild recent per-tenant spend totals so retries remain idempotent."""

    @property
    def interval_seconds(self) -> int:
        return self.settings.analytics_flush_interval_seconds

    def __init__(self, settings: WorkerSettings) -> None:
        super().__init__(settings)
        self._sessions = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )

    async def tick(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hourly_cutoff = hour_start - timedelta(
            days=self.settings.analytics_hourly_retention_days
        )
        daily_cutoff = day_start - timedelta(
            days=self.settings.analytics_daily_retention_days
        )

        async with self._sessions() as session:
            locked = await session.scalar(
                select(func.pg_try_advisory_xact_lock(_ADVISORY_LOCK_KEY))
            )
            if not locked:
                self.log.debug("Analytics refresh skipped; another worker holds the lock")
                return

            await session.execute(
                delete(AnalyticsSpendRollupModel).where(
                    AnalyticsSpendRollupModel.environment == self.settings.app_env,
                    or_(
                        and_(
                            AnalyticsSpendRollupModel.period == "hourly",
                            AnalyticsSpendRollupModel.bucket_start >= hourly_cutoff,
                        ),
                        and_(
                            AnalyticsSpendRollupModel.period == "daily",
                            AnalyticsSpendRollupModel.bucket_start >= daily_cutoff,
                        ),
                    ),
                )
            )

            hourly_count = await self._refresh_period(
                session,
                period="hourly",
                date_part="hour",
                cutoff=hourly_cutoff,
                now=now,
            )
            daily_count = await self._refresh_period(
                session,
                period="daily",
                date_part="day",
                cutoff=daily_cutoff,
                now=now,
            )
            state_insert = pg_insert(AnalyticsRefreshStateModel).values(
                environment=self.settings.app_env,
                refreshed_at=now,
                hourly_from=hourly_cutoff,
                daily_from=daily_cutoff,
            )
            await session.execute(
                state_insert.on_conflict_do_update(
                    index_elements=[AnalyticsRefreshStateModel.environment],
                    set_={
                        "refreshed_at": state_insert.excluded.refreshed_at,
                        "hourly_from": state_insert.excluded.hourly_from,
                        "daily_from": state_insert.excluded.daily_from,
                    },
                )
            )
            await session.commit()

        self.log.info(
            "Spend rollups refreshed environment=%s hourly=%d daily=%d",
            self.settings.app_env,
            hourly_count,
            daily_count,
        )

    async def _refresh_period(
        self,
        session: AsyncSession,
        *,
        period: str,
        date_part: str,
        cutoff: datetime,
        now: datetime,
    ) -> int:
        bucket_start = func.date_trunc(date_part, PaymentModel.created_at)
        aggregate = (
            select(
                ToolCallModel.organisation_id,
                ToolCallModel.project_id,
                ToolCallModel.environment,
                literal(period).label("period"),
                bucket_start.label("bucket_start"),
                ToolCallModel.agent_id,
                ToolCallModel.capability,
                PaymentModel.currency,
                PaymentModel.currency_decimals,
                func.sum(PaymentModel.amount_atomic).label("total_amount_atomic"),
                func.count(PaymentModel.id).label("transaction_count"),
                literal(now).label("refreshed_at"),
            )
            .select_from(PaymentModel)
            .join(ToolCallModel, ToolCallModel.id == PaymentModel.tool_call_id)
            .where(
                ToolCallModel.environment == self.settings.app_env,
                PaymentModel.state.in_(_SPENT_STATES),
                PaymentModel.created_at >= cutoff,
                PaymentModel.created_at <= now,
            )
            .group_by(
                ToolCallModel.organisation_id,
                ToolCallModel.project_id,
                ToolCallModel.environment,
                bucket_start,
                ToolCallModel.agent_id,
                ToolCallModel.capability,
                PaymentModel.currency,
                PaymentModel.currency_decimals,
            )
        )
        statement = pg_insert(AnalyticsSpendRollupModel).from_select(
            [*_DIMENSIONS, "total_amount_atomic", "transaction_count", "refreshed_at"],
            aggregate,
        )
        statement = statement.on_conflict_do_update(
            index_elements=[
                getattr(AnalyticsSpendRollupModel, dimension)
                for dimension in _DIMENSIONS
            ],
            set_={
                "total_amount_atomic": statement.excluded.total_amount_atomic,
                "transaction_count": statement.excluded.transaction_count,
                "refreshed_at": statement.excluded.refreshed_at,
                "updated_at": now,
            },
        )
        result = await session.execute(statement)
        return max(result.rowcount or 0, 0)
