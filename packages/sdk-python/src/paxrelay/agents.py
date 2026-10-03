"""Agent registration and lookup methods for the Python SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from paxrelay.models import Agent, AgentWallet

if TYPE_CHECKING:
    from paxrelay.client import AsyncPaxRelayClient


class AgentsResource:
    """Operations on agents in the API key's tenant."""

    def __init__(self, client: AsyncPaxRelayClient) -> None:
        self._client = client

    async def create(
        self,
        *,
        name: str,
        slug: str,
        wallet_address: str | None = None,
        description: str | None = None,
    ) -> Agent:
        """Register an agent under the current organisation and project."""
        payload = {
            "name": name,
            "slug": slug,
            "wallet_address": wallet_address,
            "description": description,
        }
        result = await self._client._request("POST", "agents", json=payload)
        return Agent.model_validate(result)

    async def list(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Agent]:
        """List agents, with optional status/search filters and pagination."""
        result = await self._client._request(
            "GET",
            "agents",
            params=_present(
                {"status": status, "search": search, "limit": limit, "offset": offset}
            ),
        )
        return [Agent.model_validate(item) for item in result]

    async def get(self, agent_id: UUID | str) -> Agent:
        """Retrieve one agent by ID."""
        resource_id = self._client._path_id(agent_id)
        result = await self._client._request("GET", f"agents/{resource_id}")
        return Agent.model_validate(result)

    async def wallet(self, agent_id: UUID | str) -> AgentWallet:
        """Retrieve an agent's primary wallet information."""
        resource_id = self._client._path_id(agent_id)
        result = await self._client._request("GET", f"agents/{resource_id}/wallet")
        return AgentWallet.model_validate(result)


def _present(values: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in values.items() if value is not None}
