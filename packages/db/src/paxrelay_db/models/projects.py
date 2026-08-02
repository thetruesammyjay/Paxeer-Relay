"""ORM models: Project, ApiKey."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from paxrelay_db.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, pk_uuid


class Project(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "projects"

    id: Mapped[str] = pk_uuid()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ApiKey(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    """Hashed API key issued to an agent or dashboard user.

    The raw key is NEVER stored. Only the SHA-256 hash is persisted.
    The raw key is returned only once at creation time.
    """
    __tablename__ = "api_keys"

    id: Mapped[str] = pk_uuid()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    key_type: Mapped[str] = mapped_column(String(16), nullable=False)  # "test" | "live"
    scopes: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
