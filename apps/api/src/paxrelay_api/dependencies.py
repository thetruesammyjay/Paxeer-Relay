"""Shared FastAPI dependencies for the control-plane API."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_db import get_session
from paxrelay_api.security import verify_api_key
from paxrelay_api.tenant import TenantContext

# Re-export TenantContext so existing route imports still resolve.
__all__ = ["TenantContext", "TenantDep", "SessionDep"]

TenantDep = Annotated[TenantContext, Depends(verify_api_key)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]
