"""Provider registration and lookup methods for the Python SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from paxrelay.models import Provider

if TYPE_CHECKING:
    from paxrelay.client import AsyncPaxRelayClient


class ProvidersResource:
    """Operations on providers in the API key's tenant."""

    def __init__(self, client: AsyncPaxRelayClient) -> None:
        self._client = client

    async def create(
        self,
        *,
        name: str,
        slug: str,
        wallet_address: str | None = None,
        description: str | None = None,
        website_url: str | None = None,
    ) -> Provider:
        """Register a service provider under the current tenant."""
        payload = {
            "name": name,
            "slug": slug,
            "wallet_address": wallet_address,
            "description": description,
            "website_url": website_url,
        }
        result = await self._client._request("POST", "providers", json=payload)
        return Provider.model_validate(result)

    async def list(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Provider]:
        """List providers, with optional status/search filters and pagination."""
        result = await self._client._request(
            "GET",
            "providers",
            params={
                key: value
                for key, value in {
                    "status": status,
                    "search": search,
                    "limit": limit,
                    "offset": offset,
                }.items()
                if value is not None
            },
        )
        return [Provider.model_validate(item) for item in result]

    async def get(self, provider_id: UUID | str) -> Provider:
        """Retrieve one provider by ID."""
        resource_id = self._client._path_id(provider_id)
        result = await self._client._request("GET", f"providers/{resource_id}")
        return Provider.model_validate(result)
