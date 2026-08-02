"""ORM models: ToolCall, RouteDecision, PaymentIntent, Payment, Quote."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from paxrelay_db.base import Base, TenantMixin, TimestampMixin, pk_uuid


class ToolCallModel(Base, TenantMixin, TimestampMixin):
    __tablename__ = "tool_calls"
    __table_args__ = (
        Index("ix_tool_call_idempotency", "agent_id", "idempotency_key", unique=True),
    )
    id: Mapped[str] = pk_uuid()
    agent_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    capability: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_state: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    payment_state: Mapped[str] = mapped_column(String(32), default="unpaid", nullable=False)
    execution_state: Mapped[str] = mapped_column(String(32), default="not_started", nullable=False)
    request_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    arguments_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    constraints_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class RouteDecisionModel(Base, TimestampMixin):
    __tablename__ = "route_decisions"
    id: Mapped[str] = pk_uuid()
    tool_call_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=False), nullable=True, index=True)
    provider_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    service_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    service_version_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    strategy: Mapped[str] = mapped_column(String(32), nullable=False)
    score_breakdown_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class QuoteModel(Base, TimestampMixin):
    __tablename__ = "quotes"
    id: Mapped[str] = pk_uuid()
    tool_call_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    service_version_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    amount_atomic: Mapped[int] = mapped_column(Numeric(78, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    currency_decimals: Mapped[int] = mapped_column(Integer, nullable=False)
    payment_scheme: Mapped[str] = mapped_column(String(16), default="402LXP", nullable=False)
    chain_id: Mapped[int] = mapped_column(Integer, default=125, nullable=False)
    settlement_layer: Mapped[str] = mapped_column(String(32), default="layerx", nullable=False)
    recipient_address: Mapped[str] = mapped_column(String(42), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(66), nullable=False)
    nonce: Mapped[str] = mapped_column(String(66), nullable=False, unique=True, index=True)
    quote_signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class PaymentIntentModel(Base, TimestampMixin):
    __tablename__ = "payment_intents"
    id: Mapped[str] = pk_uuid()
    tool_call_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    quote_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    agent_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    amount_atomic: Mapped[int] = mapped_column(Numeric(78, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    currency_decimals: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="unpaid", nullable=False)


class PaymentModel(Base, TimestampMixin):
    __tablename__ = "payments"
    id: Mapped[str] = pk_uuid()
    intent_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    tool_call_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    quote_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    agent_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False, index=True)
    provider_id: Mapped[str] = mapped_column(PG_UUID(as_uuid=False), nullable=False)
    amount_atomic: Mapped[int] = mapped_column(Numeric(78, 0), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    currency_decimals: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="submitted", nullable=False)
    proof: Mapped[str | None] = mapped_column(Text, nullable=True)
    layerx_transaction_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    layerx_batch_id: Mapped[str | None] = mapped_column(String(66), nullable=True)
    l1_settlement_id: Mapped[str | None] = mapped_column(String(66), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    anchored_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
