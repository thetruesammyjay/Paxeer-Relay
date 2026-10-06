"""LayerX transport placeholder with explicit fail-closed behavior.

The old implementation called undocumented REST paths such as
``/transactions/{hash}`` and ``/batches/{id}``. The published LayerX API uses
JSON-RPC and signed receipt evidence, so these REST lookups cannot establish
payment or settlement truth.
"""

from __future__ import annotations

from typing import Any

from paxrelay_paxeer.errors import AdapterConfigurationError


class LayerXClient:
    """Compatibility surface for LayerX reads, disabled pending SDK wiring."""

    def __init__(self, api_url: str, timeout: float = 10.0) -> None:
        # Retain constructor compatibility while avoiding unsupported requests.
        self._api_url = api_url.rstrip("/")
        self._timeout = timeout

    async def get_transaction(self, tx_hash: str) -> dict[str, Any] | None:
        del tx_hash
        raise AdapterConfigurationError(
            "layerx_receipt_rpc_verifier_not_integrated"
        )

    async def get_batch(self, batch_id: str) -> dict[str, Any] | None:
        del batch_id
        raise AdapterConfigurationError(
            "layerx_batch_rpc_verifier_not_integrated"
        )

    async def verify_transaction_matches_quote(
        self,
        tx_hash: str,
        expected_amount_atomic: int,
        expected_recipient: str,
        expected_quote_id: str,
    ) -> tuple[bool, str]:
        del tx_hash, expected_amount_atomic, expected_recipient, expected_quote_id
        raise AdapterConfigurationError(
            "layerx_402lxp_v2_verifier_not_integrated"
        )
