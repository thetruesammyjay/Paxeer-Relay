"""Webhook endpoint management — CRUD for outbound event notifications.

A webhook endpoint subscribes a caller-supplied URL to one or more domain
event types.  The signing secret is provided once at creation, hashed with
SHA-256, and never returned again — deliveries are HMAC-signed with it by the
worker's delivery pipeline.
"""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

from fastapi import APIRouter, Response, status
from sqlalchemy import select

from paxrelay_domain import EventType
from paxrelay_db.models.executions import WebhookEndpointModel
from paxrelay_db.repositories._common import sid

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.exceptions import InvalidRequestError, NotFoundError
from paxrelay_api.schemas import WebhookCreate, WebhookOut, WebhookUpdate

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_VALID_EVENT_TYPES = {e.value for e in EventType}


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_event_types(event_types: list[str]) -> None:
    """Reject any event type not defined in the domain EventType enum."""
    unknown = [e for e in event_types if e not in _VALID_EVENT_TYPES]
    if unknown:
        raise InvalidRequestError(f"Unknown event type(s): {', '.join(sorted(unknown))}")


def _webhook_out(m: WebhookEndpointModel) -> WebhookOut:
    return WebhookOut(
        id=m.id,
        url=m.url,
        event_types=list(m.event_types or []),
        is_active=m.is_active,
        description=m.description,
        created_at=m.created_at,
    )


async def _get_owned(
    session: SessionDep, tenant: TenantDep, webhook_id: UUID
) -> WebhookEndpointModel:
    """Fetch a webhook, enforcing tenant ownership (404 on cross-tenant)."""
    m = await session.get(WebhookEndpointModel, sid(webhook_id))
    if (
        m is None
        or str(m.organisation_id) != str(tenant.organisation_id)
        or str(m.project_id) != str(tenant.project_id)
    ):
        raise NotFoundError(f"Webhook {webhook_id} not found.")
    return m


@router.post("", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    body: WebhookCreate,
    session: SessionDep,
    tenant: TenantDep,
) -> WebhookOut:
    """Register a webhook endpoint. The secret is stored hashed and never returned."""
    _validate_event_types(body.event_types)
    m = WebhookEndpointModel(
        id=sid(uuid4()),
        organisation_id=sid(tenant.organisation_id),
        project_id=sid(tenant.project_id),
        environment=tenant.environment,
        url=body.url,
        event_types=body.event_types,
        secret_hash=_sha256_hex(body.secret),
        is_active=True,
        description=body.description,
    )
    session.add(m)
    await session.flush()
    await session.refresh(m)
    return _webhook_out(m)


@router.get("", response_model=list[WebhookOut])
async def list_webhooks(session: SessionDep, tenant: TenantDep) -> list[WebhookOut]:
    """List all webhook endpoints for the current tenant."""
    stmt = (
        select(WebhookEndpointModel)
        .where(
            WebhookEndpointModel.organisation_id == sid(tenant.organisation_id),
            WebhookEndpointModel.project_id == sid(tenant.project_id),
        )
        .order_by(WebhookEndpointModel.created_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_webhook_out(m) for m in rows]


@router.get("/{webhook_id}", response_model=WebhookOut)
async def get_webhook(
    webhook_id: UUID, session: SessionDep, tenant: TenantDep
) -> WebhookOut:
    """Fetch a single webhook endpoint by ID."""
    m = await _get_owned(session, tenant, webhook_id)
    return _webhook_out(m)


@router.patch("/{webhook_id}", response_model=WebhookOut)
async def update_webhook(
    webhook_id: UUID,
    body: WebhookUpdate,
    session: SessionDep,
    tenant: TenantDep,
) -> WebhookOut:
    """Partially update a webhook endpoint (url, event types, active, description)."""
    m = await _get_owned(session, tenant, webhook_id)

    if body.event_types is not None:
        _validate_event_types(body.event_types)
        m.event_types = body.event_types
    if body.url is not None:
        m.url = body.url
    if body.is_active is not None:
        m.is_active = body.is_active
    if body.description is not None:
        m.description = body.description

    await session.flush()
    await session.refresh(m)
    return _webhook_out(m)


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def delete_webhook(
    webhook_id: UUID, session: SessionDep, tenant: TenantDep
) -> Response:
    """Delete a webhook endpoint."""
    m = await _get_owned(session, tenant, webhook_id)
    await session.delete(m)
    await session.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
