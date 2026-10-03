"""Approval-queue operations for the Python SDK."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from uuid import UUID

from paxrelay.models import ApprovalRequest

if TYPE_CHECKING:
    from paxrelay.client import AsyncPaxRelayClient

ApprovalDecision = Literal["approved", "rejected"]
ApprovalStatus = Literal[
    "pending", "approved", "rejected", "expired", "consumed", "invalidated"
]


class ApprovalsResource:
    """List and decide approval requests in the API key's tenant."""

    def __init__(self, client: AsyncPaxRelayClient) -> None:
        self._client = client

    async def list(
        self,
        *,
        status: ApprovalStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ApprovalRequest]:
        """List tenant approval requests, newest first, with optional filtering."""
        params = {
            key: value
            for key, value in {
                "status": status,
                "limit": limit,
                "offset": offset,
            }.items()
            if value is not None
        }
        result = await self._client._request("GET", "approvals", params=params)
        return [ApprovalRequest.model_validate(item) for item in result]

    async def get(self, approval_id: UUID | str) -> ApprovalRequest:
        """Retrieve one tenant-scoped approval request by ID."""
        resource_id = self._client._path_id(approval_id)
        result = await self._client._request("GET", f"approvals/{resource_id}")
        return ApprovalRequest.model_validate(result)

    async def decide(
        self,
        approval_id: UUID | str,
        *,
        decision: ApprovalDecision,
        reason: str | None = None,
    ) -> ApprovalRequest:
        """Approve or reject a pending request.

        The API makes a repeated identical decision idempotent. A conflicting
        decision raises :class:`paxrelay.ConflictError`.
        """
        resource_id = self._client._path_id(approval_id)
        result = await self._client._request(
            "POST",
            f"approvals/{resource_id}/decision",
            json={"decision": decision, "reason": reason},
        )
        return ApprovalRequest.model_validate(result)

    async def approve(
        self,
        approval_id: UUID | str,
        *,
        reason: str | None = None,
    ) -> ApprovalRequest:
        """Approve a pending request, optionally recording the reason."""
        return await self.decide(approval_id, decision="approved", reason=reason)

    async def reject(
        self,
        approval_id: UUID | str,
        *,
        reason: str | None = None,
    ) -> ApprovalRequest:
        """Reject a pending request, optionally recording the reason."""
        return await self.decide(approval_id, decision="rejected", reason=reason)
