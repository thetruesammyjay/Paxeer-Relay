"""API-key authentication dependency.

Flow
----
1. Extract the ``Bearer <token>`` credential from the ``Authorization`` header.
2. Derive the stored key prefix from the token and query ``api_keys`` by it.
3. Compute SHA-256 of the presented token and compare to the stored hash in
   constant time (``secrets.compare_digest``).
4. Verify the key is active and not expired.
5. Parse the key's grants and update ``last_used_at`` in the request session.
6. Return a :class:`TenantContext` populated from the key's tenant columns.

The function is used as a FastAPI dependency — it raises ``UnauthorizedError``
(→ HTTP 401) on any failure so callers never see a partial or misleading error.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_db import ApiKey, Organisation, Project, get_session

from paxrelay_api.config import get_settings
from paxrelay_api.exceptions import UnauthorizedError
from paxrelay_api.security.rate_limit import enforce_api_key_limit
from paxrelay_api.security.scopes import parse_scopes
from paxrelay_api.tenant import TenantContext

# Re-use the shared get_session dependency; auth happens at the same DB session
# as the rest of the request so last_used_at is committed atomically.
_bearer = HTTPBearer(auto_error=False)

_KEY_PREFIX_LEN = len("pk_") + 8  # "pk_" + 8 hex chars == 11


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def verify_api_key(
    request: Request,
    response: Response,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> TenantContext:
    """FastAPI dependency — resolve and verify an API key, return tenant context.

    Raises :class:`UnauthorizedError` (HTTP 401) for any authentication failure.
    All failure paths return the same generic message to prevent oracle attacks.
    """
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Invalid or expired API key.")

    raw_key = credentials.credentials

    if len(raw_key) < _KEY_PREFIX_LEN:
        raise UnauthorizedError("Invalid or expired API key.")

    key_prefix = raw_key[:_KEY_PREFIX_LEN]
    key_hash = _sha256_hex(raw_key)

    # Look up by prefix first — the index on key_prefix makes this a fast
    # narrow scan; the hash comparison below is the authoritative check.
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == key_prefix,
            ApiKey.is_active.is_(True),
            ApiKey.deleted_at.is_(None),
        )
    )
    candidates = result.scalars().all()

    # Prefixes are indexed but not unique. Compare every candidate so a rare
    # prefix collision does not turn valid credentials into a server error.
    row: ApiKey | None = None
    for candidate in candidates:
        if secrets.compare_digest(candidate.key_hash, key_hash):
            row = candidate
    if not candidates:
        secrets.compare_digest("0" * 64, key_hash)
    if row is None:
        raise UnauthorizedError("Invalid or expired API key.")

    # Reject expired keys.
    now = datetime.now(UTC)
    if row.expires_at is not None:
        # expires_at is stored as naive UTC; make it aware for comparison.
        expires = (
            row.expires_at.replace(tzinfo=UTC)
            if row.expires_at.tzinfo is None
            else row.expires_at
        )
        if now > expires:
            raise UnauthorizedError("Invalid or expired API key.")

    project, organisation = await _get_active_tenant(session, row)
    if project is None or organisation is None:
        raise UnauthorizedError("Invalid or expired API key.")

    settings = getattr(request.app.state, "settings", None) or get_settings()
    expected_environment = (
        "development" if settings.app_env in {"development", "test"} else settings.app_env
    )
    if row.environment != expected_environment:
        raise UnauthorizedError("Invalid or expired API key.")

    try:
        scopes = parse_scopes(row.scopes)
    except ValueError as exc:
        # Corrupt or pre-scope-format values are never interpreted as broad
        # grants. The key must be rotated with a valid scope set.
        raise UnauthorizedError("Invalid or expired API key.") from exc

    tenant = TenantContext(
        organisation_id=UUID(str(row.organisation_id)),
        project_id=UUID(str(row.project_id)),
        environment=row.environment,
        scopes=scopes,
        api_key_id=UUID(str(row.id)),
    )
    await enforce_api_key_limit(
        request=request,
        response=response,
        tenant=tenant,
        settings=settings,
    )

    # Refresh at most once per minute. This keeps key inventory useful without
    # making concurrent API requests write the same key row on every call.
    last_used = row.last_used_at
    if last_used is not None and last_used.tzinfo is None:
        last_used = last_used.replace(tzinfo=UTC)
    refresh_after = now - timedelta(minutes=1)
    if last_used is None or last_used <= refresh_after:
        cutoff = refresh_after.replace(tzinfo=None)
        await session.execute(
            update(ApiKey)
            .where(
                ApiKey.id == row.id,
                or_(ApiKey.last_used_at.is_(None), ApiKey.last_used_at <= cutoff),
            )
            .values(last_used_at=now.replace(tzinfo=None))  # database timestamps are naive UTC
            .execution_options(synchronize_session=False)
        )

    return tenant


async def _get_active_tenant(
    session: AsyncSession,
    key: ApiKey,
) -> tuple[Project | None, Organisation | None]:
    """Resolve the key's active project and organisation without leaking state."""
    project = await session.get(Project, str(key.project_id))
    organisation = await session.get(Organisation, str(key.organisation_id))
    if (
        project is None
        or organisation is None
        or not project.is_active
        or not organisation.is_active
        or project.deleted_at is not None
        or organisation.deleted_at is not None
        or str(project.organisation_id) != str(key.organisation_id)
        or str(project.project_id) != str(key.project_id)
        or str(project.environment) != str(key.environment)
    ):
        return None, None
    return project, organisation
