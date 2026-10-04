"""MCP application lifespan helpers for gateway clients."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import httpx
from paxrelay.payments import AsyncPaxRelayGatewayClient

from paxrelay_mcp.client import PaxRelayMCPAdapter
from paxrelay_mcp.types import PaymentProofProvider


def gateway_adapter_lifespan(
    *,
    api_key: str,
    agent_id: UUID | str,
    base_url: str = "http://localhost:8080",
    timeout: float = 60.0,
    payment_proof_provider: PaymentProofProvider | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> Callable[[Any], Any]:
    """Build an MCP lifespan callback that owns the gateway connection pool.

    The caller supplies credentials from its secret manager or process
    environment. This helper does not persist or log the API key or proof.
    """

    @asynccontextmanager
    async def lifespan(_: Any) -> AsyncIterator[dict[str, PaxRelayMCPAdapter]]:
        gateway = AsyncPaxRelayGatewayClient(
            api_key=api_key,
            agent_id=agent_id,
            base_url=base_url,
            timeout=timeout,
            http_client=http_client,
        )
        try:
            yield {
                "paxrelay": PaxRelayMCPAdapter(
                    gateway,
                    payment_proof_provider=payment_proof_provider,
                )
            }
        finally:
            await gateway.aclose()

    return lifespan
