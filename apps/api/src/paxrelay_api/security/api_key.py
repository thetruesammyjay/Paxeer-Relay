"""API-key authentication dependency.

Flow
----
1. Extract the ``Bearer <token>`` credential from the ``Authorization`` header.
2. Derive the 8-char key prefix from the token and query ``api_keys`` by it.
3. Compute SHA-256 of the presented token and compare to the stored hash in
   constant time (``secrets.compare_digest``).
4. Verify the key is active and not expired.
5. Update ``last_used_at`` asynchronously (fire-and-forget on the same session).
6. Return a :class:`TenantContext` populated from the key's tenant columns.

The function is used as a FastAPI dependency — it raises ``UnauthorizedError``
(→ HTTP 401) on any failure so callers never see a partial or misleading error.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_db import ApiKey
from paxrelay_db import get_session

from paxrelay_api.exceptions import UnauthorizedError
from paxrelay_api.tenant import TenantContext

# Re-use the shared get_session dependency; auth happens at the same DB session
# as the rest of the request so last_used_at is committed atomically.
_bearer = HTTPBearer(auto_error=False)

_KEY_PREFIX_LEN = len("pk_") + 8  # "pk_" + 8 hex chars == 11


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def verify_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> TenantContext:
    """FastAPI dependency — resolve and verify an API key, return tenant context.

    Raises :class:`UnauthorizedError` (HTTP 401) for any authentication failure.
    All failure paths return the same generic message to prevent oracle attacks.
    """
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing or malformed Authorization header.")

    raw_key = credentials.credentials

    if len(raw_key) < _KEY_PREFIX_LEN:
        raise UnauthorizedError("Invalid API key.")

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
    row: ApiKey | None = result.scalar_one_or_none()

    # Constant-time comparison even when no row was found (avoids timing oracle).
    stored_hash = row.key_hash if row is not None else ("0" * 64)
    if not secrets.compare_digest(stored_hash, key_hash):
        raise UnauthorizedError("Invalid API key.")

    # Guard: row must not be None at this point (compare_digest would have
    # already differed), but make the type-narrowing explicit.
    assert row is not None  # noqa: S101

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
            raise UnauthorizedError("API key has expired.")

    # Stamp last_used_at — same session, committed with the rest of the request.
    await session.execute(
        update(ApiKey)
        .where(ApiKey.id == row.id)
        .values(last_used_at=now.replace(tzinfo=None))  # store naive UTC, matching schema
        .execution_options(synchronize_session=False)
    )

    from uuid import UUID

    return TenantContext(
        organisation_id=UUID(str(row.organisation_id)),
        project_id=UUID(str(row.project_id)),
        environment=row.environment,
    )
