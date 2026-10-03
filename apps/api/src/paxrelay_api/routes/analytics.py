"""Tenant-scoped spend totals and capability breakdowns."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from paxrelay_db.models.analytics import (
    AnalyticsRefreshStateModel,
    AnalyticsSpendRollupModel,
)
from paxrelay_db.models.payments import PaymentModel, ToolCallModel
from paxrelay_db.repositories._common import sid

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.exceptions import InvalidRequestError
from paxrelay_api.schemas import AnalyticsCapabilityOut, AnalyticsSpendOut
from paxrelay_api.security.authorization import require_scope
from paxrelay_api.tenant import TenantContext

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Payment states that represent money actually committed by the agent.
_SPENT_STATES = ("verified", "settled_layerx", "anchored_l1")
_ROLLUP_PERIOD = "daily"
_ROLLUP_MAX_AGE_SECONDS = 180


def _utc_naive(value: datetime) -> datetime:
    """Use the database's UTC-naive timestamp convention for query bounds."""
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _default_range(
    start_date: datetime | None,
    end_date: datetime | None,
) -> tuple[datetime, datetime]:
    """Resolve the requested interval, defaulting to the previous 30 days."""
    resolved_end = (
        _utc_naive(end_date)
        if end_date
        else datetime.now(UTC).replace(tzinfo=None)
    )
    resolved_start = (
        _utc_naive(start_date)
        if start_date
        else resolved_end - timedelta(days=30)
    )
    if resolved_start >= resolved_end:
        raise InvalidRequestError("start_date must be before end_date.")
    return resolved_start, resolved_end


def _tenant_filters(tenant: TenantContext) -> tuple[ColumnElement[bool], ...]:
    return (
        ToolCallModel.organisation_id == sid(tenant.organisation_id),
        ToolCallModel.project_id == sid(tenant.project_id),
        ToolCallModel.environment == tenant.environment,
    )


async def _usable_daily_bounds(
    session: AsyncSession,
    tenant: TenantContext,
    start: datetime,
    end: datetime,
    *,
    now: datetime,
    max_age_seconds: int,
) -> tuple[datetime, datetime] | None:
    """Return fully covered whole-day bounds when a recent rollup is available."""
    state = await session.get(AnalyticsRefreshStateModel, tenant.environment)
    if state is None:
        return None

    age = (now - state.refreshed_at).total_seconds()
    if age < -30 or age > max_age_seconds:
        return None

    first_full_day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    if start != first_full_day:
        first_full_day += timedelta(days=1)
    full_days_end = end.replace(hour=0, minute=0, second=0, microsecond=0)
    last_complete_day_end = state.refreshed_at.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    if (
        first_full_day >= full_days_end
        or first_full_day < state.daily_from
        or full_days_end > last_complete_day_end
    ):
        return None
    return first_full_day, full_days_end


async def _raw_spend(
    session: AsyncSession,
    tenant: TenantContext,
    start: datetime,
    end: datetime,
    *,
    end_exclusive: bool,
) -> tuple[int, int]:
    if start >= end and end_exclusive:
        return 0, 0
    time_filter = (
        PaymentModel.created_at < end
        if end_exclusive
        else PaymentModel.created_at <= end
    )
    statement = (
        select(
            func.coalesce(func.sum(PaymentModel.amount_atomic), 0).label("total_atomic"),
            func.count(PaymentModel.id).label("transaction_count"),
        )
        .select_from(PaymentModel)
        .join(ToolCallModel, ToolCallModel.id == PaymentModel.tool_call_id)
        .where(
            *_tenant_filters(tenant),
            PaymentModel.state.in_(_SPENT_STATES),
            PaymentModel.created_at >= start,
            time_filter,
        )
    )
    row = (await session.execute(statement)).one()
    return int(row.total_atomic or 0), int(row.transaction_count or 0)


