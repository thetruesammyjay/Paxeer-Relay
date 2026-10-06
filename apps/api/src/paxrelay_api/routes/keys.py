"""API-key creation, inventory, and revocation."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import select

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.audit import record_change
from paxrelay_api.exceptions import ForbiddenError, InvalidRequestError, NotFoundError
from paxrelay_api.schemas import ApiKeyCreate, ApiKeyOut
from paxrelay_api.security.authorization import require_scope
from paxrelay_api.security.scopes import parse_scopes
from paxrelay_api.tenant import tenant_owns
from paxrelay_db.models.projects import ApiKey
from paxrelay_db.repositories._common import sid

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

_KEY_PREFIX = "pk_"


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _api_key_out(key: ApiKey, *, raw_key: str | None = None) -> ApiKeyOut:
    return ApiKeyOut(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        key_type=key.key_type,
        scopes=key.scopes,
        expires_at=key.expires_at,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
        is_active=key.is_active,
        raw_key=raw_key,
    )


@router.post(
    "",
    response_model=ApiKeyOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("api-keys:write"))],
)
async def create_api_key(
    body: ApiKeyCreate,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> ApiKeyOut:
    requested_scopes = parse_scopes(body.scopes)
    if not requested_scopes.issubset(tenant.scopes):
        raise ForbiddenError("An API key cannot grant scopes that its owner does not have.")
    expected_key_type = "live" if tenant.environment == "production" else "test"
    if body.key_type != expected_key_type:
        raise InvalidRequestError(
            f"key_type must be '{expected_key_type}' for the {tenant.environment} environment."
        )

    raw_key = _KEY_PREFIX + secrets.token_hex(24)
    key = ApiKey(
        id=sid(uuid.uuid4()),
        name=body.name,
        key_prefix=raw_key[: len(_KEY_PREFIX) + 8],
        key_hash=_sha256_hex(raw_key),
        key_type=body.key_type,
        scopes=body.scopes,
        created_by=sid(tenant.user_id or tenant.api_key_id)
        if tenant.user_id or tenant.api_key_id
        else None,
        organisation_id=sid(tenant.organisation_id),
        project_id=sid(tenant.project_id),
        environment=tenant.environment,
        expires_at=datetime.now(UTC).replace(tzinfo=None)
        + timedelta(days=body.expires_in_days),
    )
    session.add(key)
    await session.flush()
    await session.refresh(key)
    await record_change(
        request=request,
        session=session,
        tenant=tenant,
        event_type="api_key.created",
        resource_type="api_key",
        resource_id=key.id,
        details={
            "key_prefix": key.key_prefix,
            "key_type": key.key_type,
            "scopes": sorted(requested_scopes),
            "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        },
    )
    return _api_key_out(key, raw_key=raw_key)


@router.get(
    "",
    response_model=list[ApiKeyOut],
    dependencies=[Depends(require_scope("api-keys:read"))],
)
async def list_api_keys(
    session: SessionDep,
    tenant: TenantDep,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[ApiKeyOut]:
    stmt = (
        select(ApiKey)
        .where(
            ApiKey.organisation_id == sid(tenant.organisation_id),
            ApiKey.project_id == sid(tenant.project_id),
            ApiKey.environment == tenant.environment,
        )
        .order_by(ApiKey.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    keys = (await session.execute(stmt)).scalars().all()
    return [_api_key_out(key) for key in keys]


@router.delete(
    "/{api_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
    dependencies=[Depends(require_scope("api-keys:write"))],
)
async def revoke_api_key(
    api_key_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> Response:
    key = await session.get(ApiKey, sid(api_key_id))
    if key is None or not tenant_owns(tenant, key):
        raise NotFoundError("API key not found.")

    key.is_active = False
    key.deleted_at = datetime.now(UTC).replace(tzinfo=None)
    await session.flush()
    await record_change(
        request=request,
        session=session,
        tenant=tenant,
        event_type="api_key.revoked",
        resource_type="api_key",
        resource_id=key.id,
        details={"key_prefix": key.key_prefix},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
