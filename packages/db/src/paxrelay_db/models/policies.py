"""ORM models: Policy, PolicyRule, PolicyAssignment."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from paxrelay_db.base import Base, TenantMixin, TimestampMixin, pk_uuid


class PolicyModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "policies"

    id: Mapped[str] = pk_uuid()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default="enforce", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Serialised policy rules stored as JSON for flexibility
    rules_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class PolicyRuleModel(Base, TimestampMixin):
    """Individual rule rows for structured querying (redundant with rules_json but queryable)."""
    __tablename__ = "policy_rules"

    id: Mapped[str] = pk_uuid()
    policy_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # Monetary rule values stored as atomics
    amount_atomic: Mapped[int | None] = mapped_column(Numeric(78, 0), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # Non-monetary rule values
    numeric_value: Mapped[float | None] = mapped_column(nullable=True)
    string_value: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    json_value: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class PolicyAssignmentModel(Base, TimestampMixin):
    __tablename__ = "policy_assignments"
    __table_args__ = (
        UniqueConstraint("agent_id", "policy_id", name="uq_policy_assignment"),
    )

    id: Mapped[str] = pk_uuid()
    agent_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    policy_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    assigned_by: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
