"""L1 settlement record queries."""

from __future__ import annotations

from typing import Any

import httpx


class SettlementClient:
    """HTTP client for Paxeer L1 settlement record reads."""

    def __init__(self, rpc_url: str, timeout: float = 10.0) -> None:
        self._rpc_url = rpc_url.rstrip("/")
        self._timeout = timeout

    async def read_settlement(self, settlement_id: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(
                    f"{self._rpc_url}/settlement/{settlement_id}"
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError:
                return None

    async def read_batch(self, batch_id: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(f"{self._rpc_url}/batch/{batch_id}")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError:
                return None

    async def verify_l1_commitment(
        self, batch_id: str, commitment_hash: str
    ) -> bool:
        batch = await self.read_batch(batch_id)
        if batch is None:
            return False
        return batch.get("commitment_hash", "").lower() == commitment_hash.lower()
