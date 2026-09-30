"""Resolve an agent only after validating a tenant-scoped gateway key."""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import BackgroundTasks, Depends, Header, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paxrelay_domain import Agent, AgentStatus
from paxrelay_db import ApiKey, Organisation, Project, get_engine, get_session
from paxrelay_db.repositories import SqlAlchemyAgentRepository
from paxrelay_db.repositories._common import sid
from paxrelay_gateway.config import get_settings
from paxrelay_gateway.security.rate_limit import enforce_gateway_key_limit

_bearer = HTTPBearer(auto_error=False)
_KEY_PREFIX_LEN = len("pk_") + 8
_DUMMY_HASH = "0" * 64
logger = logging.getLogger("paxrelay.gateway.auth")


class AgentAuthError(Exception):
    """Raised when the acting agent cannot be authenticated."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


async def resolve_agent(
    request: Request,
    background_tasks: BackgroundTasks,
    response: Response,
    x_agent_id: Annotated[str | None, Header()] = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> Agent:
    """Authenticate a gateway key, then resolve an agent inside its tenant."""
    if credentials is None:
        raise AgentAuthError(401, "Invalid or expired API key.")
    raw_key = credentials.credentials
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    if len(raw_key) != 51 or not raw_key.startswith("pk_"):
        secrets.compare_digest(_DUMMY_HASH, key_hash)
        raise AgentAuthError(401, "Invalid or expired API key.")

    key_prefix = raw_key[:_KEY_PREFIX_LEN]
    candidates = (
        await session.execute(
            select(ApiKey).where(
                ApiKey.key_prefix == key_prefix,
                ApiKey.is_active.is_(True),
                ApiKey.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    key: ApiKey | None = None
    for candidate in candidates:
        if secrets.compare_digest(candidate.key_hash, key_hash):
            key = candidate
    if not candidates:
        secrets.compare_digest(_DUMMY_HASH, key_hash)
    if key is None:
        raise AgentAuthError(401, "Invalid or expired API key.")

    now = datetime.now(UTC)
    expires_at = key.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if now > expires_at:
            raise AgentAuthError(401, "Invalid or expired API key.")

    settings = get_settings()
    expected_environment = (
        "development" if settings.app_env in {"development", "test"} else settings.app_env
    )
    expected_key_type = "live" if expected_environment == "production" else "test"
    if key.environment != expected_environment or key.key_type != expected_key_type:
        raise AgentAuthError(401, "Invalid or expired API key.")

    grants = _parse_grants(key.scopes)
    if grants is None or "gateway:invoke" not in grants:
        raise AgentAuthError(403, "This API key cannot invoke the gateway.")

    await enforce_gateway_key_limit(
        request=request,
        response=response,
        key_id=UUID(str(key.id)),
        project_id=UUID(str(key.project_id)),
        environment=key.environment,
        settings=settings,
    )

    project = await session.get(Project, sid(key.project_id))
    organisation = await session.get(Organisation, sid(key.organisation_id))
    if (
        project is None
        or organisation is None
        or not project.is_active
        or not organisation.is_active
        or project.deleted_at is not None
        or organisation.deleted_at is not None
        or str(project.organisation_id) != str(key.organisation_id)
        or str(project.project_id) != str(key.project_id)
        or project.environment != key.environment
    ):
        raise AgentAuthError(401, "Invalid or expired API key.")

    if not x_agent_id:
        raise AgentAuthError(401, "Invalid or unauthorized gateway credentials.")
    try:
        agent_id = UUID(x_agent_id)
    except ValueError as exc:
        raise AgentAuthError(401, "Invalid or unauthorized gateway credentials.") from exc

    repo = SqlAlchemyAgentRepository(session)
    agent = await repo.get(agent_id)
    if (
        agent is None
        or str(agent.organisation_id) != str(key.organisation_id)
        or str(agent.project_id) != str(key.project_id)
        or agent.environment.value != key.environment
    ):
        raise AgentAuthError(401, "Invalid or unauthorized gateway credentials.")
    if agent.status != AgentStatus.ACTIVE:
        raise AgentAuthError(403, "Agent is not active.")

    # Update usage in a separate transaction after the response. Keeping this
    # out of the paid-call transaction avoids holding the key row during a
    # potentially slow provider request.
    last_used = key.last_used_at
    if last_used is not None and last_used.tzinfo is None:
        last_used = last_used.replace(tzinfo=UTC)
    cutoff = now - timedelta(minutes=1)
    if last_used is None or last_used <= cutoff:
        background_tasks.add_task(
            _record_key_use,
            key_id=str(key.id),
            used_at=now.replace(tzinfo=None),
        )

    request.state.gateway_api_key_id = UUID(str(key.id))
    request.state.gateway_project_id = UUID(str(key.project_id))
    return agent


async def _record_key_use(*, key_id: str, used_at: datetime) -> None:
    """Best-effort last-used update in a short independent transaction."""
    try:
        session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
        async with session_factory.begin() as session:
            await session.execute(
                update(ApiKey)
                .where(
                    ApiKey.id == key_id,
                    ApiKey.is_active.is_(True),
                    ApiKey.deleted_at.is_(None),
                    or_(
                        ApiKey.last_used_at.is_(None),
                        ApiKey.last_used_at <= (used_at - timedelta(minutes=1)),
                    ),
                )
                .values(last_used_at=used_at)
                .execution_options(synchronize_session=False)
            )
    except Exception as exc:  # noqa: BLE001 - telemetry must not break the response.
        logger.warning(
            "Unable to update gateway API key usage metadata key_id=%s error=%s",
            key_id,
            type(exc).__name__,
        )


def _parse_grants(value: str | None) -> frozenset[str] | None:
    """Parse persisted scope pairs; malformed values fail closed."""
    if not value:
        return frozenset()
    parts = value.split(":")
    if len(parts) % 2:
        return None
    if any(
        not resource or not action
        for resource, action in zip(parts[::2], parts[1::2])
    ):
        return None
    return frozenset(
        f"{resource}:{action}" for resource, action in zip(parts[::2], parts[1::2])
    )
