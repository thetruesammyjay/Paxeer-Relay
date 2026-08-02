"""Shared FastAPI dependencies for the control-plane API."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_db import get_session


@dataclass(frozen=True)
class TenantContext:
    """The tenant every API request is scoped to.

    Phase 1 resolves tenant from the authenticated API key; the
    organisation/project are derived from the key's owning agent. A stable
    header-based override is reserved for dashboard sessions.
    """

    organisation_id: UUID
    project_id: UUID
    environment: str = "development"


async def _default_tenant() -> TenantContext:
    # Placeholder tenant for Phase 1. Auth middleware (security/) will
    # populate this from the API key's owning agent.
    return TenantContext(
        organisation_id=uuid.UUID(int=1),
        project_id=uuid.UUID(int=1),
        environment="development",
    )


TenantDep = Annotated[TenantContext, Depends(_default_tenant)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
