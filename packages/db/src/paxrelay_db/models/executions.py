"""ORM models: ExecutionAttempt, ExecutionReceipt, SettlementRecord,
ApprovalRequest, WebhookEndpoint, WebhookDelivery, AuditLog, OutboxEvent."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from paxrelay_db.base import Base, TenantMixin, TimestampMixin, pk_uuid


class ExecutionAttemptModel(Base, TimestampMixin):
    __tablename__ = "execution_attempts"
    id: Mapped[str] = pk_uuid()
    tool_call_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    payment_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
    provider_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    service_version_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_state: Mapped[str] = mapped_column(String(32), default="not_started", nullable=False)
    request_forwarded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    response_received_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_retryable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ExecutionReceiptModel(Base, TimestampMixin):
    __tablename__ = "execution_receipts"
    id: Mapped[str] = pk_uuid()
    version: Mapped[str] = mapped_column(String(8), default="1", nullable=False)
    tool_call_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True, unique=True)
    agent_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    service_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    service_version: Mapped[str] = mapped_column(String(32), nullable=False)
    capability: Mapped[str] = mapped_column(String(256), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(66), nullable=False)
    response_hash: Mapped[str] = mapped_column(String(66), nullable=False)
    receipt_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    receipt_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    signing_key_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class SettlementRecordModel(Base, TimestampMixin):
    __tablename__ = "settlement_records"
    id: Mapped[str] = pk_uuid()
    payment_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    layerx_transaction_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    layerx_batch_id: Mapped[str | None] = mapped_column(String(66), nullable=True)
    l1_block_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    l1_transaction_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    l1_commitment_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    reconciliation_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mismatch_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ApprovalRequestModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "approval_requests"
    id: Mapped[str] = pk_uuid()
    tool_call_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    amount_atomic: Mapped[int] = mapped_column(Numeric(78, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    currency_decimals: Mapped[int] = mapped_column(Integer, nullable=False)
    capability: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    decided_by: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)


class WebhookEndpointModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "webhook_endpoints"
    id: Mapped[str] = pk_uuid()
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    event_types: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)


class WebhookDeliveryModel(Base, TimestampMixin):
    __tablename__ = "webhook_deliveries"
    id: Mapped[str] = pk_uuid()
    endpoint_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AuditLogModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "audit_logs"
    id: Mapped[str] = pk_uuid()
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)


class OutboxEventModel(Base, TenantMixin, TimestampMixin):
    """Transactional outbox pattern — events written atomically with business data."""
    __tablename__ = "outbox_events"
    id: Mapped[str] = pk_uuid()
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
