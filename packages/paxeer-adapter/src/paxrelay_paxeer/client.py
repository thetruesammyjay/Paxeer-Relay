"""Paxeer adapter surfaces and LayerX 402LXP v2 payment support."""

from __future__ import annotations

import re
from typing import Any

import httpx

from paxrelay_paxeer.errors import AdapterConfigurationError
from paxrelay_paxeer.layerx import LayerXClient
from paxrelay_paxeer.layerx_receipts import (
    LayerXReceiptVerifier,
    build_payment_required,
)
from paxrelay_paxeer.settlement import SettlementClient


class OfficialPaxeerAdapter:
    """Live Paxeer and LayerX adapter with locally verified signed receipts.

    Reads all network config from constructor arguments (injected from
    pydantic-settings at startup). LayerX payment requirements, buyer proofs,
    and settlement headers follow the published 402LXP HTTP v2 contract.
    """

    supports_402lxp_http_v2 = True

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
        layerx_network_id: int | None = None,
        layerx_usdx_asset_id: str = "",
        layerx_sequencer_public_key: str = "",
        layerx_testnet_payer_account: str = "",
        gateway_public_base_url: str = "",
        payment_timeout_seconds: int = 300,
    ) -> None:
        self._rpc_url = rpc_url
        self._chain_id = chain_id
        self._timeout = timeout
        self._layerx_network_id = layerx_network_id
        self._layerx_usdx_asset_id = layerx_usdx_asset_id.lower()
        self._layerx_testnet_payer_account = layerx_testnet_payer_account.lower() or None
        self._gateway_public_base_url = gateway_public_base_url.rstrip("/")
        self._payment_timeout_seconds = payment_timeout_seconds
        self._receipt_verifier: LayerXReceiptVerifier | None = None
        if layerx_network_id is not None and layerx_sequencer_public_key and self._layerx_usdx_asset_id:
            self._receipt_verifier = LayerXReceiptVerifier(
                network_id=layerx_network_id,
                sequencer_public_key=layerx_sequencer_public_key,
            )
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
        required, _ = self._payment_required_for_quote(quote)
        return required

    def encode_payment_required(self, requirement: dict[str, Any]) -> str:
        """Encode the v2 envelope for the standard PAYMENT-REQUIRED header."""
        from layerx_sdk.x402_http import encode_header, validate_required

        return encode_header(validate_required(requirement))

    def encode_payment_response(
        self, verification: dict[str, Any], quote: dict[str, Any]
    ) -> str:
        """Encode the standard settlement header from locally verified evidence."""
        from layerx_sdk.x402_http import encode_header

        if (
            not verification.get("verified")
            or verification.get("verification_level") != "sequencer-signed"
            or not verification.get("layerx_receipt")
            or not verification.get("layerx_receipt_digest")
            or not verification.get("payer")
            or self._receipt_verifier is None
        ):
            raise AdapterConfigurationError("layerx_verified_receipt_missing")
        expected_amount = str(quote.get("amount_atomic", ""))
        if (
            verification.get("amount_atomic") != expected_amount
            or verification.get("asset") != self._layerx_usdx_asset_id
            or verification.get("pay_to")
            != str(quote.get("recipient_address", "")).lower()
            or not isinstance(verification.get("payer"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", verification["payer"])
            or not isinstance(verification.get("layerx_receipt_digest"), str)
            or not re.fullmatch(
                r"[0-9a-f]{64}", verification["layerx_receipt_digest"]
            )
            or verification.get("settlement_reference")
            != "lxp:" + verification["layerx_receipt_digest"]
        ):
            raise AdapterConfigurationError("layerx_verified_receipt_mismatch")
        return encode_header(
            {
                "success": True,
                "transaction": verification["settlement_reference"],
                "network": self._receipt_verifier.network,
                "amount": str(quote["amount_atomic"]),
                "payer": verification["payer"],
                "extensions": {
                    "layerx": {
                        "receipt": verification["layerx_receipt"],
                        "receiptDigest": verification["layerx_receipt_digest"],
                        "verificationLevel": "sequencer-signed",
                    }
                },
            }
        )

    def _payment_required_for_quote(
        self, quote: dict[str, Any]
    ) -> tuple[dict[str, Any], str]:
        if self._receipt_verifier is None or self._layerx_network_id is None:
            raise AdapterConfigurationError("layerx_402lxp_v2_not_configured")
        if not self._gateway_public_base_url:
            raise AdapterConfigurationError("gateway_public_base_url_missing")
        if quote.get("currency") != "USDX":
            raise AdapterConfigurationError("layerx_asset_currency_unsupported")
        if quote.get("chain_id") != self._chain_id:
            raise AdapterConfigurationError("paxeer_quote_chain_mismatch")
        if quote.get("currency_decimals") != 6:
            raise AdapterConfigurationError("layerx_asset_decimals_unsupported")
        tool_call_id = quote.get("tool_call_id")
        if not isinstance(tool_call_id, str) or not tool_call_id:
            raise AdapterConfigurationError("layerx_resource_id_missing")
        try:
            amount_atomic = int(quote["amount_atomic"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AdapterConfigurationError("layerx_amount_invalid") from exc
        if amount_atomic <= 0:
            raise AdapterConfigurationError("layerx_amount_invalid")
        return build_payment_required(
            resource_url=f"{self._gateway_public_base_url}/v1/invoke/{tool_call_id}",
            network=self._receipt_verifier.network,
            amount_atomic=amount_atomic,
            asset=self._layerx_usdx_asset_id,
            pay_to=str(quote.get("recipient_address", "")).lower(),
            timeout_seconds=self._payment_timeout_seconds,
            payer=self._layerx_testnet_payer_account,
        )

    async def verify_payment(
        self, proof: str, quote: dict[str, Any]
    ) -> dict[str, Any]:
        """Verify an SDK PAYMENT-SIGNATURE and its sequencer-signed receipt."""
        if self._receipt_verifier is None:
            raise AdapterConfigurationError("layerx_402lxp_v2_not_configured")
        required, _ = self._payment_required_for_quote(quote)
        return self._receipt_verifier.verify_payment_signature(
            payment_required=required,
            payment_signature=proof,
            expected_asset=self._layerx_usdx_asset_id,
            expected_pay_to=str(quote.get("recipient_address", "")).lower(),
            expected_payer=self._layerx_testnet_payer_account,
            expected_resource_url=required["resource"]["url"],
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
