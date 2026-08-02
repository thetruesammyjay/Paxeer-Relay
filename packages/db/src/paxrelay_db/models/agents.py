"""ORM models: Agent, Wallet."""

from __future__ import annotations

from sqlalchemy import Boolean, JSON, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from paxrelay_db.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, pk_uuid


class AgentModel(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", "environment", name="uq_agent_slug"),
    )

    id: Mapped[str] = pk_uuid()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    wallet_address: Mapped[str | None] = mapped_column(String(42), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class WalletModel(Base, TimestampMixin):
    __tablename__ = "wallets"

    id: Mapped[str] = pk_uuid()
    agent_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    address: Mapped[str] = mapped_column(String(42), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    label: Mapped[str | None] = mapped_column(String(64), nullable=True)
