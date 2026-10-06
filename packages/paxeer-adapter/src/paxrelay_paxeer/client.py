"""Paxeer adapter surfaces and legacy quote support.

The live payment verifier is intentionally disabled until PaxRelay integrates
the official LayerX SDK and its receipt verification contract.
"""

from __future__ import annotations

from typing import Any

import httpx

from paxrelay_paxeer.errors import AdapterConfigurationError
from paxrelay_paxeer.layerx import LayerXClient
from paxrelay_paxeer.settlement import SettlementClient

class OfficialPaxeerAdapter:
    """Partial live adapter; payment verification is not contract-qualified.

    Reads all network config from constructor arguments (injected from
    pydantic-settings at startup). The quote shape retained here is PaxRelay's
    legacy internal challenge format. It is not the published 402LXP HTTP v2
    PAYMENT-REQUIRED envelope.
    """

    def __init__(
        self,
        rpc_url: str,
        layerx_api_url: str,
        chain_id: int = 125,
        timeout: float = 15.0,
        settlement_api_url: str | None = None,
        l1_settlement_contract_address: str | None = None,
        l1_commitment_event_topic: str | None = None,
        l1_confirmation_blocks: int | None = None,
    ) -> None:
        self._rpc_url = rpc_url
        self._chain_id = chain_id
        self._timeout = timeout
        self._layerx = LayerXClient(layerx_api_url, timeout=timeout)
        self._settlement = SettlementClient(
            settlement_api_url,
            rpc_url=rpc_url,
            chain_id=chain_id,
            l1_settlement_contract_address=l1_settlement_contract_address,
            l1_commitment_event_topic=l1_commitment_event_topic,
            l1_confirmation_blocks=l1_confirmation_blocks,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # WalletAdapter
    # ------------------------------------------------------------------

    async def get_wallet(self, address: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(f"{self._rpc_url}/wallets/{address}")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError:
                return None

    async def read_policy(self, address: str) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(f"{self._rpc_url}/wallets/{address}/policy")
                if resp.status_code == 404:
                    return None
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError:
                return None

    async def verify_session(self, session_proof: str) -> bool:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.post(
                    f"{self._rpc_url}/sessions/verify",
                    json={"proof": session_proof},
                )
                return resp.status_code == 200 and resp.json().get("valid", False)
            except httpx.HTTPError:
                return False

    async def get_balance(self, address: str, currency: str) -> int:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(
                    f"{self._rpc_url}/wallets/{address}/balance",
                    params={"currency": currency},
                )
                resp.raise_for_status()
                return int(resp.json().get("balance_atomic", 0))
            except httpx.HTTPError:
                return 0

    # ------------------------------------------------------------------
    # PaymentAdapter
    # ------------------------------------------------------------------

    async def create_payment_requirement(
        self, quote: dict[str, Any]
    ) -> dict[str, Any]:
        # Payment requirements are built locally from quote data
        # No external call needed — the requirement IS the quote fields
        if quote.get("chain_id") != self._chain_id:
            raise ValueError("quote chain ID does not match the configured adapter")
        return {
            "version": "1",
            "payment_scheme": "402LXP",
            "network": "paxeer",
            "chain_id": quote["chain_id"],
            "settlement_layer": "layerx",
            "currency": quote["currency"],
            "currency_decimals": quote["currency_decimals"],
            "amount_atomic": str(quote["amount_atomic"]),
            "recipient": quote["recipient_address"],
            "quote_id": quote["quote_id"],
            "request_hash": quote["request_hash"],
            "expires_at": quote["expires_at"],
            "nonce": quote["nonce"],
        }

    async def verify_payment(
        self, proof: str, quote: dict[str, Any]
    ) -> dict[str, Any]:
        """Fail closed until the official receipt verifier is integrated.

        The previous prototype accepted fields returned by an undocumented
        REST path. Those fields are not cryptographic payment evidence under
        the published 402LXP v2 contract.
        """
        del proof, quote
        raise AdapterConfigurationError(
            "layerx_402lxp_v2_verifier_not_integrated"
        )

    async def get_payment_status(self, payment_id: str) -> dict[str, Any]:
        """Return unknown until a verified payment-ID status route is configured.

        Settlement IDs and local payment IDs are different identifiers. The
        reconciler uses the stored LayerX transaction hash for live evidence.
        """
        return {"payment_id": payment_id, "state": "unknown"}

    async def get_layerx_transaction(
        self, transaction_hash: str
    ) -> dict[str, Any] | None:
        """Read one LayerX transaction for post-payment reconciliation."""
        return await self._layerx.get_transaction(transaction_hash)

    # ------------------------------------------------------------------
    # RegistryAdapter
    # ------------------------------------------------------------------

    async def publish_service(self, service: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(f"{self._rpc_url}/registry/services", json=service)
            resp.raise_for_status()
            return resp.json()

    async def find_services(self, capability: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(
                    f"{self._rpc_url}/registry/services",
                    params={"capability": capability},
                )
                resp.raise_for_status()
                return resp.json().get("services", [])
            except httpx.HTTPError:
                return []

    async def read_provider_history(self, provider_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            try:
                resp = await client.get(f"{self._rpc_url}/registry/providers/{provider_id}/history")
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPError:
                return {"provider_id": provider_id, "error": "unavailable"}

    # ------------------------------------------------------------------
    # SettlementAdapter
    # ------------------------------------------------------------------

    async def read_settlement(self, settlement_id: str) -> dict[str, Any] | None:
        return await self._settlement.read_settlement(settlement_id)

    async def read_batch(self, batch_id: str) -> dict[str, Any] | None:
        return await self._layerx.get_batch(batch_id)

    async def verify_l1_commitment(
        self,
        transaction_hash: str,
        commitment_hash: str,
        expected_block_number: int,
    ) -> bool | None:
        return await self._settlement.verify_l1_commitment(
            transaction_hash, commitment_hash, expected_block_number
        )
