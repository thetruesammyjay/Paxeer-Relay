"""SQLAlchemy implementation of AgentRepository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_domain import Agent, AgentStatus, Environment, Wallet
from paxrelay_db.models.agents import AgentModel, WalletModel
from paxrelay_db.repositories._common import as_uuid, sid


def _to_agent(m: AgentModel) -> Agent:
    return Agent(
        id=as_uuid(m.id),
        name=m.name,
        slug=m.slug,
        organisation_id=as_uuid(m.organisation_id),
        project_id=as_uuid(m.project_id),
        environment=Environment(m.environment),
        wallet_address=m.wallet_address,
        status=AgentStatus(m.status),
        description=m.description,
        metadata=m.extra_metadata or {},
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_wallet(m: WalletModel) -> Wallet:
    return Wallet(
        id=as_uuid(m.id),
        agent_id=as_uuid(m.agent_id),
        address=m.address,
        is_primary=m.is_primary,
        label=m.label,
        created_at=m.created_at,
    )


class SqlAlchemyAgentRepository:
    """Persists :class:`Agent` and :class:`Wallet` aggregates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, agent_id: UUID) -> Agent | None:
        m = await self._session.get(AgentModel, sid(agent_id))
        return _to_agent(m) if m is not None else None

    async def get_by_slug(self, project_id: UUID, slug: str) -> Agent | None:
        stmt = select(AgentModel).where(
            AgentModel.project_id == sid(project_id),
            AgentModel.slug == slug,
            AgentModel.deleted_at.is_(None),
        )
        m = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_agent(m) if m is not None else None

    async def list(
        self,
        organisation_id: UUID,
        project_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
    ) -> list[Agent]:
        stmt = select(AgentModel).where(
            AgentModel.organisation_id == sid(organisation_id),
            AgentModel.project_id == sid(project_id),
            AgentModel.deleted_at.is_(None),
        )
        if status is not None:
            stmt = stmt.where(AgentModel.status == status)
        if search is not None:
            pattern = f"%{search}%"
            stmt = stmt.where(
                AgentModel.name.ilike(pattern) | AgentModel.slug.ilike(pattern)
            )
        stmt = (
            stmt.order_by(AgentModel.created_at.desc()).limit(limit).offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_agent(m) for m in rows]

    async def save(self, agent: Agent) -> Agent:
        m = await self._session.get(AgentModel, sid(agent.id))
        if m is None:
            m = AgentModel(id=sid(agent.id))
            self._session.add(m)
        m.name = agent.name
        m.slug = agent.slug
        m.organisation_id = sid(agent.organisation_id)
        m.project_id = sid(agent.project_id)
        m.environment = agent.environment.value
        m.wallet_address = agent.wallet_address
        m.status = agent.status.value
        m.description = agent.description
        m.extra_metadata = dict(agent.metadata)
        await self._session.flush()
        await self._session.refresh(m)
        return _to_agent(m)

    async def get_wallet(self, agent_id: UUID) -> Wallet | None:
        stmt = (
            select(WalletModel)
            .where(WalletModel.agent_id == sid(agent_id))
            .order_by(WalletModel.is_primary.desc(), WalletModel.created_at.asc())
        )
        m = (await self._session.execute(stmt)).scalars().first()
        return _to_wallet(m) if m is not None else None

    async def save_wallet(self, wallet: Wallet) -> Wallet:
        m = await self._session.get(WalletModel, sid(wallet.id))
        if m is None:
            m = WalletModel(id=sid(wallet.id))
            self._session.add(m)
        m.agent_id = sid(wallet.agent_id)
        m.address = wallet.address
        m.is_primary = wallet.is_primary
        m.label = wallet.label
        await self._session.flush()
        await self._session.refresh(m)
        return _to_wallet(m)
