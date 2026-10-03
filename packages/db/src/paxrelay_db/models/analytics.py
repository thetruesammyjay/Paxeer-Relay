"""Materialized spend aggregates used by reporting and dashboard queries."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from paxrelay_db.base import Base, TenantMixin, TimestampMixin


class AnalyticsSpendRollupModel(Base, TenantMixin, TimestampMixin):
    """Hourly and daily committed spend per tenant, agent, and capability."""

    __tablename__ = "analytics_spend_rollups"
    __table_args__ = (
        Index(
            "uq_analytics_spend_rollup_dimensions",
            "organisation_id",
            "project_id",
            "environment",
            "period",
            "bucket_start",
            "agent_id",
            "capability",
            "currency",
            "currency_decimals",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    period: Mapped[str] = mapped_column(String(8), nullable=False)
    bucket_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    agent_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    capability: Mapped[str] = mapped_column(String(256), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    currency_decimals: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount_atomic: Mapped[int] = mapped_column(Numeric(78, 0), nullable=False)
    transaction_count: Mapped[int] = mapped_column(Integer, nullable=False)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class AnalyticsRefreshStateModel(Base):
    """Successful refresh watermark for each worker environment."""

    __tablename__ = "analytics_refresh_state"

    environment: Mapped[str] = mapped_column(String(32), primary_key=True)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    hourly_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    daily_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
