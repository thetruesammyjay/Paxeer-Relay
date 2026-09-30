"""Agent registration and lookup routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, status

from paxrelay_domain import Agent
from paxrelay_db.repositories import SqlAlchemyAgentRepository

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.audit import record_change
from paxrelay_api.exceptions import NotFoundError
from paxrelay_api.schemas import AgentCreate, AgentOut, WalletOut
from paxrelay_api.security.authorization import require_scope
from paxrelay_api.tenant import tenant_owns

router = APIRouter(prefix="/agents", tags=["agents"])


def _agent_out(agent: Agent) -> AgentOut:
    return AgentOut(
        id=agent.id,
        name=agent.name,
        slug=agent.slug,
        organisation_id=agent.organisation_id,
        project_id=agent.project_id,
        environment=agent.environment.value,
        wallet_address=agent.wallet_address,
        status=agent.status.value,
        description=agent.description,
        created_at=agent.created_at,
    )


@router.post(
    "",
    response_model=AgentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_scope("agents:write"))],
)
async def create_agent(
    body: AgentCreate,
    request: Request,
    session: SessionDep,
    tenant: TenantDep,
) -> AgentOut:
    repo = SqlAlchemyAgentRepository(session)
    agent = Agent(
        name=body.name,
        slug=body.slug,
        organisation_id=tenant.organisation_id,
        project_id=tenant.project_id,
        environment=tenant.environment,
        wallet_address=body.wallet_address,
        description=body.description,
    )
    saved = await repo.save(agent)
    await record_change(
        request=request,
        session=session,
        tenant=tenant,
        event_type="agent.created",
        resource_type="agent",
        resource_id=saved.id,
        details={"slug": saved.slug},
    )
    return _agent_out(saved)


@router.get(
    "",
    response_model=list[AgentOut],
    dependencies=[Depends(require_scope("agents:read"))],
)
async def list_agents(
    session: SessionDep,
    tenant: TenantDep,
    status: str | None = Query(None, description="Filter by agent status"),
    search: str | None = Query(None, description="Case-insensitive match on name or slug"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[AgentOut]:
    repo = SqlAlchemyAgentRepository(session)
    agents = await repo.list(
        tenant.organisation_id,
        tenant.project_id,
        limit=limit,
        offset=offset,
        status=status,
        search=search,
        environment=tenant.environment,
    )
    return [_agent_out(a) for a in agents]


@router.get(
    "/{agent_id}",
    response_model=AgentOut,
    dependencies=[Depends(require_scope("agents:read"))],
)
async def get_agent(agent_id: UUID, session: SessionDep, tenant: TenantDep) -> AgentOut:
    repo = SqlAlchemyAgentRepository(session)
    agent = await repo.get(agent_id)
    # Treat a cross-tenant resource as not-found to avoid information leakage.
    if agent is None or not tenant_owns(tenant, agent):
        raise NotFoundError(f"Agent {agent_id} not found.")
    return _agent_out(agent)


@router.get(
    "/{agent_id}/wallet",
    response_model=WalletOut,
    dependencies=[Depends(require_scope("agents:read"))],
)
async def get_agent_wallet(agent_id: UUID, session: SessionDep, tenant: TenantDep) -> WalletOut:
    repo = SqlAlchemyAgentRepository(session)
    # Verify ownership before reading the wallet.
    agent = await repo.get(agent_id)
    if agent is None or not tenant_owns(tenant, agent):
        raise NotFoundError(f"Agent {agent_id} not found.")
    wallet = await repo.get_wallet(agent_id)
    if wallet is None:
        raise NotFoundError(f"No wallet found for agent {agent_id}.")
    return WalletOut(
        id=wallet.id,
        agent_id=wallet.agent_id,
        address=wallet.address,
        is_primary=wallet.is_primary,
        label=wallet.label,
    )
