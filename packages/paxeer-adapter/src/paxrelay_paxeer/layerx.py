"""LayerX transaction and batch query helpers."""

from __future__ import annotations

from typing import Any

import httpx


class LayerXClient:
    """HTTP client for LayerX transaction lookups.

    Reads LAYERX_API_URL from settings at construction time.
    """

    def __init__(self, api_url: str, timeout: float = 10.0) -> None:
        self._api_url = api_url.rstrip("/")
        self._timeout = timeout

    async def get_transaction(self, tx_hash: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(f"{self._api_url}/transactions/{tx_hash}")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError:
                return None

    async def get_batch(self, batch_id: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(f"{self._api_url}/batches/{batch_id}")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError:
                return None

    async def verify_transaction_matches_quote(
        self,
        tx_hash: str,
        expected_amount_atomic: int,
        expected_recipient: str,
        expected_quote_id: str,
    ) -> tuple[bool, str]:
        tx = await self.get_transaction(tx_hash)
        if tx is None:
            return False, "transaction_not_found"
        if int(tx.get("amount_atomic", -1)) != expected_amount_atomic:
            return False, "amount_mismatch"
        if tx.get("recipient", "").lower() != expected_recipient.lower():
            return False, "recipient_mismatch"
        if tx.get("memo") != expected_quote_id and tx.get("quote_id") != expected_quote_id:
            return False, "quote_id_mismatch"
        return True, ""
