"""Agent registration and lookup routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

from paxrelay_domain import Agent
from paxrelay_db.repositories import SqlAlchemyAgentRepository

from paxrelay_api.dependencies import SessionDep, TenantDep
from paxrelay_api.exceptions import NotFoundError
from paxrelay_api.schemas import AgentCreate, AgentOut, WalletOut

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


@router.post("", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
async def create_agent(
    body: AgentCreate,
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
    return _agent_out(saved)


@router.get("", response_model=list[AgentOut])
async def list_agents(session: SessionDep, tenant: TenantDep) -> list[AgentOut]:
    repo = SqlAlchemyAgentRepository(session)
    agents = await repo.list(tenant.organisation_id, tenant.project_id)
    return [_agent_out(a) for a in agents]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: UUID, session: SessionDep) -> AgentOut:
    repo = SqlAlchemyAgentRepository(session)
    agent = await repo.get(agent_id)
    if agent is None:
        raise NotFoundError(f"Agent {agent_id} not found.")
    return _agent_out(agent)


@router.get("/{agent_id}/wallet", response_model=WalletOut)
async def get_agent_wallet(agent_id: UUID, session: SessionDep) -> WalletOut:
    repo = SqlAlchemyAgentRepository(session)
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
