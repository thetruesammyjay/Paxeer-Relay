"""ORM models: Provider, Service, ServiceVersion, ProviderMetrics."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from paxrelay_db.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin, pk_uuid


class ProviderModel(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "providers"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", "environment", name="uq_provider_slug"),
    )

    id: Mapped[str] = pk_uuid()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    wallet_address: Mapped[str | None] = mapped_column(String(42), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ServiceModel(Base, TenantMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "services"
    __table_args__ = (
        UniqueConstraint("provider_id", "slug", "environment", name="uq_service_slug"),
    )

    id: Mapped[str] = pk_uuid()
    provider_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    capability: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    protocols: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Pricing stored as JSON (pricing model + atomic amount + currency)
    pricing_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    delivery_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    health_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class ServiceVersionModel(Base, TimestampMixin):
    __tablename__ = "service_versions"

    id: Mapped[str] = pk_uuid()
    service_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    capability: Mapped[str] = mapped_column(String(256), nullable=False)
    endpoint_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    protocol: Mapped[str] = mapped_column(String(16), default="http", nullable=False)
    mcp_tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    mcp_input_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    pricing_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    delivery_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    openapi_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ProviderMetricsModel(Base, TimestampMixin):
    __tablename__ = "provider_metrics"

    id: Mapped[str] = pk_uuid()
    service_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    reputation_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    success_rate: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    availability_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    health_check_passing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
