"""Analytics endpoints — spend totals and capability breakdown.

Tenant scoping note: ``PaymentModel`` has no organisation/project columns, so
every aggregate joins through ``ToolCallModel`` (which carries the tenant
columns) to keep results isolated to the caller's tenant.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from paxrelay_db.models.payments import PaymentModel, ToolCallModel
from paxrelay_db.repositories._common import sid

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.exceptions import InvalidRequestError
from paxrelay_api.schemas import AnalyticsCapabilityOut, AnalyticsSpendOut

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Payment states that represent money actually committed by the agent.
_SPENT_STATES = ("verified", "settled_layerx", "anchored_l1")


def _default_range(
    start_date: datetime | None,
    end_date: datetime | None,
) -> tuple[datetime, datetime]:
    """Resolve an optional date range, defaulting to the last 30 days."""
    resolved_end = end_date or datetime.utcnow()
    resolved_start = start_date or (resolved_end - timedelta(days=30))
    if resolved_start >= resolved_end:
        raise InvalidRequestError("start_date must be before end_date.")
    return resolved_start, resolved_end


@router.get("/spend", response_model=AnalyticsSpendOut)
async def get_spend_analytics(
    session: SessionDep,
    tenant: TenantDep,
    period: str = Query("daily", pattern=r"^(daily|monthly)$"),
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
) -> AnalyticsSpendOut:
    """Aggregate committed spend for the tenant over the requested window."""
    start, end = _default_range(start_date, end_date)

    stmt = (
        select(
            func.coalesce(func.sum(PaymentModel.amount_atomic), 0).label("total_atomic"),
            func.count(PaymentModel.id).label("transaction_count"),
        )
        .join(ToolCallModel, ToolCallModel.id == PaymentModel.tool_call_id)
        .where(
            ToolCallModel.organisation_id == sid(tenant.organisation_id),
            ToolCallModel.project_id == sid(tenant.project_id),
            PaymentModel.state.in_(_SPENT_STATES),
            PaymentModel.created_at >= start,
            PaymentModel.created_at <= end,
        )
    )
    row = (await session.execute(stmt)).one()

    return AnalyticsSpendOut(
        period=period,
        start_date=start,
        end_date=end,
        total_amount_atomic=int(row.total_atomic or 0),
        currency="USDX",
        decimals=6,
        transaction_count=int(row.transaction_count or 0),
    )


@router.get("/capabilities", response_model=list[AnalyticsCapabilityOut])
async def get_capability_breakdown(
    session: SessionDep,
    tenant: TenantDep,
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
) -> list[AnalyticsCapabilityOut]:
    """Break committed spend down by capability, highest spend first."""
    start, end = _default_range(start_date, end_date)

    stmt = (
        select(
            ToolCallModel.capability.label("capability"),
            func.coalesce(func.sum(PaymentModel.amount_atomic), 0).label("total_atomic"),
            func.count(PaymentModel.id).label("call_count"),
        )
        .join(PaymentModel, PaymentModel.tool_call_id == ToolCallModel.id)
        .where(
            ToolCallModel.organisation_id == sid(tenant.organisation_id),
            ToolCallModel.project_id == sid(tenant.project_id),
            PaymentModel.state.in_(_SPENT_STATES),
            PaymentModel.created_at >= start,
            PaymentModel.created_at <= end,
        )
        .group_by(ToolCallModel.capability)
        .order_by(func.sum(PaymentModel.amount_atomic).desc())
        .limit(limit)
    )
    rows = (await session.execute(stmt)).all()

    return [
        AnalyticsCapabilityOut(
            capability=row.capability,
            total_amount_atomic=int(row.total_atomic or 0),
            currency="USDX",
            decimals=6,
            call_count=int(row.call_count or 0),
        )
        for row in rows
    ]
