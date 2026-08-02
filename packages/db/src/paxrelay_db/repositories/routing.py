"""SQLAlchemy implementation of RouteRepository."""

from __future__ import annotations

from uuid import UUID

from paxrelay_domain import (
    RouteDecision,
    RouteScoreBreakdown,
    RoutingStrategy,
)
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_db.models.payments import RouteDecisionModel
from paxrelay_db.repositories._common import as_uuid, sid


def _to_decision(m: RouteDecisionModel) -> RouteDecision:
    return RouteDecision(
        id=as_uuid(m.id),
        tool_call_id=as_uuid(m.tool_call_id) if m.tool_call_id else None,
        provider_id=as_uuid(m.provider_id),
        service_id=as_uuid(m.service_id),
        service_version_id=as_uuid(m.service_version_id),
        score=m.score,
        strategy=RoutingStrategy(m.strategy),
        breakdown=RouteScoreBreakdown.model_validate(m.score_breakdown_json or {}),
        explanation=m.explanation,
        attempt_number=m.attempt_number,
        created_at=m.created_at,
    )


class SqlAlchemyRouteRepository:
    """Persists routing decisions for audit and explainability."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, decision: RouteDecision) -> RouteDecision:
        m = await self._session.get(RouteDecisionModel, sid(decision.id))
        if m is None:
            m = RouteDecisionModel(id=sid(decision.id))
            self._session.add(m)
        m.tool_call_id = sid(decision.tool_call_id) if decision.tool_call_id else None
        m.provider_id = sid(decision.provider_id)
        m.service_id = sid(decision.service_id)
        m.service_version_id = sid(decision.service_version_id)
        m.score = decision.score
        m.strategy = decision.strategy.value
        m.score_breakdown_json = decision.breakdown.model_dump(mode="json")
        m.explanation = decision.explanation
        m.attempt_number = decision.attempt_number
        await self._session.flush()
        await self._session.refresh(m)
        return _to_decision(m)

    async def get(self, route_id: UUID) -> RouteDecision | None:
        m = await self._session.get(RouteDecisionModel, sid(route_id))
        return _to_decision(m) if m is not None else None

    async def get_by_tool_call(self, tool_call_id: UUID) -> RouteDecision | None:
        """Return the routing decision recorded for a tool call."""
        stmt = select(RouteDecisionModel).where(
            RouteDecisionModel.tool_call_id == sid(tool_call_id)
        )
        m = (await self._session.execute(stmt)).scalars().first()
        return _to_decision(m) if m is not None else None
