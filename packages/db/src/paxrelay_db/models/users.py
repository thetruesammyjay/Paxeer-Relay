"""ORM models: User, Organisation, Membership."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from paxrelay_db.base import Base, SoftDeleteMixin, TimestampMixin, pk_uuid


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[str] = pk_uuid()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Organisation(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "organisations"

    id: Mapped[str] = pk_uuid()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(32), default="free", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Membership(Base, TimestampMixin):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organisation_id", name="uq_membership"),
    )

    id: Mapped[str] = pk_uuid()
    user_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    organisation_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), default="member", nullable=False)
    invited_by: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)


class ExternalIdentity(Base, TimestampMixin):
    """A verified external identity linked to one PaxRelay user."""

    __tablename__ = "external_identities"
    __table_args__ = (
        UniqueConstraint("issuer", "subject", name="uq_external_identity_issuer_subject"),
    )

    id: Mapped[str] = pk_uuid()
    user_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    issuer: Mapped[str] = mapped_column(String(512), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)


class ProjectMembership(Base, TimestampMixin):
    """A user's role in one project and environment."""

    __tablename__ = "project_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "project_id", "environment", name="uq_project_membership_user_project_env"
        ),
        CheckConstraint(
            "role IN ('owner', 'admin', 'operator', 'analyst', 'viewer')",
            name="ck_project_membership_role",
        ),
        Index("ix_project_memberships_lookup", "user_id", "environment", "is_active"),
    )

    id: Mapped[str] = pk_uuid()
    user_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organisation_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("organisations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        PG_UUID(as_uuid=False),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
