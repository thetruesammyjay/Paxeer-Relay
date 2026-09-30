"""Read-only payment reconciliation against local and external records."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from paxrelay_db import get_engine
from paxrelay_db.models.executions import OutboxEventModel, SettlementRecordModel
from paxrelay_db.models.payments import (
    PaymentIntentModel,
    PaymentModel,
    QuoteModel,
    ToolCallModel,
)
from paxrelay_domain import EventType
from paxrelay_paxeer.errors import AdapterReadError
from paxrelay_paxeer.interfaces import PaymentAdapter, SettlementAdapter
from paxrelay_worker.jobs import BaseJob

_RECONCILABLE_PAYMENT_STATES = ("verified", "settled_layerx", "anchored_l1")
_HASH_RE = re.compile(r"0x[0-9a-fA-F]{64}")
_ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{40}")


@dataclass(frozen=True)
class _PaymentSnapshot:
    record_id: str
    payment_id: str
    source_fingerprint: str
    amount_atomic: int
    currency: str
    quote_id: str
    recipient_address: str
    transaction_hash: str | None
    batch_id: str | None
    l1_settlement_id: str | None


@dataclass(frozen=True)
class _ExternalResult:
    status: str
    mismatch_details: dict[str, Any] | None = None
    layerx_transaction_hash: str | None = None
    layerx_batch_id: str | None = None
    l1_settlement_id: str | None = None
    l1_block_number: int | None = None
    l1_transaction_hash: str | None = None
    l1_commitment_hash: str | None = None
    last_error: str | None = None


def _identifier(value: object | None) -> str | None:
    return str(value).lower() if value is not None else None


def _valid_external_reference(value: object, maximum_length: int = 66) -> bool:
    return (
        isinstance(value, str)
        and 0 < len(value) <= maximum_length
        and value.strip() == value
        and value.isprintable()
    )


def _same_external_reference(left: str, right: str) -> bool:
    if _HASH_RE.fullmatch(left) and _HASH_RE.fullmatch(right):
        return left.lower() == right.lower()
    return left == right


def _record_mismatch(
    issues: list[dict[str, Any]],
    code: str,
    expected: object,
    actual: object,
) -> None:
    if expected != actual:
        issues.append({"code": code, "expected": expected, "actual": actual})


def _internal_fingerprint(
    payment: PaymentModel,
    intent: PaymentIntentModel | None,
    quote: QuoteModel | None,
    tool_call: ToolCallModel | None,
    expected_chain_id: int,
) -> str:
    """Hash only local facts that can change a reconciliation decision."""

    def timestamp(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    facts = {
        "expected_chain_id": expected_chain_id,
        "payment": {
            "id": _identifier(payment.id),
            "intent_id": _identifier(payment.intent_id),
            "quote_id": _identifier(payment.quote_id),
            "tool_call_id": _identifier(payment.tool_call_id),
            "agent_id": _identifier(payment.agent_id),
            "provider_id": _identifier(payment.provider_id),
            "amount_atomic": str(payment.amount_atomic),
            "currency": payment.currency,
            "currency_decimals": payment.currency_decimals,
            "state": payment.state,
            "verified_at": timestamp(payment.verified_at),
            "settled_at": timestamp(payment.settled_at),
            "anchored_at": timestamp(payment.anchored_at),
            "transaction_hash": payment.layerx_transaction_hash,
            "batch_id": payment.layerx_batch_id,
            "l1_settlement_id": payment.l1_settlement_id,
        },
        "intent": (
            None
            if intent is None
            else {
                "id": _identifier(intent.id),
                "quote_id": _identifier(intent.quote_id),
                "tool_call_id": _identifier(intent.tool_call_id),
                "agent_id": _identifier(intent.agent_id),
                "provider_id": _identifier(intent.provider_id),
                "amount_atomic": str(intent.amount_atomic),
                "currency": intent.currency,
                "currency_decimals": intent.currency_decimals,
            }
        ),
        "quote": (
            None
            if quote is None
            else {
                "id": _identifier(quote.id),
                "tool_call_id": _identifier(quote.tool_call_id),
                "provider_id": _identifier(quote.provider_id),
                "amount_atomic": str(quote.amount_atomic),
                "currency": quote.currency,
                "currency_decimals": quote.currency_decimals,
                "payment_scheme": quote.payment_scheme,
                "chain_id": quote.chain_id,
                "settlement_layer": quote.settlement_layer,
                "request_hash": _identifier(quote.request_hash),
                "recipient_address": quote.recipient_address.lower(),
            }
        ),
        "tool_call": (
            None
            if tool_call is None
            else {
                "id": _identifier(tool_call.id),
                "agent_id": _identifier(tool_call.agent_id),
                "request_hash": _identifier(tool_call.request_hash),
            }
        ),
    }
    encoded = json.dumps(facts, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _internal_mismatches(
    payment: PaymentModel,
    intent: PaymentIntentModel | None,
    quote: QuoteModel | None,
    tool_call: ToolCallModel | None,
    expected_chain_id: int,
) -> list[dict[str, Any]]:
    """Compare the payment facts recorded by adjacent local rows."""
    issues: list[dict[str, Any]] = []
    if intent is None:
        issues.append({"code": "payment_intent_missing"})
    else:
        for field, expected, actual in (
            ("intent_quote_id_mismatch", _identifier(payment.quote_id), _identifier(intent.quote_id)),
            ("intent_tool_call_mismatch", _identifier(payment.tool_call_id), _identifier(intent.tool_call_id)),
            ("intent_agent_mismatch", _identifier(payment.agent_id), _identifier(intent.agent_id)),
            ("intent_provider_mismatch", _identifier(payment.provider_id), _identifier(intent.provider_id)),
            ("intent_amount_mismatch", int(payment.amount_atomic), int(intent.amount_atomic)),
            ("intent_currency_mismatch", payment.currency, intent.currency),
            ("intent_currency_decimals_mismatch", payment.currency_decimals, intent.currency_decimals),
        ):
            _record_mismatch(issues, field, expected, actual)

    if quote is None:
        issues.append({"code": "quote_missing"})
    else:
        for field, expected, actual in (
            ("quote_tool_call_mismatch", _identifier(payment.tool_call_id), _identifier(quote.tool_call_id)),
            ("quote_provider_mismatch", _identifier(payment.provider_id), _identifier(quote.provider_id)),
            ("quote_amount_mismatch", int(payment.amount_atomic), int(quote.amount_atomic)),
            ("quote_currency_mismatch", payment.currency, quote.currency),
            ("quote_currency_decimals_mismatch", payment.currency_decimals, quote.currency_decimals),
        ):
            _record_mismatch(issues, field, expected, actual)
        for field, expected, actual in (
            ("quote_payment_scheme_mismatch", "402LXP", quote.payment_scheme),
            ("quote_chain_id_mismatch", expected_chain_id, quote.chain_id),
            ("quote_settlement_layer_mismatch", "layerx", quote.settlement_layer),
        ):
            _record_mismatch(issues, field, expected, actual)
        if _HASH_RE.fullmatch(quote.request_hash) is None:
            issues.append({"code": "quote_request_hash_invalid"})
        if _ADDRESS_RE.fullmatch(quote.recipient_address) is None:
            issues.append({"code": "quote_recipient_invalid"})

    if tool_call is None:
        issues.append({"code": "tool_call_missing"})
    else:
        _record_mismatch(
            issues,
            "payment_agent_mismatch",
            _identifier(payment.agent_id),
            _identifier(tool_call.agent_id),
        )
        if quote is not None:
            if tool_call.request_hash is None:
                issues.append({"code": "tool_call_request_hash_missing"})
            else:
                _record_mismatch(
                    issues,
                    "quote_request_hash_mismatch",
                    _identifier(tool_call.request_hash),
                    _identifier(quote.request_hash),
                )

    if payment.verified_at is None:
        issues.append({"code": "verified_timestamp_missing"})
    if payment.state in _RECONCILABLE_PAYMENT_STATES and not payment.layerx_transaction_hash:
        issues.append({"code": "layerx_transaction_reference_missing"})
    elif payment.layerx_transaction_hash and _HASH_RE.fullmatch(payment.layerx_transaction_hash) is None:
        issues.append({"code": "layerx_transaction_reference_invalid"})
    if payment.layerx_batch_id is not None and not _valid_external_reference(payment.layerx_batch_id):
        issues.append({"code": "layerx_batch_reference_invalid"})
    if payment.l1_settlement_id is not None and not _valid_external_reference(
        payment.l1_settlement_id
    ):
        issues.append({"code": "l1_settlement_reference_invalid"})
    if payment.state in {"settled_layerx", "anchored_l1"} and payment.settled_at is None:
        issues.append({"code": "layerx_settlement_timestamp_missing"})
    if payment.state == "anchored_l1":
        if payment.anchored_at is None:
            issues.append({"code": "l1_anchor_timestamp_missing"})
        if payment.l1_settlement_id is None:
            issues.append({"code": "l1_settlement_reference_missing"})
    return issues


def _first_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _parse_amount(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return None


def _mismatch(
    code: str,
    expected: str | int | None = None,
    actual: str | int | None = None,
) -> _ExternalResult:
    issue: dict[str, Any] = {"code": code}
    if expected is not None or actual is not None:
        issue["expected"] = expected[:256] if isinstance(expected, str) else expected
        issue["actual"] = actual[:256] if isinstance(actual, str) else actual
    return _ExternalResult(
        status="mismatch",
        mismatch_details={"issues": [issue]},
    )


def _pending(status: str = "awaiting_external", error: str = "evidence_pending") -> _ExternalResult:
    return _ExternalResult(status=status, last_error=error)


def _batch_contains_transaction(transactions: Any, tx_hash: str) -> bool | None:
    """Return None when a batch has no usable transaction list."""
    if not isinstance(transactions, list) or not transactions:
        return None
    for item in transactions:
        candidate = item if isinstance(item, str) else (
            _first_value(item, "transaction_hash", "tx_hash", "hash")
            if isinstance(item, dict)
            else None
        )
        if isinstance(candidate, str) and candidate.lower() == tx_hash.lower():
            return True
    return False


class ReconciliationJob(BaseJob):
    """Compare stored payments with adapter evidence without changing payments."""

    def __init__(
        self,
        settings: Any,
        payment_adapter: PaymentAdapter,
        settlement_adapter: SettlementAdapter,
    ) -> None:
        super().__init__(settings)
        self.payment_adapter = payment_adapter
        self.settlement_adapter = settlement_adapter
        self.batch_size = settings.reconciliation_batch_size
        self.concurrency = settings.reconciliation_concurrency
        self.claim_lease_seconds = settings.reconciliation_claim_lease_seconds

    @property
    def interval_seconds(self) -> int:
        return self.settings.settlement_poll_interval_seconds

    async def tick(self) -> None:
        await self._check_internal_consistency()
        await self._check_external_evidence()

    async def _check_internal_consistency(self) -> None:
        session_factory = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, autoflush=False
        )
        now = datetime.now(UTC).replace(tzinfo=None)
        async with session_factory() as session:
            statement = (
                select(
                    PaymentModel,
                    PaymentIntentModel,
                    QuoteModel,
                    ToolCallModel,
                    SettlementRecordModel,
                )
                .outerjoin(PaymentIntentModel, PaymentIntentModel.id == PaymentModel.intent_id)
                .outerjoin(QuoteModel, QuoteModel.id == PaymentModel.quote_id)
                .outerjoin(ToolCallModel, ToolCallModel.id == PaymentModel.tool_call_id)
                .outerjoin(SettlementRecordModel, SettlementRecordModel.payment_id == PaymentModel.id)
                .where(
                    PaymentModel.state.in_(_RECONCILABLE_PAYMENT_STATES),
                    or_(
                        SettlementRecordModel.id.is_(None),
                        SettlementRecordModel.internal_checked_at.is_(None),
                        SettlementRecordModel.internal_fingerprint.is_(None),
                        PaymentModel.updated_at > SettlementRecordModel.updated_at,
                        PaymentIntentModel.updated_at > SettlementRecordModel.updated_at,
                        QuoteModel.updated_at > SettlementRecordModel.updated_at,
                        ToolCallModel.updated_at > SettlementRecordModel.updated_at,
                    ),
                )
                .order_by(PaymentModel.updated_at.asc(), PaymentModel.id.asc())
                .limit(self.batch_size)
                .with_for_update(skip_locked=True, of=PaymentModel)
            )
            rows = (await session.execute(statement)).all()
            mismatch_count = 0
            outbox_count = 0
            unscoped_mismatch_count = 0

            for payment, intent, quote, tool_call, record in rows:
                issues = _internal_mismatches(
                    payment,
                    intent,
                    quote,
                    tool_call,
                    self.settings.paxeer_chain_id,
                )
                details = {"issues": issues} if issues else None
                old_status = record.reconciliation_status if record is not None else None
                old_details = record.mismatch_details if record is not None else None
                fingerprint = _internal_fingerprint(
                    payment,
                    intent,
                    quote,
                    tool_call,
                    self.settings.paxeer_chain_id,
                )
                source_changed = (
                    record is None
                    or record.internal_fingerprint != fingerprint
                )

                if record is None:
                    record = SettlementRecordModel(
                        id=str(uuid4()),
                        payment_id=payment.id,
                        reconciliation_status="awaiting_external",
                    )
                    session.add(record)

                record.layerx_transaction_hash = payment.layerx_transaction_hash
                record.layerx_batch_id = payment.layerx_batch_id
                record.reconciliation_status = (
                    "mismatch"
                    if issues
                    else "awaiting_external"
                    if source_changed or old_status in {None, "pending"}
                    else old_status
                )
                record.mismatch_details = (
                    details
                    if issues or source_changed or old_status != "mismatch"
                    else old_details
                )
                record.internal_checked_at = now
                record.internal_fingerprint = fingerprint
                if source_changed:
                    record.next_attempt_at = None
                    record.last_error = None
                    record.l1_settlement_id = payment.l1_settlement_id
                    record.l1_block_number = None
                    record.l1_transaction_hash = None
                    record.l1_commitment_hash = None
                    record.reconciled_at = None
                    record.claimed_at = None
                    record.claim_token = None

                if issues:
                    mismatch_count += 1
                    if tool_call is None:
                        unscoped_mismatch_count += 1
                        self.log.error(
                            "Payment %s has local reconciliation issues but no tenant-owned tool call",
                            payment.id,
                        )
                    if old_status != "mismatch" or old_details != details:
                        if tool_call is not None:
                            self._add_mismatch_event(session, now, record, tool_call, issues)
                            outbox_count += 1

            await session.commit()

        if rows:
            self.log.info(
                "Checked %d local payment record(s); found %d mismatch(es), %d without a tenant owner, queued %d event(s)",
                len(rows), mismatch_count, unscoped_mismatch_count, outbox_count,
            )

    async def _check_external_evidence(self) -> None:
        candidates = await self._claim_due_records()
        if not candidates:
            return
        semaphore = asyncio.Semaphore(self.concurrency)

        async def process(snapshot: _PaymentSnapshot, claim_token: str) -> None:
            async with semaphore:
                result = await self._read_external_evidence(snapshot)
                await self._finish_claim(snapshot, claim_token, result)

        results = await asyncio.gather(
            *(process(snapshot, token) for snapshot, token in candidates),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, Exception):
                self.log.error(
                    "A claimed reconciliation record did not finish (%s)",
                    type(result).__name__,
                )

    async def _claim_due_records(self) -> list[tuple[_PaymentSnapshot, str]]:
        session_factory = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, autoflush=False
        )
        now = datetime.now(UTC).replace(tzinfo=None)
        stale_before = now - timedelta(seconds=self.claim_lease_seconds)
        claimed: list[tuple[_PaymentSnapshot, str]] = []
        async with session_factory() as session:
            statement = (
                select(
                    SettlementRecordModel,
                    PaymentModel,
                    PaymentIntentModel,
                    QuoteModel,
                    ToolCallModel,
                )
                .join(PaymentModel, PaymentModel.id == SettlementRecordModel.payment_id)
                .outerjoin(PaymentIntentModel, PaymentIntentModel.id == PaymentModel.intent_id)
                .outerjoin(QuoteModel, QuoteModel.id == PaymentModel.quote_id)
                .outerjoin(ToolCallModel, ToolCallModel.id == PaymentModel.tool_call_id)
                .where(
                    PaymentModel.state.in_(_RECONCILABLE_PAYMENT_STATES),
                    SettlementRecordModel.reconciliation_status.in_(
                        ("awaiting_external", "layerx_confirmed")
                    ),
                    SettlementRecordModel.internal_checked_at.is_not(None),
                    or_(
                        SettlementRecordModel.next_attempt_at.is_(None),
                        SettlementRecordModel.next_attempt_at <= now,
                    ),
                    or_(
                        SettlementRecordModel.claim_token.is_(None),
                        SettlementRecordModel.claimed_at.is_(None),
                        SettlementRecordModel.claimed_at < stale_before,
                    ),
                )
                .order_by(SettlementRecordModel.created_at.asc(), SettlementRecordModel.id.asc())
                .limit(self.batch_size)
                .with_for_update(skip_locked=True, of=SettlementRecordModel)
            )
            rows = (await session.execute(statement)).all()
            for record, payment, intent, quote, tool_call in rows:
                fingerprint = _internal_fingerprint(
                    payment,
                    intent,
                    quote,
                    tool_call,
                    self.settings.paxeer_chain_id,
                )
                issues = _internal_mismatches(
                    payment,
                    intent,
                    quote,
                    tool_call,
                    self.settings.paxeer_chain_id,
                )
                if issues:
                    details = {"issues": issues}
                    old_status = record.reconciliation_status
                    old_details = record.mismatch_details
                    record.reconciliation_status = "mismatch"
                    record.mismatch_details = details
                    record.internal_checked_at = now
                    record.internal_fingerprint = fingerprint
                    record.last_checked_at = now
                    record.last_error = None
                    record.layerx_transaction_hash = payment.layerx_transaction_hash
                    record.layerx_batch_id = payment.layerx_batch_id
                    record.l1_settlement_id = payment.l1_settlement_id
                    record.l1_block_number = None
                    record.l1_transaction_hash = None
                    record.l1_commitment_hash = None
                    record.next_attempt_at = None
                    record.claimed_at = None
                    record.claim_token = None
                    record.reconciled_at = None
                    if old_status != "mismatch" or old_details != details:
                        if tool_call is not None:
                            self._add_mismatch_event(
                                session, now, record, tool_call, issues
                            )
                        else:
                            self.log.error(
                                "Payment %s has local reconciliation issues but no tenant owner",
                                payment.id,
                            )
                    continue
                if record.internal_fingerprint != fingerprint:
                    record.reconciliation_status = "awaiting_external"
                    record.mismatch_details = None
                    record.internal_checked_at = now
                    record.internal_fingerprint = fingerprint
                    record.last_error = None
                    record.layerx_transaction_hash = payment.layerx_transaction_hash
                    record.layerx_batch_id = payment.layerx_batch_id
                    record.l1_settlement_id = payment.l1_settlement_id
                    record.l1_block_number = None
                    record.l1_transaction_hash = None
                    record.l1_commitment_hash = None
                    record.next_attempt_at = None
                    record.claimed_at = None
                    record.claim_token = None
                    record.reconciled_at = None
                    continue
                if intent is None or quote is None or tool_call is None:
                    continue
                claim_token = str(uuid4())
                record.claim_token = claim_token
                record.claimed_at = now
                record.attempt_count += 1
                claimed.append(
                    (
                        _PaymentSnapshot(
                            record_id=record.id,
                            payment_id=payment.id,
                            source_fingerprint=fingerprint,
                            amount_atomic=int(payment.amount_atomic),
                            currency=payment.currency,
                            quote_id=payment.quote_id,
                            recipient_address=quote.recipient_address,
                            transaction_hash=payment.layerx_transaction_hash,
                            batch_id=payment.layerx_batch_id,
                            l1_settlement_id=payment.l1_settlement_id,
                        ),
                        claim_token,
                    )
                )
            await session.commit()
        return claimed

    async def _read_external_evidence(self, snapshot: _PaymentSnapshot) -> _ExternalResult:
        response: dict[str, Any] = {}
        status_error: str | None = None
        if self.settings.use_mock_adapter:
            try:
                payment_status = await self.payment_adapter.get_payment_status(
                    snapshot.payment_id
                )
                if isinstance(payment_status, dict):
                    response.update(payment_status)
                else:
                    status_error = "adapter_invalid_response"
            except AdapterReadError as exc:
                status_error = exc.code
            except Exception as exc:
                self.log.warning(
                    "Payment status read failed for %s (%s)",
                    snapshot.payment_id,
                    type(exc).__name__,
                )
                status_error = "adapter_read_error"

        transaction: dict[str, Any] = {}
        if not self.settings.use_mock_adapter:
            if not snapshot.transaction_hash:
                return _pending(error="transaction_reference_missing")
            try:
                layerx_transaction = await self.payment_adapter.get_layerx_transaction(
                    snapshot.transaction_hash
                )
            except AdapterReadError as exc:
                return _pending(error=exc.code)
            except Exception as exc:
                self.log.warning(
                    "LayerX transaction read failed for %s (%s)",
                    snapshot.payment_id,
                    type(exc).__name__,
                )
                return _pending(error="adapter_read_error")
            if layerx_transaction is None:
                return _pending(error=status_error or "evidence_pending")
            if not isinstance(layerx_transaction, dict):
                return _pending(error="adapter_invalid_response")
            transaction = layerx_transaction

        external_payment_ids = (
            response.get("payment_id"),
            transaction.get("payment_id"),
        )
        mismatched_payment_id = next(
            (
                value for value in external_payment_ids
                if isinstance(value, str)
                and value.lower() != snapshot.payment_id.lower()
            ),
            None,
        )
        if mismatched_payment_id is not None:
            return _mismatch(
                "external_payment_id_mismatch",
                snapshot.payment_id,
                mismatched_payment_id,
            )
        external_settlement_id = _first_value(
            response, "l1_settlement_id", "settlement_id"
        ) or _first_value(transaction, "l1_settlement_id", "settlement_id")
        if external_settlement_id is not None and not _valid_external_reference(
            external_settlement_id
        ):
            return _mismatch("external_settlement_id_invalid")
        if (
            isinstance(external_settlement_id, str)
            and snapshot.l1_settlement_id
            and not _same_external_reference(
                external_settlement_id, snapshot.l1_settlement_id
            )
        ):
            return _mismatch(
                "external_settlement_id_mismatch",
                snapshot.l1_settlement_id,
                external_settlement_id,
            )
        if response.get("layerx_confirmed") is False:
            return _pending()

        tx_hash = _first_value(
            transaction, "layerx_transaction_hash", "transaction_hash", "hash"
        ) or _first_value(response, "layerx_transaction_hash")
        if tx_hash is None and not self.settings.use_mock_adapter:
            # A successful lookup by the stored hash identifies the returned record.
            tx_hash = snapshot.transaction_hash
        batch_id = _first_value(
            transaction, "layerx_batch_id", "batch_id"
        ) or _first_value(response, "layerx_batch_id", "batch_id")
        if batch_id is not None and not _valid_external_reference(batch_id):
            return _mismatch("external_batch_id_invalid")
        amount_value = _first_value(transaction, "amount_atomic")
        recipient = _first_value(transaction, "recipient", "recipient_address")
        quote_id = _first_value(transaction, "quote_id", "memo")
        if self.settings.use_mock_adapter:
            amount_value = response.get("amount_atomic")
            recipient = response.get("recipient")
            quote_id = _first_value(response, "quote_id", "memo")

        if isinstance(tx_hash, str) and snapshot.transaction_hash:
            if tx_hash.lower() != snapshot.transaction_hash.lower():
                return _mismatch(
                    "external_transaction_hash_mismatch",
                    snapshot.transaction_hash,
                    tx_hash,
                )
        if isinstance(batch_id, str) and snapshot.batch_id:
            if not _same_external_reference(batch_id, snapshot.batch_id):
                return _mismatch(
                    "external_batch_id_mismatch", snapshot.batch_id, batch_id
                )
        if quote_id is not None and str(quote_id).lower() != snapshot.quote_id.lower():
            return _mismatch(
                "external_quote_id_mismatch", snapshot.quote_id, str(quote_id)
            )
        external_currency = _first_value(transaction, "currency") or response.get("currency")
        if external_currency is not None:
            if str(external_currency).upper() != snapshot.currency.upper():
                return _mismatch(
                    "external_currency_mismatch", snapshot.currency, str(external_currency)
                )

        if not self.settings.use_mock_adapter:
            if not isinstance(tx_hash, str) or not isinstance(snapshot.transaction_hash, str):
                return _pending()
            if amount_value is None or recipient is None or quote_id is None:
                return _pending()
            amount = _parse_amount(amount_value)
            if amount is None:
                return _mismatch("external_amount_invalid")
            if amount != snapshot.amount_atomic:
                return _mismatch(
                    "external_amount_mismatch", snapshot.amount_atomic, amount
                )
            if not isinstance(recipient, str):
                return _mismatch("external_recipient_invalid")
            if recipient.lower() != snapshot.recipient_address.lower():
                return _mismatch(
                    "external_recipient_mismatch",
                    snapshot.recipient_address,
                    recipient,
                )
            if not isinstance(quote_id, str) or quote_id.lower() != snapshot.quote_id.lower():
                return _mismatch(
                    "external_quote_id_mismatch", snapshot.quote_id, str(quote_id)
                )
            if _HASH_RE.fullmatch(tx_hash) is None:
                return _mismatch("external_transaction_hash_invalid")

        confirmed_hash = tx_hash if isinstance(tx_hash, str) else snapshot.transaction_hash
        confirmed_batch = batch_id if isinstance(batch_id, str) else snapshot.batch_id
        layerx_confirmed = (
            response.get("layerx_confirmed") is True
            if self.settings.use_mock_adapter
            else True
        )
        if not layerx_confirmed:
            return _pending()

        layerx_result = _ExternalResult(
            status="layerx_confirmed",
            layerx_transaction_hash=confirmed_hash,
            layerx_batch_id=confirmed_batch,
            l1_settlement_id=(
                external_settlement_id
                if isinstance(external_settlement_id, str)
                else snapshot.l1_settlement_id
            ),
        )
        # The bundled mock adapter deliberately cannot prove L1 finality.
        if self.settings.use_mock_adapter:
            return layerx_result

        settlement_id = external_settlement_id
        if not isinstance(settlement_id, str):
            settlement_id = snapshot.l1_settlement_id
        if not isinstance(settlement_id, str) or not settlement_id:
            return _ExternalResult(
                status="layerx_confirmed",
                layerx_transaction_hash=confirmed_hash,
                layerx_batch_id=confirmed_batch,
                last_error=status_error or "evidence_pending",
            )
        if snapshot.l1_settlement_id and not _same_external_reference(
            settlement_id, snapshot.l1_settlement_id
        ):
            return _mismatch(
                "external_settlement_id_mismatch",
                snapshot.l1_settlement_id,
                settlement_id,
            )

        external_commitment = _first_value(
            response, "l1_commitment_hash", "commitment_hash"
        ) or _first_value(transaction, "l1_commitment_hash", "commitment_hash")
        if external_commitment is not None and not isinstance(external_commitment, str):
            return _mismatch("external_commitment_hash_invalid")
        if isinstance(external_commitment, str) and _HASH_RE.fullmatch(external_commitment) is None:
            return _mismatch("external_commitment_hash_invalid")
        try:
            settlement = await self.settlement_adapter.read_settlement(settlement_id)
            if settlement is None:
                return layerx_result
            returned_settlement_id = _first_value(settlement, "settlement_id", "id")
            if not isinstance(returned_settlement_id, str):
                return layerx_result
            if not _valid_external_reference(returned_settlement_id):
                return _mismatch("l1_settlement_id_invalid")
            if not _same_external_reference(returned_settlement_id, settlement_id):
                return _mismatch(
                    "l1_settlement_id_mismatch", settlement_id, returned_settlement_id
                )
            if settlement.get("l1_anchored") is not True:
                return layerx_result

            settlement_batch = _first_value(settlement, "batch_id", "layerx_batch_id")
            if not isinstance(settlement_batch, str):
                return layerx_result
            if not _valid_external_reference(settlement_batch):
                return _mismatch("external_batch_id_invalid")
            if confirmed_batch and not _same_external_reference(
                settlement_batch, confirmed_batch
            ):
                return _mismatch("l1_batch_id_mismatch", confirmed_batch, settlement_batch)
            settlement_commitment = _first_value(
                settlement, "l1_commitment_hash", "commitment_hash"
            )
            if not isinstance(settlement_commitment, str):
                return layerx_result
            if _HASH_RE.fullmatch(settlement_commitment) is None:
                return _mismatch("external_commitment_hash_invalid")
            if (
                isinstance(external_commitment, str)
                and settlement_commitment.lower() != external_commitment.lower()
            ):
                return _mismatch(
                    "l1_commitment_hash_mismatch",
                    external_commitment,
                    settlement_commitment,
                )
            commitment_hash = external_commitment or settlement_commitment

            batch = await self.settlement_adapter.read_batch(settlement_batch)
            if batch is None:
                return layerx_result
            returned_batch_id = _first_value(batch, "batch_id", "id")
            if not isinstance(returned_batch_id, str):
                return layerx_result
            if not _valid_external_reference(returned_batch_id):
                return _mismatch("external_batch_id_invalid")
            if not _same_external_reference(returned_batch_id, settlement_batch):
                return _mismatch("l1_batch_id_mismatch", settlement_batch, returned_batch_id)
            batch_commitment = _first_value(batch, "l1_commitment_hash", "commitment_hash")
            if not isinstance(batch_commitment, str):
                return layerx_result
            if batch_commitment.lower() != commitment_hash.lower():
                return _mismatch(
                    "l1_commitment_hash_mismatch", commitment_hash, batch_commitment
                )

            member = _batch_contains_transaction(
                batch.get("transactions"), confirmed_hash or ""
            )
            if member is None:
                return layerx_result
            if not member:
                return _mismatch(
                    "l1_transaction_not_in_batch", confirmed_hash, "not_listed"
                )

            block_number = _parse_amount(
                _first_value(settlement, "l1_block_number", "block_number")
            )
            l1_tx_hash = _first_value(
                settlement, "l1_transaction_hash", "transaction_hash"
            )
            if block_number is None or not isinstance(l1_tx_hash, str):
                return layerx_result
            if block_number < 0:
                return _mismatch("l1_block_number_invalid")
            if _HASH_RE.fullmatch(l1_tx_hash) is None:
                return _mismatch("l1_transaction_hash_invalid")

            commitment_verified = await self.settlement_adapter.verify_l1_commitment(
                l1_tx_hash, commitment_hash, block_number
            )
            if commitment_verified is None:
                return layerx_result
            if not commitment_verified:
                return _mismatch("l1_commitment_verification_failed")

            return _ExternalResult(
                status="reconciled",
                layerx_transaction_hash=confirmed_hash,
                layerx_batch_id=settlement_batch,
                l1_settlement_id=settlement_id,
                l1_block_number=block_number,
                l1_transaction_hash=l1_tx_hash,
                l1_commitment_hash=commitment_hash,
            )
        except AdapterReadError as exc:
            return _ExternalResult(
                status="layerx_confirmed",
                layerx_transaction_hash=confirmed_hash,
                layerx_batch_id=confirmed_batch,
                l1_settlement_id=layerx_result.l1_settlement_id,
                last_error=exc.code,
            )
        except Exception as exc:
            self.log.warning(
                "Settlement evidence read failed for %s (%s)",
                snapshot.payment_id,
                type(exc).__name__,
            )
            return _ExternalResult(
                status="layerx_confirmed",
                layerx_transaction_hash=confirmed_hash,
                layerx_batch_id=confirmed_batch,
                l1_settlement_id=layerx_result.l1_settlement_id,
                last_error="adapter_read_error",
            )

    async def _finish_claim(
        self,
        snapshot: _PaymentSnapshot,
        claim_token: str,
        result: _ExternalResult,
    ) -> None:
        session_factory = async_sessionmaker(
            bind=get_engine(), expire_on_commit=False, autoflush=False
        )
        now = datetime.now(UTC).replace(tzinfo=None)
        async with session_factory() as session:
            statement = (
                select(
                    SettlementRecordModel,
                    PaymentModel,
                    PaymentIntentModel,
                    QuoteModel,
                    ToolCallModel,
                )
                .join(PaymentModel, PaymentModel.id == SettlementRecordModel.payment_id)
                .outerjoin(PaymentIntentModel, PaymentIntentModel.id == PaymentModel.intent_id)
                .outerjoin(QuoteModel, QuoteModel.id == PaymentModel.quote_id)
                .outerjoin(ToolCallModel, ToolCallModel.id == PaymentModel.tool_call_id)
                .where(
                    SettlementRecordModel.id == snapshot.record_id,
                    SettlementRecordModel.claim_token == claim_token,
                )
                .with_for_update(of=SettlementRecordModel)
            )
            row = (await session.execute(statement)).one_or_none()
            if row is None:
                return
            record, payment, intent, quote, tool_call = row
            if record.reconciliation_status == "mismatch":
                record.claimed_at = None
                record.claim_token = None
                record.next_attempt_at = None
                await session.commit()
                return
            current_fingerprint = _internal_fingerprint(
                payment,
                intent,
                quote,
                tool_call,
                self.settings.paxeer_chain_id,
            )
            if current_fingerprint != snapshot.source_fingerprint:
                record.claimed_at = None
                record.claim_token = None
                record.next_attempt_at = None
                record.internal_checked_at = None
                record.last_error = "source_changed"
                record.layerx_transaction_hash = payment.layerx_transaction_hash
                record.layerx_batch_id = payment.layerx_batch_id
                record.l1_settlement_id = payment.l1_settlement_id
                record.l1_block_number = None
                record.l1_transaction_hash = None
                record.l1_commitment_hash = None
                record.reconciled_at = None
                await session.commit()
                return
            old_status = record.reconciliation_status
            old_details = record.mismatch_details
            record.reconciliation_status = result.status
            record.mismatch_details = result.mismatch_details
            record.last_checked_at = now
            record.last_error = result.last_error
            record.claimed_at = None
            record.claim_token = None
            record.next_attempt_at = (
                now + timedelta(seconds=self._retry_delay(record.attempt_count))
                if result.status in {"awaiting_external", "layerx_confirmed"}
                else None
            )
            record.reconciled_at = now if result.status == "reconciled" else None
            if result.layerx_transaction_hash is not None:
                record.layerx_transaction_hash = result.layerx_transaction_hash
            if result.layerx_batch_id is not None:
                record.layerx_batch_id = result.layerx_batch_id
            if result.l1_settlement_id is not None:
                record.l1_settlement_id = result.l1_settlement_id
            if result.l1_block_number is not None:
                record.l1_block_number = result.l1_block_number
            if result.l1_transaction_hash is not None:
                record.l1_transaction_hash = result.l1_transaction_hash
            if result.l1_commitment_hash is not None:
                record.l1_commitment_hash = result.l1_commitment_hash

            if result.status == "mismatch" and (
                old_status != "mismatch" or old_details != result.mismatch_details
            ):
                tool_call = await session.get(ToolCallModel, payment.tool_call_id)
                if tool_call is not None:
                    issue_codes = [
                        item["code"] for item in (result.mismatch_details or {}).get("issues", [])
                    ]
                    self._add_mismatch_event(
                        session, now, record, tool_call,
                        [{"code": code} for code in issue_codes],
                    )
                else:
                    self.log.error(
                        "Payment %s has external reconciliation issues but no tenant owner",
                        payment.id,
                    )
            await session.commit()

    def _retry_delay(self, attempt_count: int) -> int:
        base = self.settings.reconciliation_retry_initial_seconds
        maximum = self.settings.reconciliation_retry_max_seconds
        return min(maximum, base * (2 ** min(max(attempt_count - 1, 0), 12)))

    @staticmethod
    def _add_mismatch_event(
        session: Any,
        now: datetime,
        record: SettlementRecordModel,
        tool_call: ToolCallModel,
        issues: list[dict[str, Any]],
    ) -> None:
        event_id = str(uuid4())
        event_type = EventType.SETTLEMENT_MISMATCH.value
        session.add(
            OutboxEventModel(
                id=event_id,
                organisation_id=tool_call.organisation_id,
                project_id=tool_call.project_id,
                environment=tool_call.environment,
                event_type=event_type,
                payload_json={
                    "event_id": event_id,
                    "event_type": event_type,
                    "occurred_at": f"{now.isoformat()}Z",
                    "organisation_id": tool_call.organisation_id,
                    "project_id": tool_call.project_id,
                    "environment": tool_call.environment,
                    "data": {
                        "payment_id": record.payment_id,
                        "settlement_record_id": record.id,
                        "issue_codes": [issue["code"] for issue in issues],
                    },
                },
                status="pending",
            )
        )
