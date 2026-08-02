"""API key issuance.

The raw key is generated once, returned to the caller a single time, and only
its SHA-256 hash is persisted. The ``pk_`` prefix is stored so the API can
look up which key presented without holding the raw value.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, status

from paxrelay_db.models.projects import ApiKey
from paxrelay_db.repositories._common import sid

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.schemas import ApiKeyCreate, ApiKeyOut

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

_KEY_PREFIX = "pk_"


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.post("", response_model=ApiKeyOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreate,
    session: SessionDep,
    tenant: TenantDep,
) -> ApiKeyOut:
    raw_key = _KEY_PREFIX + secrets.token_hex(24)
    key = ApiKey(
        id=sid(uuid.uuid4()),
        name=body.name,
        key_prefix=raw_key[: _KEY_PREFIX.__len__() + 8],
        key_hash=_sha256_hex(raw_key),
        key_type=body.key_type,
        scopes=body.scopes,
        organisation_id=sid(tenant.organisation_id),
        project_id=sid(tenant.project_id),
        environment=tenant.environment,
        expires_at=datetime.utcnow() + timedelta(days=365),
    )
    session.add(key)
    await session.flush()
    return ApiKeyOut(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        key_type=key.key_type,
        raw_key=raw_key,  # the only time the raw key is ever available
    )
