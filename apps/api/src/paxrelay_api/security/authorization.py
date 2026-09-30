"""FastAPI dependencies for scope-based route authorization."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Depends

from paxrelay_api.exceptions import ForbiddenError
from paxrelay_api.security.api_key import verify_api_key
from paxrelay_api.security.scopes import ALL_SCOPES
from paxrelay_api.tenant import TenantContext


def require_scope(scope: str) -> Callable[..., Coroutine[Any, Any, TenantContext]]:
    """Return a FastAPI dependency that enforces one API-key grant."""
    if scope not in ALL_SCOPES:
        raise ValueError(f"Unknown API scope: {scope}")

    async def enforce(tenant: TenantContext = Depends(verify_api_key)) -> TenantContext:
        if scope not in tenant.scopes:
            raise ForbiddenError("This API key does not have the required scope.")
        return tenant

    return enforce
