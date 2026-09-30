"""Batch operations — bulk create agents and providers.

Each item is created inside its own SAVEPOINT (``begin_nested``) so a single
failure (e.g. a duplicate slug) rolls back only that item and reports an error,
while the rest of the batch still succeeds.  The outer request transaction
commits the successful items together.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.exc import IntegrityError

from paxrelay_domain import Agent, Provider
from paxrelay_db.repositories import (
    SqlAlchemyAgentRepository,
    SqlAlchemyProviderRepository,
)

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.audit import record_change
from paxrelay_api.routes.agents import _agent_out
from paxrelay_api.routes.providers import _provider_out
from paxrelay_api.schemas import (
    BatchAgentCreate,
    BatchAgentResponse,
    BatchAgentResult,
    BatchProviderCreate,
    BatchProviderResponse,
    BatchProviderResult,
)
from paxrelay_api.security.authorization import require_scope

router = APIRouter(prefix="/batch", tags=["batch"])


@router.post(
    "/agents",
    response_model=BatchAgentResponse,
    status_code=status.HTTP_207_MULTI_STATUS,
    dependencies=[
        Depends(require_scope("batch:write")),
        Depends(require_scope("agents:write")),
    ],
)
async def batch_create_agents(
    body: BatchAgentCreate,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> BatchAgentResponse:
    """Create up to 100 agents; each item succeeds or fails independently."""
    repo = SqlAlchemyAgentRepository(session)
    results: list[BatchAgentResult] = []
    success = 0

    for item in body.agents:
        # Proactive slug conflict check for a clean error message.
        existing = await repo.get_by_slug(
            tenant.project_id, item.slug, tenant.environment
        )
        if existing is not None:
            results.append(
                BatchAgentResult(
                    success=False, error=f"Agent slug '{item.slug}' already exists."
                )
            )
            continue
        try:
            async with session.begin_nested():
                agent = Agent(
                    name=item.name,
                    slug=item.slug,
                    organisation_id=tenant.organisation_id,
                    project_id=tenant.project_id,
                    environment=tenant.environment,
                    wallet_address=item.wallet_address,
                    description=item.description,
                )
                saved = await repo.save(agent)
                await record_change(
                    request=request,
                    session=session,
                    tenant=tenant,
                    event_type="agent.created",
                    resource_type="agent",
                    resource_id=saved.id,
                    details={"slug": saved.slug, "batch": True},
                )
            results.append(BatchAgentResult(success=True, agent=_agent_out(saved)))
            success += 1
        except IntegrityError:
            results.append(
                BatchAgentResult(success=False, error="The agent conflicts with an existing record.")
            )
        except Exception:  # noqa: BLE001 — do not expose database/internal details
            results.append(
                BatchAgentResult(success=False, error="The agent could not be created.")
            )

    return BatchAgentResponse(
        results=results,
        success_count=success,
        failure_count=len(results) - success,
    )


@router.post(
    "/providers",
    response_model=BatchProviderResponse,
    status_code=status.HTTP_207_MULTI_STATUS,
    dependencies=[
        Depends(require_scope("batch:write")),
        Depends(require_scope("providers:write")),
    ],
)
async def batch_create_providers(
    body: BatchProviderCreate,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> BatchProviderResponse:
    """Create up to 100 providers; each item succeeds or fails independently."""
    repo = SqlAlchemyProviderRepository(session)
    results: list[BatchProviderResult] = []
    success = 0

    for item in body.providers:
        try:
            async with session.begin_nested():
                provider = Provider(
                    name=item.name,
                    slug=item.slug,
                    organisation_id=tenant.organisation_id,
                    project_id=tenant.project_id,
                    environment=tenant.environment,
                    wallet_address=item.wallet_address,
                    description=item.description,
                    website_url=item.website_url,
                )
                saved = await repo.save(provider)
                await record_change(
                    request=request,
                    session=session,
                    tenant=tenant,
                    event_type="provider.created",
                    resource_type="provider",
                    resource_id=saved.id,
                    details={"slug": saved.slug, "batch": True},
                )
            results.append(BatchProviderResult(success=True, provider=_provider_out(saved)))
            success += 1
        except IntegrityError:
            results.append(
                BatchProviderResult(success=False, error="The provider conflicts with an existing record.")
            )
        except Exception:  # noqa: BLE001 — do not expose database/internal details
            results.append(
                BatchProviderResult(success=False, error="The provider could not be created.")
            )

    return BatchProviderResponse(
        results=results,
        success_count=success,
        failure_count=len(results) - success,
    )
