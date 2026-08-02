"""Gateway authentication middleware.

Phase 1 trusts the ``X-Agent-Id`` header as the acting agent identity and
enforces that the agent is active. This is the extension point where API-key
authentication (hash lookup on the ``api_keys`` table) plugs in later.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_domain import Agent, AgentStatus
from paxrelay_db import get_session
from paxrelay_db.repositories import SqlAlchemyAgentRepository


class AgentAuthError(Exception):
    """Raised when the acting agent cannot be authenticated."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


async def resolve_agent(
    x_agent_id: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_session),
) -> Agent:
    """Resolve and validate the acting agent from the request headers."""
    if not x_agent_id:
        raise AgentAuthError(401, "Missing X-Agent-Id header.")
    try:
        agent_id = UUID(x_agent_id)
    except ValueError as exc:
        raise AgentAuthError(401, "Malformed X-Agent-Id header.") from exc

    repo = SqlAlchemyAgentRepository(session)
    agent = await repo.get(agent_id)
    if agent is None:
        raise AgentAuthError(401, "Unknown agent.")
    if agent.status != AgentStatus.ACTIVE:
        raise AgentAuthError(403, "Agent is not active.")
    return agent
