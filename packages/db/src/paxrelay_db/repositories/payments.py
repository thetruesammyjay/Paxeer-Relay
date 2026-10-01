"""SQLAlchemy implementations of ToolCallRepository and PaymentRepository."""

from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_domain import (
    Environment,
    ExecutionAttempt,
    ExecutionState,
    Payment,
    PaymentIntent,
    PaymentState,
    Quote,
    RequestState,
    ToolCall,
)
from paxrelay_db.models.agents import AgentModel
from paxrelay_db.models.budget import BudgetReservationModel
from paxrelay_db.models.executions import ExecutionAttemptModel
from paxrelay_db.models.payments import (
    PaymentIntentModel,
    PaymentModel,
    QuoteModel,
    ToolCallModel,
)
from paxrelay_db.repositories._common import as_uuid, sid


# ---------------------------------------------------------------------------
# Mappers
# ---------------------------------------------------------------------------


def _to_tool_call(m: ToolCallModel) -> ToolCall:
    return ToolCall(
        id=as_uuid(m.id),
        agent_id=as_uuid(m.agent_id),
        organisation_id=as_uuid(m.organisation_id),
        project_id=as_uuid(m.project_id),
        capability=m.capability,
        idempotency_key=m.idempotency_key,
        request_state=RequestState(m.request_state),
        payment_state=PaymentState(m.payment_state),
        execution_state=ExecutionState(m.execution_state),
        request_hash=m.request_hash,
        arguments=m.arguments_json or {},
        constraints=m.constraints_json or {},
        result_json=m.result_json,
        metadata=m.extra_metadata or {},
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_quote(m: QuoteModel) -> Quote:
    return Quote(
        id=as_uuid(m.id),
        tool_call_id=as_uuid(m.tool_call_id),
        provider_id=as_uuid(m.provider_id),
        service_version_id=as_uuid(m.service_version_id),
        amount={
            "amount_atomic": int(m.amount_atomic),
            "currency": m.currency,
            "decimals": m.currency_decimals,
        },
        payment_scheme=m.payment_scheme,
        chain_id=m.chain_id,
        settlement_layer=m.settlement_layer,
        recipient_address=m.recipient_address,
        request_hash=m.request_hash,
        nonce=m.nonce,
        quote_signature=m.quote_signature,
        created_at=m.created_at,
        expires_at=m.expires_at,
    )


def _to_intent(m: PaymentIntentModel) -> PaymentIntent:
    return PaymentIntent(
        id=as_uuid(m.id),
        tool_call_id=as_uuid(m.tool_call_id),
        quote_id=as_uuid(m.quote_id),
        agent_id=as_uuid(m.agent_id),
        provider_id=as_uuid(m.provider_id),
        amount={
            "amount_atomic": int(m.amount_atomic),
            "currency": m.currency,
            "decimals": m.currency_decimals,
        },
        state=PaymentState(m.state),
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_payment(m: PaymentModel) -> Payment:
    return Payment(
        id=as_uuid(m.id),
        intent_id=as_uuid(m.intent_id),
        tool_call_id=as_uuid(m.tool_call_id),
        quote_id=as_uuid(m.quote_id),
        agent_id=as_uuid(m.agent_id),
        provider_id=as_uuid(m.provider_id),
        amount={
            "amount_atomic": int(m.amount_atomic),
            "currency": m.currency,
            "decimals": m.currency_decimals,
        },
        state=PaymentState(m.state),
        proof=m.proof,
        layerx_transaction_hash=m.layerx_transaction_hash,
        layerx_batch_id=m.layerx_batch_id,
        l1_settlement_id=m.l1_settlement_id,
        verified_at=m.verified_at,
        settled_at=m.settled_at,
        anchored_at=m.anchored_at,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_attempt(m: ExecutionAttemptModel) -> ExecutionAttempt:
    return ExecutionAttempt(
        id=as_uuid(m.id),
        tool_call_id=as_uuid(m.tool_call_id),
        payment_id=as_uuid(m.payment_id) if m.payment_id else None,
        provider_id=as_uuid(m.provider_id),
        service_version_id=as_uuid(m.service_version_id),
        attempt_number=m.attempt_number,
        execution_state=ExecutionState(m.execution_state),
        request_forwarded_at=m.request_forwarded_at,
        response_received_at=m.response_received_at,
        latency_ms=m.latency_ms,
        http_status_code=m.http_status_code,
        provider_error_code=m.provider_error_code,
        is_retryable=m.is_retryable,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


# ---------------------------------------------------------------------------
# ToolCall repository
# ---------------------------------------------------------------------------


class SqlAlchemyToolCallRepository:
    """Persists tool calls (the aggregate root) and their execution attempts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, tool_call_id: UUID) -> ToolCall | None:
        m = await self._session.get(ToolCallModel, sid(tool_call_id))
        return _to_tool_call(m) if m is not None else None

    async def get_by_idempotency_key(
        self,
        agent_id: UUID,
        idempotency_key: str,
    ) -> ToolCall | None:
        stmt = select(ToolCallModel).where(
            ToolCallModel.agent_id == sid(agent_id),
            ToolCallModel.idempotency_key == idempotency_key,
        )
        m = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_tool_call(m) if m is not None else None

    async def lock_idempotency_key(
        self,
        agent_id: UUID,
        idempotency_key: str,
    ) -> None:
        """Serialize concurrent requests using the same per-agent key."""
        digest = hashlib.sha256(agent_id.bytes + b"\0" + idempotency_key.encode()).digest()
        lock_key = int.from_bytes(digest[:8], byteorder="big", signed=True)
        await self._session.execute(select(func.pg_advisory_xact_lock(lock_key)))

    async def list(
        self,
        organisation_id: UUID,
        project_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ToolCall]:
        stmt = (
            select(ToolCallModel)
            .where(
                ToolCallModel.organisation_id == sid(organisation_id),
                ToolCallModel.project_id == sid(project_id),
            )
            .order_by(ToolCallModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_tool_call(m) for m in rows]

    async def save(self, call: ToolCall) -> ToolCall:
        m = await self._session.get(ToolCallModel, sid(call.id))
        if m is None:
            m = ToolCallModel(id=sid(call.id))
            self._session.add(m)
        m.agent_id = sid(call.agent_id)
        m.organisation_id = sid(call.organisation_id)
        m.project_id = sid(call.project_id)
        m.capability = call.capability
        m.idempotency_key = call.idempotency_key
        m.request_state = call.request_state.value
        m.payment_state = call.payment_state.value
        m.execution_state = call.execution_state.value
        m.request_hash = call.request_hash
        m.arguments_json = dict(call.arguments)
        m.constraints_json = dict(call.constraints)
        m.result_json = dict(call.result_json) if call.result_json is not None else None
        m.extra_metadata = dict(call.metadata)
        await self._session.flush()
        await self._session.refresh(m)
        return _to_tool_call(m)

    async def get_attempts(self, tool_call_id: UUID) -> list[ExecutionAttempt]:
        stmt = (
            select(ExecutionAttemptModel)
            .where(ExecutionAttemptModel.tool_call_id == sid(tool_call_id))
            .order_by(ExecutionAttemptModel.attempt_number.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_attempt(m) for m in rows]

    async def save_attempt(self, attempt: ExecutionAttempt) -> ExecutionAttempt:
        m = await self._session.get(ExecutionAttemptModel, sid(attempt.id))
        if m is None:
            m = ExecutionAttemptModel(id=sid(attempt.id))
            self._session.add(m)
        m.tool_call_id = sid(attempt.tool_call_id)
        m.payment_id = sid(attempt.payment_id) if attempt.payment_id else None
        m.provider_id = sid(attempt.provider_id)
        m.service_version_id = sid(attempt.service_version_id)
        m.attempt_number = attempt.attempt_number
        m.execution_state = attempt.execution_state.value
        m.request_forwarded_at = attempt.request_forwarded_at
        m.response_received_at = attempt.response_received_at
        m.latency_ms = attempt.latency_ms
        m.http_status_code = attempt.http_status_code
        m.provider_error_code = attempt.provider_error_code
        m.is_retryable = attempt.is_retryable
        await self._session.flush()
        await self._session.refresh(m)
        return _to_attempt(m)


# ---------------------------------------------------------------------------
# Payment repository
# ---------------------------------------------------------------------------


class SqlAlchemyPaymentRepository:
    """Persists quotes, payment intents, payments, and nonce usage."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_quote(self, quote_id: UUID) -> Quote | None:
        m = await self._session.get(QuoteModel, sid(quote_id))
        return _to_quote(m) if m is not None else None

    async def get_quote_by_tool_call(self, tool_call_id: UUID) -> Quote | None:
        """Return the most recent quote issued for a tool call."""
        stmt = (
            select(QuoteModel)
            .where(QuoteModel.tool_call_id == sid(tool_call_id))
            .order_by(QuoteModel.created_at.desc())
        )
        m = (await self._session.execute(stmt)).scalars().first()
        return _to_quote(m) if m is not None else None

    async def save_quote(self, quote: Quote) -> Quote:
        m = await self._session.get(QuoteModel, sid(quote.id))
        if m is None:
            m = QuoteModel(id=sid(quote.id))
            self._session.add(m)
        m.tool_call_id = sid(quote.tool_call_id)
        m.provider_id = sid(quote.provider_id)
        m.service_version_id = sid(quote.service_version_id)
        m.amount_atomic = quote.amount.amount_atomic
        m.currency = quote.amount.currency.value
        m.currency_decimals = quote.amount.decimals
        m.payment_scheme = quote.payment_scheme
        m.chain_id = quote.chain_id
        m.settlement_layer = quote.settlement_layer
        m.recipient_address = quote.recipient_address
        m.request_hash = quote.request_hash
        m.nonce = quote.nonce
        m.quote_signature = quote.quote_signature
        m.expires_at = quote.expires_at
        await self._session.flush()
        await self._session.refresh(m)
        return _to_quote(m)

    async def get_intent(self, intent_id: UUID) -> PaymentIntent | None:
        m = await self._session.get(PaymentIntentModel, sid(intent_id))
        return _to_intent(m) if m is not None else None

    async def save_intent(self, intent: PaymentIntent) -> PaymentIntent:
        m = await self._session.get(PaymentIntentModel, sid(intent.id))
        if m is None:
            m = PaymentIntentModel(id=sid(intent.id))
            self._session.add(m)
        m.tool_call_id = sid(intent.tool_call_id)
        m.quote_id = sid(intent.quote_id)
        m.agent_id = sid(intent.agent_id)
        m.provider_id = sid(intent.provider_id)
        m.amount_atomic = intent.amount.amount_atomic
        m.currency = intent.amount.currency.value
        m.currency_decimals = intent.amount.decimals
        m.state = intent.state.value
        await self._session.flush()
        await self._session.refresh(m)
        return _to_intent(m)

    async def get(self, payment_id: UUID) -> Payment | None:
        m = await self._session.get(PaymentModel, sid(payment_id))
        return _to_payment(m) if m is not None else None

    async def get_by_tool_call(self, tool_call_id: UUID) -> Payment | None:
        stmt = (
            select(PaymentModel)
            .where(PaymentModel.tool_call_id == sid(tool_call_id))
            .order_by(PaymentModel.created_at.desc())
        )
        m = (await self._session.execute(stmt)).scalars().first()
        return _to_payment(m) if m is not None else None

    async def save(self, payment: Payment) -> Payment:
        m = await self._session.get(PaymentModel, sid(payment.id))
        if m is None:
            m = PaymentModel(id=sid(payment.id))
            self._session.add(m)
        m.intent_id = sid(payment.intent_id)
        m.tool_call_id = sid(payment.tool_call_id)
        m.quote_id = sid(payment.quote_id)
        m.agent_id = sid(payment.agent_id)
        m.provider_id = sid(payment.provider_id)
        m.amount_atomic = payment.amount.amount_atomic
        m.currency = payment.amount.currency.value
        m.currency_decimals = payment.amount.decimals
        m.state = payment.state.value
        m.proof = payment.proof
        m.layerx_transaction_hash = payment.layerx_transaction_hash
        m.layerx_batch_id = payment.layerx_batch_id
        m.l1_settlement_id = payment.l1_settlement_id
        m.verified_at = payment.verified_at
        m.settled_at = payment.settled_at
        m.anchored_at = payment.anchored_at
        await self._session.flush()
        await self._session.refresh(m)
        return _to_payment(m)

    async def consume_nonce(
        self,
        quote_id: UUID,
        nonce: str,
        agent_id: UUID,
    ) -> bool:
        """Atomically claim a quote nonce and serialize budget conversion."""
        owner_stmt = (
            select(ToolCallModel.agent_id)
            .join(QuoteModel, QuoteModel.tool_call_id == ToolCallModel.id)
            .where(QuoteModel.id == sid(quote_id), QuoteModel.nonce == nonce)
        )
        quote_owner = (await self._session.execute(owner_stmt)).scalar_one_or_none()
        if quote_owner != sid(agent_id):
            return False

        lock_stmt = (
            select(AgentModel.id)
            .where(AgentModel.id == sid(agent_id))
            .with_for_update()
        )
        if (await self._session.execute(lock_stmt)).scalar_one_or_none() is None:
            return False

        stmt = (
            update(QuoteModel)
            .where(
                QuoteModel.id == sid(quote_id),
                QuoteModel.nonce == nonce,
                QuoteModel.is_used.is_(False),
            )
            .values(is_used=True)
            .returning(QuoteModel.id)
        )
        result = await self._session.execute(stmt)
        consumed = result.scalar_one_or_none() is not None
        if not consumed:
            return False

        reservation_stmt = (
            update(BudgetReservationModel)
            .where(
                BudgetReservationModel.quote_id == sid(quote_id),
                BudgetReservationModel.status == "active",
            )
            .values(status="consumed", consumed_at=datetime.utcnow())
        )
        await self._session.execute(reservation_stmt)
        return True