async def _spend_totals(
    session: AsyncSession,
    tenant: TenantContext,
    start: datetime,
    end: datetime,
    *,
    request: Request,
) -> tuple[int, int]:
    settings = getattr(request.app.state, "settings", None)
    max_age = getattr(
        settings,
        "analytics_rollup_max_age_seconds",
        _ROLLUP_MAX_AGE_SECONDS,
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    bounds = await _usable_daily_bounds(
        session,
        tenant,
        start,
        end,
        now=now,
        max_age_seconds=max_age,
    )
    if bounds is None:
        return await _raw_spend(
            session, tenant, start, end, end_exclusive=False
        )

    full_start, full_end = bounds
    total_atomic = 0
    transaction_count = 0

    if start < full_start:
        amount, count = await _raw_spend(
            session, tenant, start, full_start, end_exclusive=True
        )
        total_atomic += amount
        transaction_count += count

    rollup_statement = select(
        func.coalesce(func.sum(AnalyticsSpendRollupModel.total_amount_atomic), 0),
        func.coalesce(func.sum(AnalyticsSpendRollupModel.transaction_count), 0),
    ).where(
        AnalyticsSpendRollupModel.organisation_id == sid(tenant.organisation_id),
        AnalyticsSpendRollupModel.project_id == sid(tenant.project_id),
        AnalyticsSpendRollupModel.environment == tenant.environment,
        AnalyticsSpendRollupModel.period == _ROLLUP_PERIOD,
        AnalyticsSpendRollupModel.bucket_start >= full_start,
        AnalyticsSpendRollupModel.bucket_start < full_end,
    )
    amount, count = (await session.execute(rollup_statement)).one()
    total_atomic += int(amount or 0)
    transaction_count += int(count or 0)

    # Include the exact end timestamp. This preserves the API's existing
    # inclusive end-date behavior when it falls exactly at midnight.
    amount, count = await _raw_spend(
        session, tenant, full_end, end, end_exclusive=False
    )
    total_atomic += amount
    transaction_count += count
    return total_atomic, transaction_count


async def _raw_capabilities(
    session: AsyncSession,
    tenant: TenantContext,
    start: datetime,
    end: datetime,
    *,
    end_exclusive: bool,
) -> dict[str, tuple[int, int]]:
    if start >= end and end_exclusive:
        return {}
    time_filter = (
        PaymentModel.created_at < end
        if end_exclusive
        else PaymentModel.created_at <= end
    )
    statement = (
        select(
            ToolCallModel.capability.label("capability"),
            func.coalesce(func.sum(PaymentModel.amount_atomic), 0).label("amount"),
            func.count(PaymentModel.id).label("count"),
        )
        .select_from(ToolCallModel)
        .join(PaymentModel, PaymentModel.tool_call_id == ToolCallModel.id)
        .where(
            *_tenant_filters(tenant),
            PaymentModel.state.in_(_SPENT_STATES),
            PaymentModel.created_at >= start,
            time_filter,
        )
        .group_by(ToolCallModel.capability)
    )
    rows = (await session.execute(statement)).all()
    return {
        row.capability: (int(row.amount or 0), int(row.count or 0))
        for row in rows
    }


async def _capability_totals(
    session: AsyncSession,
    tenant: TenantContext,
    start: datetime,
    end: datetime,
    *,
    request: Request,
) -> dict[str, tuple[int, int]]:
    settings = getattr(request.app.state, "settings", None)
    max_age = getattr(
        settings,
        "analytics_rollup_max_age_seconds",
        _ROLLUP_MAX_AGE_SECONDS,
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    bounds = await _usable_daily_bounds(
        session,
        tenant,
        start,
        end,
        now=now,
        max_age_seconds=max_age,
    )
    if bounds is None:
        return await _raw_capabilities(
            session, tenant, start, end, end_exclusive=False
        )

    full_start, full_end = bounds
    totals: dict[str, tuple[int, int]] = {}

    if start < full_start:
        totals.update(
            await _raw_capabilities(
                session, tenant, start, full_start, end_exclusive=True
            )
        )

    rollup_statement = (
        select(
            AnalyticsSpendRollupModel.capability,
            func.sum(AnalyticsSpendRollupModel.total_amount_atomic).label("amount"),
            func.sum(AnalyticsSpendRollupModel.transaction_count).label("count"),
        )
        .where(
            AnalyticsSpendRollupModel.organisation_id == sid(tenant.organisation_id),
            AnalyticsSpendRollupModel.project_id == sid(tenant.project_id),
            AnalyticsSpendRollupModel.environment == tenant.environment,
            AnalyticsSpendRollupModel.period == _ROLLUP_PERIOD,
            AnalyticsSpendRollupModel.bucket_start >= full_start,
            AnalyticsSpendRollupModel.bucket_start < full_end,
        )
        .group_by(AnalyticsSpendRollupModel.capability)
    )
    for row in (await session.execute(rollup_statement)).all():
        previous_amount, previous_count = totals.get(row.capability, (0, 0))
        totals[row.capability] = (
            previous_amount + int(row.amount or 0),
            previous_count + int(row.count or 0),
        )

    trailing = await _raw_capabilities(
        session, tenant, full_end, end, end_exclusive=False
    )
    for capability, (amount, count) in trailing.items():
        previous_amount, previous_count = totals.get(capability, (0, 0))
        totals[capability] = (
            previous_amount + amount,
            previous_count + count,
        )
    return totals


@router.get(
    "/spend",
    response_model=AnalyticsSpendOut,
    dependencies=[Depends(require_scope("analytics:read"))],
)
async def get_spend_analytics(
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
    period: str = Query("daily", pattern=r"^(daily|monthly)$"),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
) -> AnalyticsSpendOut:
    """Aggregate committed spend for the tenant over the requested window."""
    start, end = _default_range(start_date, end_date)
    total_atomic, transaction_count = await _spend_totals(
        session, tenant, start, end, request=request
    )

    return AnalyticsSpendOut(
        period=period,
        start_date=start,
        end_date=end,
        total_amount_atomic=total_atomic,
        currency="USDX",
        decimals=6,
        transaction_count=transaction_count,
    )


@router.get(
    "/capabilities",
    response_model=list[AnalyticsCapabilityOut],
    dependencies=[Depends(require_scope("analytics:read"))],
)
async def get_capability_breakdown(
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> list[AnalyticsCapabilityOut]:
    """Break committed spend down by capability, highest spend first."""
    start, end = _default_range(start_date, end_date)
    totals = await _capability_totals(
        session, tenant, start, end, request=request
    )
    ordered = sorted(
        totals.items(),
        key=lambda item: (-item[1][0], item[0]),
    )[:limit]
    return [
        AnalyticsCapabilityOut(
            capability=capability,
            total_amount_atomic=amount,
            currency="USDX",
            decimals=6,
            call_count=count,
        )
        for capability, (amount, count) in ordered
    ]
