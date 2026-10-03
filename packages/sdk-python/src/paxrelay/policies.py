"""Spend-policy creation, lookup, and assignment for the Python SDK."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal
from uuid import UUID

from paxrelay.models import Policy, PolicyAssignment

if TYPE_CHECKING:
    from paxrelay.client import AsyncPaxRelayClient

PolicyMode = Literal["observe", "warn", "enforce"]


class PoliciesResource:
    """Operations on policies in the API key's tenant."""

    def __init__(self, client: AsyncPaxRelayClient) -> None:
        self._client = client

    async def create(
        self,
        *,
        name: str,
        mode: PolicyMode = "enforce",
        description: str | None = None,
        maximum_per_call_atomic: int | None = None,
        daily_budget_atomic: int | None = None,
        monthly_budget_atomic: int | None = None,
        approval_threshold_atomic: int | None = None,
        allowed_capabilities: Sequence[str] = (),
        allowed_providers: Sequence[UUID | str] = (),
        blocked_providers: Sequence[UUID | str] = (),
    ) -> Policy:
        """Create a tenant policy using USDX atomic amounts (six decimals)."""
        payload = {
            "name": name,
            "mode": mode,
            "description": description,
            "maximum_per_call": _money(maximum_per_call_atomic),
            "daily_budget": _money(daily_budget_atomic),
            "monthly_budget": _money(monthly_budget_atomic),
            "approval_threshold": _money(approval_threshold_atomic),
            "allowed_capabilities": list(allowed_capabilities),
            "allowed_providers": [str(provider_id) for provider_id in allowed_providers],
            "blocked_providers": [str(provider_id) for provider_id in blocked_providers],
        }
        result = await self._client._request("POST", "policies", json=payload)
        return Policy.model_validate(result)

    async def list(
        self,
        *,
        mode: PolicyMode | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Policy]:
        """List policies, optionally filtered by mode, active state, or name."""
        params = {
            key: value
            for key, value in {
                "mode": mode,
                "is_active": is_active,
                "search": search,
                "limit": limit,
                "offset": offset,
            }.items()
            if value is not None
        }
        result = await self._client._request("GET", "policies", params=params)
        return [Policy.model_validate(item) for item in result]

    async def get(self, policy_id: UUID | str) -> Policy:
        """Retrieve policy metadata by ID."""
        resource_id = self._client._path_id(policy_id)
        result = await self._client._request("GET", f"policies/{resource_id}")
        return Policy.model_validate(result)

    async def assign(
        self,
        policy_id: UUID | str,
        *,
        agent_id: UUID | str,
    ) -> PolicyAssignment:
        """Assign a tenant-owned policy to a tenant-owned agent."""
        policy_uuid = self._client._path_id(policy_id)
        agent_uuid = self._client._path_id(agent_id)
        result = await self._client._request(
            "POST",
            f"policies/{policy_uuid}/assign",
            json={"agent_id": agent_uuid},
        )
        return PolicyAssignment.model_validate(result)


def _money(amount_atomic: int | None) -> dict[str, int | str] | None:
    if amount_atomic is None:
        return None
    return {"amount_atomic": amount_atomic, "currency": "USDX", "decimals": 6}
