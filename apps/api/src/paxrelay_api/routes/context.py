"""Return the authenticated API key's tenant context and environment."""

from __future__ import annotations

from fastapi import APIRouter

from paxrelay_api.dependencies import TenantDep
from paxrelay_api.schemas import WorkspaceContextOut

router = APIRouter(prefix="/context", tags=["context"])


@router.get("", response_model=WorkspaceContextOut)
async def get_workspace_context(tenant: TenantDep) -> WorkspaceContextOut:
    """Report the tenant context already bound to the verified bearer key."""
    if tenant.api_key_id is None:
        # ``TenantDep`` is currently backed by API-key auth. Keep this explicit
        # so a future alternate auth dependency cannot return an anonymous ID.
        raise RuntimeError("authenticated workspace has no API key identifier")
    return WorkspaceContextOut(
        organisation_id=tenant.organisation_id,
        project_id=tenant.project_id,
        environment=tenant.environment,
        api_key_id=tenant.api_key_id,
        scopes=sorted(tenant.scopes),
    )
