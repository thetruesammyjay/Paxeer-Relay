"""LayerX transaction and batch query helpers."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx

from paxrelay_paxeer.errors import AdapterResponseError, AdapterUnavailableError


class LayerXClient:
    """HTTP client for LayerX transaction lookups.

    Reads LAYERX_API_URL from settings at construction time.
    """

    def __init__(self, api_url: str, timeout: float = 10.0) -> None:
        self._api_url = api_url.rstrip("/")
        self._timeout = timeout

    async def get_transaction(self, tx_hash: str) -> dict[str, Any] | None:
        # Transaction hashes are fixed-width EVM hashes. Validate before
        # placing the value in a URL path, and encode it even after validation.
        if not isinstance(tx_hash, str) or re.fullmatch(r"0x[0-9a-fA-F]{64}", tx_hash) is None:
            return None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(
                    f"{self._api_url}/transactions/{quote(tx_hash, safe='')}"
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                payload = resp.json()
                if not isinstance(payload, dict):
                    raise AdapterResponseError("LayerX transaction response must be an object")
                return payload
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 or exc.response.status_code >= 500:
                    raise AdapterUnavailableError("LayerX transaction read is unavailable") from exc
                raise AdapterResponseError("LayerX rejected the transaction read") from exc
            except httpx.HTTPError as exc:
                raise AdapterUnavailableError("LayerX transaction read is unavailable") from exc
            except ValueError as exc:
                raise AdapterResponseError("LayerX transaction response is not valid JSON") from exc

    async def get_batch(self, batch_id: str) -> dict[str, Any] | None:
        if not isinstance(batch_id, str) or not batch_id or len(batch_id) > 256:
            return None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(
                    f"{self._api_url}/batches/{quote(batch_id, safe='')}"
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                payload = resp.json()
                if not isinstance(payload, dict):
                    raise AdapterResponseError("LayerX batch response must be an object")
                return payload
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 or exc.response.status_code >= 500:
                    raise AdapterUnavailableError("LayerX batch read is unavailable") from exc
                raise AdapterResponseError("LayerX rejected the batch read") from exc
            except httpx.HTTPError as exc:
                raise AdapterUnavailableError("LayerX batch read is unavailable") from exc
            except ValueError as exc:
                raise AdapterResponseError("LayerX batch response is not valid JSON") from exc

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
        raw_amount = tx.get("amount_atomic")
        if isinstance(raw_amount, bool):
            return False, "amount_mismatch"
        if isinstance(raw_amount, int):
            amount_atomic = int(raw_amount)
        elif isinstance(raw_amount, str) and raw_amount.isdecimal():
            amount_atomic = int(raw_amount)
        else:
            return False, "amount_mismatch"
        if amount_atomic != expected_amount_atomic:
            return False, "amount_mismatch"
        recipient = tx.get("recipient")
        if not isinstance(recipient, str) or recipient.lower() != expected_recipient.lower():
            return False, "recipient_mismatch"
        if tx.get("memo") != expected_quote_id and tx.get("quote_id") != expected_quote_id:
            return False, "quote_id_mismatch"
        return True, ""
