"""Service publishing and lookup methods for the Python SDK."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from paxrelay.models import Service

if TYPE_CHECKING:
    from paxrelay.client import AsyncPaxRelayClient

ServiceProtocol = Literal["http", "mcp", "grpc"]


class ServicesResource:
    """Operations on services published by tenant-owned providers."""

    def __init__(self, client: AsyncPaxRelayClient) -> None:
        self._client = client

    async def publish(
        self,
        provider_id: UUID | str,
        *,
        name: str,
        slug: str,
        capability: str,
        price_amount_atomic: int,
        base_url: str,
        endpoint_url: str,
        protocols: Sequence[ServiceProtocol] = ("http",),
        version: str = "1.0.0",
        description: str | None = None,
    ) -> Service:
        """Publish a service and its initial immutable routing version.

        ``price_amount_atomic`` is expressed in the API's supported currency,
        USDX, with six decimal places. The API checks provider ownership and
        enforces HTTPS and wallet requirements for production tenants.
        """
        payload = {
            "name": name,
            "slug": slug,
            "capability": capability,
            "protocols": list(protocols),
            "price_per_call": {
                "amount_atomic": price_amount_atomic,
                "currency": "USDX",
                "decimals": 6,
            },
            "base_url": base_url,
            "endpoint_url": endpoint_url,
            "version": version,
            "description": description,
        }
        result = await self._client._request(
            "POST",
            f"services/providers/{self._client._path_id(provider_id)}",
            json=payload,
        )
        return Service.model_validate(result)

    async def list(self) -> list[Service]:
        """List services in the API key's tenant."""
        result = await self._client._request("GET", "services")
        return [Service.model_validate(item) for item in result]

    async def get(self, service_id: UUID | str) -> Service:
        """Retrieve one service by ID."""
        resource_id = self._client._path_id(service_id)
        result = await self._client._request("GET", f"services/{resource_id}")
        return Service.model_validate(result)
