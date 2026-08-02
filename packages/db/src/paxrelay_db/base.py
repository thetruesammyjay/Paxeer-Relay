"""SQLAlchemy declarative base and shared ORM mixins.

Design rules:
- All primary keys are UUID strings (stored as native UUID on Postgres).
- All monetary values are NUMERIC(78, 0) + a currency column — never floats.
- All tenant-scoped tables carry organisation_id, project_id, and environment.
- All timestamps are stored in UTC and returned as timezone-naive UTC datetimes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all PaxRelay ORM models."""

    type_annotation_map: dict[Any, Any] = {}


# ---------------------------------------------------------------------------
# Reusable column factories
# ---------------------------------------------------------------------------


def pk_uuid() -> MappedColumn[str]:
    """Primary key column — UUID v4, stored as native Postgres UUID."""
    return mapped_column(
        PG_UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )


def fk_uuid(nullable: bool = False) -> MappedColumn[str | None]:
    """Foreign key UUID column."""
    return mapped_column(PG_UUID(as_uuid=False), nullable=nullable)


def utcnow_col(server_default: bool = True) -> MappedColumn[datetime]:
    """Timestamp column defaulting to current UTC time."""
    if server_default:
        return mapped_column(DateTime, server_default=func.now(), nullable=False)
    return mapped_column(DateTime, nullable=False, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Mixins
# ---------------------------------------------------------------------------


class TimestampMixin:
    """Adds created_at and updated_at to any model."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TenantMixin:
    """Adds multi-tenancy columns required on every tenant-owned table.

    Database queries MUST enforce all three scoping columns.
    Row-Level Security may add defence-in-depth but must not replace
    application-level checks.
    """

    organisation_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), nullable=False, index=True
    )
    project_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False), nullable=False, index=True
    )
    environment: Mapped[str] = mapped_column(
        String(32), nullable=False, default="development"
    )


class SoftDeleteMixin:
    """Adds soft-delete support via a deleted_at timestamp.

    A non-null deleted_at means the record is logically deleted
    but preserved for auditing purposes.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def soft_delete(self) -> None:
        self.deleted_at = datetime.utcnow()

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
