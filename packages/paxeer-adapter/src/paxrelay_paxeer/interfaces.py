"""Paxeer Network adapter Protocol interfaces.

These are the only entry points into Paxeer-specific code.
No other module in PaxRelay should import from paxeer SDK, ethers,
or RPC clients directly — everything must go through these interfaces.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class WalletAdapter(Protocol):
    """Read wallet state and verify session keys."""

    async def get_wallet(self, address: str) -> dict[str, Any] | None: ...
    async def read_policy(self, address: str) -> dict[str, Any] | None: ...
    async def verify_session(self, session_proof: str) -> bool: ...
    async def get_balance(self, address: str, currency: str) -> int: ...


@runtime_checkable
class PaymentAdapter(Protocol):
    """Generate payment requirements and verify proofs via 402LXP."""

    async def create_payment_requirement(
        self,
        quote: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def verify_payment(
        self,
        proof: str,
        quote: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def get_payment_status(self, payment_id: str) -> dict[str, Any]: ...

    async def get_layerx_transaction(
        self, transaction_hash: str
    ) -> dict[str, Any] | None: ...


@runtime_checkable
class RegistryAdapter(Protocol):
    """Read from and write to the Paxeer service registry."""

    async def publish_service(self, service: dict[str, Any]) -> dict[str, Any]: ...
    async def find_services(self, capability: str) -> list[dict[str, Any]]: ...
    async def read_provider_history(self, provider_id: str) -> dict[str, Any]: ...


@runtime_checkable
class SettlementAdapter(Protocol):
    """Read LayerX and L1 settlement records."""

    async def read_settlement(self, settlement_id: str) -> dict[str, Any] | None: ...
    async def read_batch(self, batch_id: str) -> dict[str, Any] | None: ...
    async def verify_l1_commitment(
        self,
        transaction_hash: str,
        commitment_hash: str,
        expected_block_number: int,
    ) -> bool | None: ...
