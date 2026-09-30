"""ORM model for temporary per-agent spend reservations."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from paxrelay_db.base import Base, TenantMixin, TimestampMixin, pk_uuid


class BudgetReservationModel(Base, TenantMixin, TimestampMixin):
    """Reserve policy budget while a payment quote is valid."""

    __tablename__ = "budget_reservations"
    __table_args__ = (
        UniqueConstraint("quote_id", name="uq_budget_reservation_quote"),
        Index(
            "ix_budget_reservation_agent_status_expiry",
            "agent_id",
            "status",
            "expires_at",
        ),
    )

    id: Mapped[str] = pk_uuid()
    agent_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    quote_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    amount_atomic: Mapped[int] = mapped_column(Numeric(78, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
