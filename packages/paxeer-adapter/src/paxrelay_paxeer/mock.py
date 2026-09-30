"""Mock Paxeer adapter — powers local development and automated tests.

All behaviours are deterministic and configurable via constructor arguments.
No real network calls are made.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any


class MockPaxeerAdapter:
    """Implements WalletAdapter, PaymentAdapter, RegistryAdapter, SettlementAdapter.

    Configured by passing options at construction time so tests can
    assert specific behaviours (e.g. payment_always_fails=True).
    """

    def __init__(
        self,
        *,
        payment_always_fails: bool = False,
        verification_latency_ms: int = 0,
        mock_balance_atomic: int = 1_000_000_000,  # 1000 USDX
    ) -> None:
        self._payment_always_fails = payment_always_fails
        self._mock_balance_atomic = mock_balance_atomic
        self._used_nonces: set[str] = set()

    # ------------------------------------------------------------------
    # WalletAdapter
    # ------------------------------------------------------------------

    async def get_wallet(self, address: str) -> dict[str, Any]:
        return {
            "address": address.lower(),
            "type": "policy_bound",
            "chain_id": 125,
            "exists": True,
        }

    async def read_policy(self, address: str) -> dict[str, Any]:
        return {
            "address": address.lower(),
            "policy_active": True,
            "spend_limit_daily_atomic": 100_000_000,  # 100 USDX
        }

    async def verify_session(self, session_proof: str) -> bool:
        # Accept any non-empty proof in mock mode
        return bool(session_proof)

    async def get_balance(self, address: str, currency: str) -> int:
        return self._mock_balance_atomic

    # ------------------------------------------------------------------
    # PaymentAdapter
    # ------------------------------------------------------------------

    async def create_payment_requirement(
        self, quote: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "version": "1",
            "payment_scheme": "402LXP",
            "network": "paxeer",
            "chain_id": 125,
            "settlement_layer": "layerx",
            "currency": quote.get("currency", "USDX"),
            "amount_atomic": str(quote.get("amount_atomic", 0)),
            "recipient": quote.get("recipient_address", "0x0000000000000000000000000000000000000001"),
            "quote_id": quote.get("quote_id", ""),
            "request_hash": quote.get("request_hash", ""),
            "expires_at": quote.get("expires_at", ""),
            "nonce": quote.get("nonce", secrets.token_hex(32)),
        }

    async def verify_payment(
        self, proof: str, quote: dict[str, Any]
    ) -> dict[str, Any]:
        if self._payment_always_fails:
            return {"verified": False, "reason": "mock_failure"}

        # Simulate nonce replay protection
        nonce = quote.get("nonce", proof[:16])
        if nonce in self._used_nonces:
            return {"verified": False, "reason": "nonce_already_used"}
        self._used_nonces.add(nonce)

        tx_hash = "0x" + hashlib.sha256(proof.encode()).hexdigest()
        return {
            "verified": True,
            "layerx_transaction_hash": tx_hash,
            "layerx_batch_id": "0x" + secrets.token_hex(16),
            "verified_at": datetime.utcnow().isoformat() + "Z",
        }

    async def get_payment_status(self, payment_id: str) -> dict[str, Any]:
        return {
            "payment_id": payment_id,
            "state": "verified",
            "layerx_confirmed": True,
            "l1_anchored": False,
        }

    async def get_layerx_transaction(
        self, transaction_hash: str
    ) -> dict[str, Any] | None:
        # The mock status endpoint supplies synthetic confirmation instead.
        return None

    # ------------------------------------------------------------------
    # RegistryAdapter
    # ------------------------------------------------------------------

    async def publish_service(self, service: dict[str, Any]) -> dict[str, Any]:
        return {**service, "registry_id": "reg_mock_" + secrets.token_hex(8)}

    async def find_services(self, capability: str) -> list[dict[str, Any]]:
        return []  # No external registry in mock mode

    async def read_provider_history(self, provider_id: str) -> dict[str, Any]:
        return {
            "provider_id": provider_id,
            "total_calls": 0,
            "success_rate": 1.0,
            "reputation_score": 1.0,
        }

    # ------------------------------------------------------------------
    # SettlementAdapter
    # ------------------------------------------------------------------

    async def read_settlement(self, settlement_id: str) -> dict[str, Any]:
        return {
            "settlement_id": settlement_id,
            "status": "pending",
            "l1_anchored": False,
        }

    async def read_batch(self, batch_id: str) -> dict[str, Any]:
        return {
            "batch_id": batch_id,
            "transactions": [],
            "anchored_at": None,
        }

    async def verify_l1_commitment(
        self,
        transaction_hash: str,
        commitment_hash: str,
        expected_block_number: int,
    ) -> bool:
        # Always returns True in mock mode
        return True
