"""Provider registration and lookup routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

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
async def list_providers(session: SessionDep, tenant: TenantDep) -> list[ProviderOut]:
    repo = SqlAlchemyProviderRepository(session)
    providers = await repo.list_active(tenant.organisation_id, tenant.project_id)
    return [_provider_out(p) for p in providers]


@router.get("/{provider_id}", response_model=ProviderOut)
async def get_provider(provider_id: UUID, session: SessionDep) -> ProviderOut:
    repo = SqlAlchemyProviderRepository(session)
    provider = await repo.get(provider_id)
    if provider is None:
        raise NotFoundError(f"Provider {provider_id} not found.")
    return _provider_out(provider)
