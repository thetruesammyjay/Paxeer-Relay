"""Webhook endpoint management — CRUD for outbound event notifications.

A webhook endpoint subscribes a caller-supplied URL to one or more domain
event types. The shared secret is hashed for identification and encrypted at
rest so the worker can sign outbound deliveries.
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import and_, or_, select

from paxrelay_domain import EventType
from paxrelay_db.models.executions import WebhookDeliveryModel, WebhookEndpointModel
from paxrelay_db.repositories._common import sid

from paxrelay_api.config import get_settings
from paxrelay_api.audit import record_change
from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.exceptions import ConflictError, InvalidRequestError, NotFoundError
from paxrelay_api.schemas import (
    WebhookCreate,
    WebhookDeliveryOut,
    WebhookDeliveryPageOut,
    WebhookOut,
    WebhookUpdate,
)
from paxrelay_api.security.authorization import require_scope
from paxrelay_receipts.webhook_secrets import (
    encrypt_webhook_secret,
    webhook_secret_digest,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_VALID_EVENT_TYPES = {e.value for e in EventType}


def _validate_event_types(event_types: list[str]) -> None:
    """Reject any event type not defined in the domain EventType enum."""
    unknown = [e for e in event_types if e not in _VALID_EVENT_TYPES]
    if unknown:
        raise InvalidRequestError(f"Unknown event type(s): {', '.join(sorted(unknown))}")


def _validate_destination_url(url: str, environment: str) -> None:
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as exc:
        raise InvalidRequestError(
            "Webhook URL must include a valid HTTP or HTTPS host."
        ) from exc
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise InvalidRequestError("Webhook URL must include a valid HTTP or HTTPS host.")
    if parsed.username is not None or parsed.password is not None or parsed.fragment:
        raise InvalidRequestError(
            "Webhook URL cannot contain embedded credentials or a fragment."
        )
    if environment in {"staging", "production"} and parsed.scheme != "https":
        raise InvalidRequestError("Staging and production webhook URLs must use HTTPS.")


def _webhook_out(m: WebhookEndpointModel) -> WebhookOut:
    return WebhookOut(
        id=m.id,
        url=m.url,
        event_types=list(m.event_types or []),
        secret_configured=m.secret_ciphertext is not None,
        is_active=m.is_active,
        description=m.description,
        created_at=m.created_at,
    )


def _delivery_out(m: WebhookDeliveryModel) -> WebhookDeliveryOut:
    return WebhookDeliveryOut(
        id=m.id,
        event_type=m.event_type,
        status=m.status,
        attempt_count=m.attempt_count,
        http_status_code=m.http_status_code,
        last_error=m.last_error,
        created_at=m.created_at,
        updated_at=m.updated_at,
        next_attempt_at=m.next_attempt_at,
        delivered_at=m.delivered_at,
    )


async def _get_owned(
    session: SessionDep,
    tenant: TenantDep,
    webhook_id: UUID,
    *,
    for_update: bool = False,
) -> WebhookEndpointModel:
    """Fetch a webhook, enforcing tenant ownership (404 on cross-tenant)."""
    stmt = select(WebhookEndpointModel).where(
        WebhookEndpointModel.id == sid(webhook_id),
        WebhookEndpointModel.organisation_id == sid(tenant.organisation_id),
        WebhookEndpointModel.project_id == sid(tenant.project_id),
        WebhookEndpointModel.environment == tenant.environment,
    )
    if for_update:
        stmt = stmt.with_for_update()
    m = (await session.execute(stmt)).scalar_one_or_none()
    if m is None:
        raise NotFoundError(f"Webhook {webhook_id} not found.")
    return m


@router.post(
    "",
    response_model=WebhookOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("webhooks:write"))],
)
async def create_webhook(
    body: WebhookCreate,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> WebhookOut:
    """Register an endpoint; its shared secret is encrypted and never returned."""
    _validate_event_types(body.event_types)
    _validate_destination_url(body.url, tenant.environment)
    settings = getattr(request.app.state, "settings", None) or get_settings()
    endpoint_id = sid(uuid4())
    secret = body.secret.get_secret_value()
    m = WebhookEndpointModel(
        id=endpoint_id,
        organisation_id=sid(tenant.organisation_id),
        project_id=sid(tenant.project_id),
        environment=tenant.environment,
        url=body.url,
        event_types=body.event_types,
        secret_hash=webhook_secret_digest(secret),
        secret_ciphertext=encrypt_webhook_secret(
            secret,
            settings.webhook_encryption_key or settings.auth_secret,
            endpoint_id,
        ),
        is_active=True,
        description=body.description,
    )
    session.add(m)
    await session.flush()
    await session.refresh(m)
    await record_change(
        request=request,
        session=session,
        tenant=tenant,
        event_type="webhook.created",
        resource_type="webhook_endpoint",
        resource_id=m.id,
        details={"event_types": list(m.event_types or [])},
    )
    return _webhook_out(m)


@router.get(
    "",
    response_model=list[WebhookOut],
    dependencies=[Depends(require_scope("webhooks:read"))],
)
async def list_webhooks(session: SessionDep, tenant: TenantDep) -> list[WebhookOut]:
    """List all webhook endpoints for the current tenant."""
    stmt = (
        select(WebhookEndpointModel)
        .where(
            WebhookEndpointModel.organisation_id == sid(tenant.organisation_id),
            WebhookEndpointModel.project_id == sid(tenant.project_id),
            WebhookEndpointModel.environment == tenant.environment,
        )
        .order_by(WebhookEndpointModel.created_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [_webhook_out(m) for m in rows]


@router.get(
    "/{webhook_id}",
    response_model=WebhookOut,
    dependencies=[Depends(require_scope("webhooks:read"))],
)
async def get_webhook(
    webhook_id: UUID, session: SessionDep, tenant: TenantDep
) -> WebhookOut:
    """Fetch a single webhook endpoint by ID."""
    m = await _get_owned(session, tenant, webhook_id)
    return _webhook_out(m)


@router.get(
    "/{webhook_id}/deliveries",
    response_model=WebhookDeliveryPageOut,
    dependencies=[Depends(require_scope("webhooks:read"))],
)
async def list_webhook_deliveries(
    webhook_id: UUID,
    session: SessionDep,
    tenant: TenantDep,
    status_filter: str | None = Query(
        None,
        alias="status",
        pattern=r"^(pending|processing|delivered|failed|cancelled)$",
    ),
    limit: int = Query(50, ge=1, le=100),
    before_created_at: datetime | None = Query(None),
    before_id: UUID | None = Query(None),
) -> WebhookDeliveryPageOut:
    """List delivery metadata for one tenant-owned endpoint, newest first."""
    endpoint = await _get_owned(session, tenant, webhook_id)
    if (before_created_at is None) != (before_id is None):
        raise InvalidRequestError(
            "Both before_created_at and before_id are required for pagination."
        )

    stmt = select(WebhookDeliveryModel).where(
        WebhookDeliveryModel.endpoint_id == endpoint.id
    )
    if status_filter is not None:
        stmt = stmt.where(WebhookDeliveryModel.status == status_filter)
    if before_created_at is not None and before_id is not None:
        cursor_time = before_created_at
        if cursor_time.tzinfo is not None:
            cursor_time = cursor_time.astimezone(UTC).replace(tzinfo=None)
        stmt = stmt.where(
            or_(
                WebhookDeliveryModel.created_at < cursor_time,
                and_(
                    WebhookDeliveryModel.created_at == cursor_time,
                    WebhookDeliveryModel.id < sid(before_id),
                ),
            )
        )

    rows = (
        await session.execute(
            stmt.order_by(
                WebhookDeliveryModel.created_at.desc(),
                WebhookDeliveryModel.id.desc(),
            ).limit(limit + 1)
        )
    ).scalars().all()
    has_more = len(rows) > limit
    page_rows = rows[:limit]
    last_row = page_rows[-1] if has_more and page_rows else None
    return WebhookDeliveryPageOut(
        items=[_delivery_out(row) for row in page_rows],
        next_cursor_created_at=last_row.created_at if last_row is not None else None,
        next_cursor_id=last_row.id if last_row is not None else None,
    )


@router.post(
    "/{webhook_id}/deliveries/{delivery_id}/retry",
    response_model=WebhookDeliveryOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_scope("webhooks:write"))],
)
async def retry_webhook_delivery(
    webhook_id: UUID,
    delivery_id: UUID,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> WebhookDeliveryOut:
    """Queue a failed delivery again after an operator corrects its endpoint."""
    endpoint = await _get_owned(session, tenant, webhook_id, for_update=True)
    if not endpoint.is_active or endpoint.secret_ciphertext is None:
        raise ConflictError(
            "Activate the endpoint and configure its signing secret before retrying."
        )

    stmt = (
        select(WebhookDeliveryModel)
        .where(
            WebhookDeliveryModel.id == sid(delivery_id),
            WebhookDeliveryModel.endpoint_id == endpoint.id,
        )
        .with_for_update()
    )
    delivery = (await session.execute(stmt)).scalar_one_or_none()
    if delivery is None:
        raise NotFoundError("Webhook delivery not found.")
    if delivery.status not in {"failed", "cancelled"}:
        raise ConflictError("Only failed or cancelled deliveries can be retried.")

    previous_status = delivery.status
    previous_attempt_count = delivery.attempt_count
    now = datetime.now(UTC).replace(tzinfo=None)
    delivery.status = "pending"
    delivery.attempt_count = 0
    delivery.http_status_code = None
    delivery.last_error = None
    delivery.next_attempt_at = now
    delivery.delivered_at = None
    delivery.claimed_at = None
    delivery.claim_token = None
    delivery.updated_at = now
    await session.flush()
    await record_change(
        request=request,
        session=session,
        tenant=tenant,
        event_type="webhook.delivery.retried",
        resource_type="webhook_delivery",
        resource_id=delivery.id,
        details={
            "webhook_id": endpoint.id,
            "previous_status": previous_status,
            "previous_attempt_count": previous_attempt_count,
        },
    )
    return _delivery_out(delivery)


@router.patch(
    "/{webhook_id}",
    response_model=WebhookOut,
    dependencies=[Depends(require_scope("webhooks:write"))],
)
async def update_webhook(
    webhook_id: UUID,
    body: WebhookUpdate,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> WebhookOut:
    """Partially update a webhook endpoint (url, event types, active, description)."""
    m = await _get_owned(session, tenant, webhook_id)
    if body.is_active is True and body.secret is None and m.secret_ciphertext is None:
        raise InvalidRequestError(
            "Set a new signing secret before activating this endpoint."
        )
    changed_fields: list[str] = []

    if body.event_types is not None:
        _validate_event_types(body.event_types)
        m.event_types = body.event_types
        changed_fields.append("event_types")
    if body.url is not None:
        _validate_destination_url(body.url, tenant.environment)
        m.url = body.url
        changed_fields.append("url")
    if body.secret is not None:
        settings = getattr(request.app.state, "settings", None) or get_settings()
        secret = body.secret.get_secret_value()
        m.secret_hash = webhook_secret_digest(secret)
        m.secret_ciphertext = encrypt_webhook_secret(
            secret,
            settings.webhook_encryption_key or settings.auth_secret,
            m.id,
        )
        changed_fields.append("secret")
    if body.is_active is not None:
        m.is_active = body.is_active
        changed_fields.append("is_active")
    if body.description is not None:
        m.description = body.description
        changed_fields.append("description")

    await session.flush()
    await session.refresh(m)
    if changed_fields:
        await record_change(
            request=request,
            session=session,
            tenant=tenant,
            event_type="webhook.updated",
            resource_type="webhook_endpoint",
            resource_id=m.id,
            details={"changed_fields": sorted(changed_fields)},
        )
    return _webhook_out(m)


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
    dependencies=[Depends(require_scope("webhooks:write"))],
)
async def delete_webhook(
    webhook_id: UUID,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> Response:
    """Delete a webhook endpoint."""
    m = await _get_owned(session, tenant, webhook_id)
    await session.delete(m)
    await session.flush()
    await record_change(
        request=request,
        session=session,
        tenant=tenant,
        event_type="webhook.deleted",
        resource_type="webhook_endpoint",
        resource_id=m.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
