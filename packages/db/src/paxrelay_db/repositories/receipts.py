"""SQLAlchemy implementation of ReceiptRepository.

The full signed receipt is stored as ``receipt_json`` (the domain model dumped
to JSON), with hash/signature columns duplicated for indexed lookups.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_domain import ExecutionReceipt
from paxrelay_db.models.executions import ExecutionReceiptModel
from paxrelay_db.repositories._common import sid


def _to_receipt(m: ExecutionReceiptModel) -> ExecutionReceipt:
    return ExecutionReceipt.model_validate(m.receipt_json)


class SqlAlchemyReceiptRepository:
    """Persists signed execution receipts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, receipt_id: UUID) -> ExecutionReceipt | None:
        m = await self._session.get(ExecutionReceiptModel, sid(receipt_id))
        return _to_receipt(m) if m is not None else None

    async def get_by_tool_call(self, tool_call_id: UUID) -> ExecutionReceipt | None:
        stmt = select(ExecutionReceiptModel).where(
            ExecutionReceiptModel.tool_call_id == sid(tool_call_id)
        )
        m = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_receipt(m) if m is not None else None

    async def save(self, receipt: ExecutionReceipt) -> ExecutionReceipt:
        m = await self._session.get(ExecutionReceiptModel, sid(receipt.id))
        if m is None:
            m = ExecutionReceiptModel(id=sid(receipt.id))
            self._session.add(m)
        m.version = receipt.version
        m.tool_call_id = sid(receipt.tool_call_id)
        m.agent_id = sid(receipt.agent_id)
        m.provider_id = sid(receipt.provider_id)
        m.service_id = sid(receipt.service_id)
        m.service_version = receipt.service_version
        m.capability = receipt.capability
        m.request_hash = receipt.request_hash
        m.response_hash = receipt.response_hash
        m.receipt_json = receipt.model_dump(mode="json")
        m.receipt_hash = receipt.receipt_hash
        m.signature = receipt.signature
        m.signing_key_id = receipt.signing_key_id
        m.issued_at = receipt.issued_at
        await self._session.flush()
        await self._session.refresh(m)
        return _to_receipt(m)
