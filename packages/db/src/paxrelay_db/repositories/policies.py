"""SQLAlchemy implementation of PolicyRepository.

Policy rules are stored as a JSON blob (``rules_json``) that round-trips the
frozen :class:`PolicyRules` domain object. Daily/monthly spend is aggregated
from verified payments and unexpired quote reservations.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_domain import (
    Agent,
    Environment,
    Policy,
    PolicyAssignment,
    PolicyMode,
    PolicyRules,
    Quote,
)
from paxrelay_db.models.agents import AgentModel
from paxrelay_db.models.budget import BudgetReservationModel
from paxrelay_db.models.payments import PaymentModel
from paxrelay_db.models.policies import PolicyAssignmentModel, PolicyModel
from paxrelay_db.repositories._common import as_uuid, sid


def _to_policy(m: PolicyModel) -> Policy:
    return Policy(
        id=as_uuid(m.id),
        organisation_id=as_uuid(m.organisation_id),
        project_id=as_uuid(m.project_id),
        environment=Environment(m.environment),
        name=m.name,
        description=m.description,
        mode=PolicyMode(m.mode),
        rules=PolicyRules.model_validate(m.rules_json or {}),
        version=m.version,
        is_active=m.is_active,
        activated_at=m.activated_at,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_assignment(m: PolicyAssignmentModel) -> PolicyAssignment:
    return PolicyAssignment(
        id=as_uuid(m.id),
        agent_id=as_uuid(m.agent_id),
        policy_id=as_uuid(m.policy_id),
        assigned_at=m.created_at,
        assigned_by=as_uuid(m.assigned_by) if m.assigned_by else None,
    )


class SqlAlchemyPolicyRepository:
    """Persists policies and their assignments to agents."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, policy_id: UUID) -> Policy | None:
        stmt = select(PolicyModel).where(
            PolicyModel.id == sid(policy_id), PolicyModel.deleted_at.is_(None)
        )
        m = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_policy(m) if m is not None else None

    async def get_active_for_agent(self, agent_id: UUID) -> Policy | None:
        stmt = (
            select(PolicyModel)
            .join(
                PolicyAssignmentModel,
                PolicyAssignmentModel.policy_id == PolicyModel.id,
            )
            .where(
                PolicyAssignmentModel.agent_id == sid(agent_id),
                PolicyModel.is_active.is_(True),
            )
            .order_by(PolicyModel.version.desc())
        )
        m = (await self._session.execute(stmt)).scalars().first()
        return _to_policy(m) if m is not None else None

    async def list(
        self,
        organisation_id: UUID,
        project_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
        mode: str | None = None,
        is_active: bool | None = None,
        search: str | None = None,
        environment: str | None = None,
    ) -> list[Policy]:
        stmt = select(PolicyModel).where(
            PolicyModel.organisation_id == sid(organisation_id),
            PolicyModel.project_id == sid(project_id),
            PolicyModel.deleted_at.is_(None),
        )
        if environment is not None:
            stmt = stmt.where(PolicyModel.environment == environment)
        if mode is not None:
            stmt = stmt.where(PolicyModel.mode == mode)
        if is_active is not None:
            stmt = stmt.where(PolicyModel.is_active.is_(is_active))
        if search is not None:
            stmt = stmt.where(PolicyModel.name.ilike(f"%{search}%"))
        stmt = (
            stmt.order_by(PolicyModel.created_at.desc()).limit(limit).offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_policy(m) for m in rows]

    async def save(self, policy: Policy) -> Policy:
        m = await self._session.get(PolicyModel, sid(policy.id))
        if m is None:
            m = PolicyModel(id=sid(policy.id))
            self._session.add(m)
        m.organisation_id = sid(policy.organisation_id)
        m.project_id = sid(policy.project_id)
        m.environment = policy.environment.value
        m.name = policy.name
        m.description = policy.description
        m.mode = policy.mode.value
        m.version = policy.version
        m.is_active = policy.is_active
        m.activated_at = policy.activated_at
        m.rules_json = policy.rules.model_dump(mode="json")
        await self._session.flush()
        await self._session.refresh(m)
        return _to_policy(m)

    async def assign(self, assignment: PolicyAssignment) -> PolicyAssignment:
        m = await self._session.get(PolicyAssignmentModel, sid(assignment.id))
        if m is None:
            m = PolicyAssignmentModel(id=sid(assignment.id))
            self._session.add(m)
        m.agent_id = sid(assignment.agent_id)
        m.policy_id = sid(assignment.policy_id)
        m.assigned_by = sid(assignment.assigned_by) if assignment.assigned_by else None
        await self._session.flush()
        await self._session.refresh(m)
        return _to_assignment(m)

    async def lock_agent_for_budget(self, agent_id: UUID) -> bool:
        """Serialize budget checks and reservations for one agent."""
        stmt = (
            select(AgentModel.id)
            .where(AgentModel.id == sid(agent_id), AgentModel.deleted_at.is_(None))
            .with_for_update()
        )
        locked = (await self._session.execute(stmt)).scalar_one_or_none() is not None
        if not locked:
            return False

        expire_stmt = (
            update(BudgetReservationModel)
            .where(
                BudgetReservationModel.agent_id == sid(agent_id),
                BudgetReservationModel.status == "active",
                BudgetReservationModel.expires_at <= datetime.utcnow(),
            )
            .values(status="expired")
        )
        await self._session.execute(expire_stmt)
        return True

    async def reserve_budget(self, agent: Agent, quote: Quote) -> None:
        """Hold the quote amount against this agent's budget until expiry."""
        reservation = BudgetReservationModel(
            organisation_id=sid(agent.organisation_id),
            project_id=sid(agent.project_id),
            environment=agent.environment.value,
            agent_id=sid(agent.id),
            quote_id=sid(quote.id),
            amount_atomic=quote.amount.amount_atomic,
            currency=quote.amount.currency.value,
            status="active",
            expires_at=quote.expires_at,
        )
        self._session.add(reservation)
        await self._session.flush()

    async def _spend_since(self, agent_id: UUID, since: datetime) -> int:
        now = datetime.utcnow()
        stmt = select(func.coalesce(func.sum(PaymentModel.amount_atomic), 0)).where(
            PaymentModel.agent_id == sid(agent_id),
            PaymentModel.state.in_(("verified", "settled_layerx", "anchored_l1")),
            PaymentModel.created_at >= since,
        )
        paid = (await self._session.execute(stmt)).scalar_one()
        reservation_stmt = select(
            func.coalesce(func.sum(BudgetReservationModel.amount_atomic), 0)
        ).where(
            BudgetReservationModel.agent_id == sid(agent_id),
            BudgetReservationModel.status == "active",
            BudgetReservationModel.created_at >= since,
            BudgetReservationModel.expires_at > now,
        )
        reserved = (await self._session.execute(reservation_stmt)).scalar_one()
        return int(paid or 0) + int(reserved or 0)

    async def get_daily_spend(self, agent_id: UUID) -> int:
        return await self._spend_since(agent_id, datetime.utcnow() - timedelta(days=1))

    async def get_monthly_spend(self, agent_id: UUID) -> int:
        return await self._spend_since(
            agent_id,
            datetime.utcnow() - timedelta(days=30),
        )
