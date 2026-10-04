"""ORM models: ExecutionAttempt, ExecutionReceipt, SettlementRecord,
ApprovalRequest, WebhookEndpoint, WebhookDelivery, AuditLog, OutboxEvent."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from paxrelay_db.base import Base, TenantMixin, TimestampMixin, pk_uuid


class ExecutionAttemptModel(Base, TimestampMixin):
    __tablename__ = "execution_attempts"
    __table_args__ = (
        Index(
            "ix_execution_attempts_service_version_created",
            "service_version_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_execution_attempts_terminal_completion",
            "response_received_at",
            "created_at",
            "attempt_number",
            "id",
            postgresql_where=text(
                "response_received_at IS NOT NULL AND execution_state IN "
                "('succeeded', 'provider_error', 'timeout', 'unknown')"
            ),
        ),
        Index(
            "ix_execution_attempts_active_stale",
            "execution_state",
            "created_at",
            "id",
            postgresql_where=text("execution_state IN ('reserved', 'running')"),
        ),
    )
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
    __table_args__ = (
        UniqueConstraint("payment_id", name="uq_settlement_record_payment"),
        Index(
            "ix_settlement_reconciliation_review",
            "reconciliation_status",
            "created_at",
            "id",
        ),
        Index(
            "ix_settlement_reconciliation_due",
            "next_attempt_at",
            "created_at",
            "id",
            postgresql_where=text(
                "reconciliation_status IN ('awaiting_external', 'layerx_confirmed')"
            ),
        ),
        Index(
            "ix_settlement_reconciliation_claim",
            "claimed_at",
            postgresql_where=text("claim_token IS NOT NULL"),
        ),
    )
    id: Mapped[str] = pk_uuid()
    payment_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    layerx_transaction_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    layerx_batch_id: Mapped[str | None] = mapped_column(String(66), nullable=True)
    l1_settlement_id: Mapped[str | None] = mapped_column(String(66), nullable=True)
    l1_block_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    l1_transaction_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    l1_commitment_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    reconciliation_status: Mapped[str] = mapped_column(
        String(32), default="awaiting_external", nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0"), nullable=False
    )
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(64), nullable=True)
    internal_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    internal_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mismatch_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ApprovalRequestModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "approval_requests"
    __table_args__ = (
        UniqueConstraint("tool_call_id", name="uq_approval_request_tool_call"),
        Index(
            "ix_approval_expiration_pending",
            "expires_at",
            "id",
            postgresql_where=text("status IN ('pending', 'approved')"),
        ),
    )
    id: Mapped[str] = pk_uuid()
    tool_call_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    amount_atomic: Mapped[int] = mapped_column(Numeric(78, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    currency_decimals: Mapped[int] = mapped_column(Integer, nullable=False)
    capability: Mapped[str] = mapped_column(String(256), nullable=False)
    provider_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
    service_version_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
    recipient_address: Mapped[str | None] = mapped_column(String(42), nullable=True)
    request_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    policy_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
    policy_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    decision_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)


class WebhookEndpointModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "webhook_endpoints"
    id: Mapped[str] = pk_uuid()
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    event_types: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # Keep the digest for auditing/legacy compatibility. The encrypted value
    # is required by the delivery worker to create an HMAC signature.
    secret_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    secret_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(256), nullable=True)


class WebhookDeliveryModel(Base, TimestampMixin):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index(
            "ix_webhook_delivery_due",
            "next_attempt_at",
            "created_at",
            "id",
            postgresql_where=text("status = 'pending'"),
        ),
        Index(
            "ix_webhook_delivery_stale_claim",
            "claimed_at",
            postgresql_where=text("status = 'processing'"),
        ),
    )
    id: Mapped[str] = pk_uuid()
    endpoint_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    http_status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    claim_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(64), nullable=True)


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
    __table_args__ = (
        Index(
            "ix_outbox_pending_created",
            "created_at",
            "id",
            postgresql_where=text("status = 'pending'"),
        ),
    )
    id: Mapped[str] = pk_uuid()
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
