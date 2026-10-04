"""Read transaction history through the Python SDK."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from paxrelay.models import ExecutionAttempt, Transaction

if TYPE_CHECKING:
    from paxrelay.client import AsyncPaxRelayClient


class TransactionsResource:
    """Read tenant-scoped transaction summaries from the API."""

    def __init__(self, client: AsyncPaxRelayClient) -> None:
        self._client = client

    async def list(
        self,
        *,
        agent_id: UUID | str | None = None,
        request_state: str | None = None,
        payment_state: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Transaction]:
        """List transaction summaries with optional filters and pagination.

        Datetimes are serialized as ISO 8601 strings. Prefer timezone-aware
        values so the API can interpret the requested range consistently.
        """
        params: dict[str, object] = {
            "request_state": request_state,
            "payment_state": payment_state,
            "created_after": created_after.isoformat() if created_after else None,
            "created_before": created_before.isoformat() if created_before else None,
            "limit": limit,
            "offset": offset,
        }
        if agent_id is not None:
            params["agent_id"] = self._client._path_id(agent_id)
        params = {key: value for key, value in params.items() if value is not None}

        result = await self._client._request("GET", "transactions", params=params)
        return [Transaction.model_validate(item) for item in result]

    async def execution_attempts(
        self,
        tool_call_id: UUID | str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ExecutionAttempt]:
        """List provider attempt metadata for a tenant-owned transaction.

        If an attempt is ``unknown``, check the provider's records before
        deciding whether to retry the action.
        """
        call_id = self._client._path_id(tool_call_id)
        result = await self._client._request(
            "GET",
            f"transactions/{call_id}/execution-attempts",
            params={"limit": limit, "offset": offset},
        )
        return [ExecutionAttempt.model_validate(item) for item in result]
