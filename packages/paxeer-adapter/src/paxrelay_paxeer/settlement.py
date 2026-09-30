"""Read settlement records and verify L1 commitment receipts."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx

from paxrelay_paxeer.errors import (
    AdapterConfigurationError,
    AdapterResponseError,
    AdapterUnavailableError,
)

_HASH_RE = re.compile(r"0x[0-9a-fA-F]{64}")
_ADDRESS_RE = re.compile(r"0x[0-9a-fA-F]{40}")


class SettlementClient:
    """Read the settlement index and verify commitment events through JSON-RPC."""

    def __init__(
        self,
        api_url: str | None,
        *,
        rpc_url: str,
        chain_id: int,
        l1_settlement_contract_address: str | None,
        l1_commitment_event_topic: str | None,
        l1_confirmation_blocks: int | None,
        timeout: float = 10.0,
    ) -> None:
        self._api_url = api_url.rstrip("/") if api_url else None
        self._rpc_url = rpc_url
        self._chain_id = chain_id
        self._contract_address = l1_settlement_contract_address
        self._event_topic = l1_commitment_event_topic
        self._confirmation_blocks = l1_confirmation_blocks
        self._timeout = timeout

    def _require_api_url(self) -> str:
        if self._api_url is None:
            raise AdapterResponseError("Paxeer settlement API URL is not configured")
        return self._api_url

    async def read_settlement(self, settlement_id: str) -> dict[str, Any] | None:
        api_url = self._require_api_url()
        if not isinstance(settlement_id, str) or not settlement_id or len(settlement_id) > 256:
            return None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(
                    f"{api_url}/settlement/{quote(settlement_id, safe='')}"
                )
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                payload = resp.json()
                if not isinstance(payload, dict):
                    raise AdapterResponseError("Settlement response must be an object")
                return payload
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 or exc.response.status_code >= 500:
                    raise AdapterUnavailableError("Paxeer settlement read is unavailable") from exc
                raise AdapterResponseError("Paxeer rejected the settlement read") from exc
            except httpx.HTTPError as exc:
                raise AdapterUnavailableError("Paxeer settlement read is unavailable") from exc
            except ValueError as exc:
                raise AdapterResponseError("Paxeer settlement response is not valid JSON") from exc

    async def _rpc(self, client: httpx.AsyncClient, method: str, params: list[Any]) -> Any:
        try:
            response = await client.post(
                self._rpc_url,
                json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429 or exc.response.status_code >= 500:
                raise AdapterUnavailableError("Paxeer JSON-RPC is unavailable") from exc
            raise AdapterResponseError("Paxeer JSON-RPC rejected the request") from exc
        except httpx.HTTPError as exc:
            raise AdapterUnavailableError("Paxeer JSON-RPC is unavailable") from exc
        except ValueError as exc:
            raise AdapterResponseError("Paxeer JSON-RPC response is not valid JSON") from exc

        if not isinstance(payload, dict) or payload.get("id") != 1:
            raise AdapterResponseError("Paxeer JSON-RPC response has an invalid envelope")
        if payload.get("error") is not None:
            raise AdapterUnavailableError("Paxeer JSON-RPC could not provide receipt evidence")
        if "result" not in payload:
            raise AdapterResponseError("Paxeer JSON-RPC response has no result")
        return payload["result"]

    @staticmethod
    def _quantity(value: Any) -> int | None:
        if not isinstance(value, str) or not value.startswith("0x"):
            return None
        try:
            return int(value[2:] or "0", 16)
        except ValueError:
            return None

    def _has_commitment_event(self, logs: Any, commitment_hash: str) -> bool:
        if not isinstance(logs, list):
            return False
        expected_contract = (self._contract_address or "").lower()
        expected_topic = (self._event_topic or "").lower()
        expected_word = commitment_hash[2:].lower()
        for log in logs:
            if not isinstance(log, dict):
                continue
            if str(log.get("address", "")).lower() != expected_contract:
                continue
            topics = log.get("topics")
            if not isinstance(topics, list) or not topics:
                continue
            if not isinstance(topics[0], str) or topics[0].lower() != expected_topic:
                continue
            if any(
                isinstance(topic, str) and topic[2:].lower() == expected_word
                for topic in topics[1:]
            ):
                return True
            data = log.get("data")
            if isinstance(data, str) and data.startswith("0x"):
                encoded = data[2:].lower()
                if len(encoded) % 64 == 0 and any(
                    encoded[offset:offset + 64] == expected_word
                    for offset in range(0, len(encoded), 64)
                ):
                    return True
        return False

    async def verify_l1_commitment(
        self,
        transaction_hash: str,
        commitment_hash: str,
        expected_block_number: int,
    ) -> bool | None:
        """Check a canonical, sufficiently confirmed receipt for the exact event.

        ``None`` means the receipt is not available or has not reached the
        configured confirmation depth. ``False`` means the available chain
        evidence contradicts the settlement record.
        """
        if not self._contract_address or not self._event_topic or not self._confirmation_blocks:
            raise AdapterConfigurationError("L1 commitment verification is not configured")
        if _ADDRESS_RE.fullmatch(self._contract_address) is None:
            raise AdapterResponseError("L1 settlement contract address is invalid")
        if _HASH_RE.fullmatch(self._event_topic) is None:
            raise AdapterResponseError("L1 commitment event topic is invalid")
        if _HASH_RE.fullmatch(transaction_hash) is None or _HASH_RE.fullmatch(commitment_hash) is None:
            return False
        if expected_block_number < 0:
            return False

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            rpc_chain_id = self._quantity(await self._rpc(client, "eth_chainId", []))
            if rpc_chain_id is None:
                raise AdapterResponseError("Paxeer JSON-RPC returned an invalid chain ID")
            if rpc_chain_id != self._chain_id:
                raise AdapterResponseError("Paxeer JSON-RPC chain ID does not match configuration")

            receipt = await self._rpc(
                client, "eth_getTransactionReceipt", [transaction_hash]
            )
            if receipt is None:
                return None
            if not isinstance(receipt, dict):
                raise AdapterResponseError("Paxeer transaction receipt is malformed")
            receipt_hash = receipt.get("transactionHash")
            receipt_block = self._quantity(receipt.get("blockNumber"))
            receipt_status = self._quantity(receipt.get("status"))
            receipt_block_hash = receipt.get("blockHash")
            if (
                not isinstance(receipt_hash, str)
                or _HASH_RE.fullmatch(receipt_hash) is None
                or receipt_block is None
                or not isinstance(receipt_block_hash, str)
                or _HASH_RE.fullmatch(receipt_block_hash) is None
                or receipt_status is None
            ):
                raise AdapterResponseError("Paxeer transaction receipt is incomplete")
            if receipt_hash.lower() != transaction_hash.lower():
                return False
            if receipt_block != expected_block_number or receipt_status != 1:
                return False

            canonical_block = await self._rpc(
                client,
                "eth_getBlockByNumber",
                [hex(receipt_block), False],
            )
            if canonical_block is None:
                return None
            if not isinstance(canonical_block, dict):
                raise AdapterResponseError("Paxeer canonical block response is malformed")
            canonical_hash = canonical_block.get("hash")
            if not isinstance(canonical_hash, str) or _HASH_RE.fullmatch(canonical_hash) is None:
                raise AdapterResponseError("Paxeer canonical block hash is invalid")
            if canonical_hash.lower() != receipt_block_hash.lower():
                return False

            latest_block = self._quantity(await self._rpc(client, "eth_blockNumber", []))
            if latest_block is None:
                raise AdapterResponseError("Paxeer JSON-RPC returned an invalid block number")
            if latest_block - receipt_block + 1 < self._confirmation_blocks:
                return None

            return self._has_commitment_event(receipt.get("logs"), commitment_hash)
