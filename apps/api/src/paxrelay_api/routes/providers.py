"""Provider registration and lookup routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, status

from paxrelay_domain import Provider
from paxrelay_db.repositories import SqlAlchemyProviderRepository

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.exceptions import NotFoundError
from paxrelay_api.schemas import ProviderCreate, ProviderOut

router = APIRouter(prefix="/providers", tags=["providers"])


def _provider_out(p: Provider) -> ProviderOut:
    return ProviderOut(
        id=p.id,
        name=p.name,
        slug=p.slug,
        organisation_id=p.organisation_id,
        project_id=p.project_id,
        environment=p.environment.value,
        wallet_address=p.wallet_address,
        status=p.status.value,
        is_verified=p.is_verified,
        description=p.description,
    )


@router.post("", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
async def create_provider(
    body: ProviderCreate,
    session: SessionDep,
    tenant: TenantDep,
) -> ProviderOut:
    repo = SqlAlchemyProviderRepository(session)
    provider = Provider(
        name=body.name,
        slug=body.slug,
        organisation_id=tenant.organisation_id,
        project_id=tenant.project_id,
        environment=tenant.environment,
        wallet_address=body.wallet_address,
        description=body.description,
        website_url=body.website_url,
    )
    saved = await repo.save(provider)
    return _provider_out(saved)


@router.get("", response_model=list[ProviderOut])
async def list_providers(
    session: SessionDep,
    tenant: TenantDep,
    status: str | None = Query(None, description="Filter by provider status"),
    search: str | None = Query(None, description="Case-insensitive match on name or slug"),
    limit: int = Query(100, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[ProviderOut]:
    repo = SqlAlchemyProviderRepository(session)
    providers = await repo.list(
        tenant.organisation_id,
        tenant.project_id,
        limit=limit,
        offset=offset,
        status=status,
        search=search,
    )
    return [_provider_out(p) for p in providers]


@router.get("/{provider_id}", response_model=ProviderOut)
async def get_provider(provider_id: UUID, session: SessionDep, tenant: TenantDep) -> ProviderOut:
    repo = SqlAlchemyProviderRepository(session)
    provider = await repo.get(provider_id)
    # Treat a cross-tenant resource as not-found to avoid information leakage.
    if provider is None or provider.organisation_id != tenant.organisation_id:
        raise NotFoundError(f"Provider {provider_id} not found.")
    return _provider_out(provider)
