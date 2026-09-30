"""Service publishing and lookup routes.

Publishing a service also creates its immutable service version and the
initial provider metrics row (defaults to perfect scores until health checks
measure real values), so routing has something to score immediately.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from paxrelay_domain import (
    ProviderMetrics,
    Service,
    ServiceDelivery,
    ServiceHealth,
    ServicePricing,
    ServiceProtocol,
    ServiceVersion,
)
from paxrelay_db.repositories import SqlAlchemyProviderRepository

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.audit import record_change
from paxrelay_api.exceptions import NotFoundError
from paxrelay_api.schemas import ServiceCreate, ServiceOut
from paxrelay_api.security.authorization import require_scope
from paxrelay_api.tenant import tenant_owns

router = APIRouter(prefix="/services", tags=["services"])


def _service_out(s: Service) -> ServiceOut:
    price = s.pricing.price_per_call
    return ServiceOut(
        id=s.id,
        provider_id=s.provider_id,
        name=s.name,
        slug=s.slug,
        capability=s.capability,
        protocols=[p.value for p in s.protocols],
        status=s.status.value,
        base_url=s.base_url,
        price_per_call=(
            {
                "amount_atomic": price.amount_atomic,
                "currency": price.currency.value,
                "decimals": price.decimals,
            }
            if price
            else None
        ),
        description=s.description,
    )


@router.post(
    "/providers/{provider_id}",
    response_model=ServiceOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("services:write"))],
)
async def publish_service(
    provider_id: UUID,
    body: ServiceCreate,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> ServiceOut:
    repo = SqlAlchemyProviderRepository(session)
    provider = await repo.get(provider_id)
    # Reject cross-tenant provider references — treat as not-found to avoid
    # leaking the existence of providers owned by other organisations.
    if provider is None or not tenant_owns(tenant, provider):
        raise NotFoundError(f"Provider {provider_id} not found.")

    service = Service(
        provider_id=provider_id,
        organisation_id=tenant.organisation_id,
        project_id=tenant.project_id,
        environment=tenant.environment,
        name=body.name,
        slug=body.slug,
        capability=body.capability,
        protocols=[ServiceProtocol(p) for p in body.protocols],
        pricing=ServicePricing(
            price_per_call={
                "amount_atomic": body.price_per_call.amount_atomic,
                "currency": body.price_per_call.currency,
                "decimals": body.price_per_call.decimals,
            }
        ),
        delivery=ServiceDelivery(),
        health=ServiceHealth(),
        base_url=body.base_url,
        description=body.description,
    )
    saved = await repo.save_service(service)

    # Immutable service version snapshot (the routing target).
    version = ServiceVersion(
        service_id=saved.id,
        provider_id=provider_id,
        version=body.version,
        capability=body.capability,
        pricing=service.pricing,
        delivery=service.delivery,
        endpoint_url=body.endpoint_url,
    )
    await repo.save_service_version(version)

    # Default metrics so routing can score the new service immediately.
    await repo.save_metrics(
        ProviderMetrics(
            service_id=saved.id,
            provider_id=provider_id,
            reputation_score=1.0,
            success_rate=1.0,
            avg_latency_ms=0.0,
            availability_score=1.0,
            health_check_passing=True,
        )
    )
    await record_change(
        request=request,
        session=session,
        tenant=tenant,
        event_type="service.published",
        resource_type="service",
        resource_id=saved.id,
        details={"provider_id": str(provider_id), "slug": saved.slug},
    )
    return _service_out(saved)


@router.get(
    "",
    response_model=list[ServiceOut],
    dependencies=[Depends(require_scope("services:read"))],
)
async def list_services(session: SessionDep, tenant: TenantDep) -> list[ServiceOut]:
    repo = SqlAlchemyProviderRepository(session)
    services = await repo.list_services_by_tenant(
        tenant.organisation_id,
        tenant.project_id,
        environment=tenant.environment,
    )
    return [_service_out(s) for s in services]


@router.get(
    "/{service_id}",
    response_model=ServiceOut,
    dependencies=[Depends(require_scope("services:read"))],
)
async def get_service(service_id: UUID, session: SessionDep, tenant: TenantDep) -> ServiceOut:
    repo = SqlAlchemyProviderRepository(session)
    service = await repo.get_service(service_id)
    # Treat a cross-tenant resource as not-found to avoid information leakage.
    if service is None or not tenant_owns(tenant, service):
        raise NotFoundError(f"Service {service_id} not found.")
    return _service_out(service)
