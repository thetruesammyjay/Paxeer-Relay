"""SQLAlchemy implementation of AuditRepository."""

from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_db.models.executions import AuditLogModel
from paxrelay_db.repositories._common import sid


class SqlAlchemyAuditRepository:
    """Append-only audit log writer."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        event_type: str,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        organisation_id: UUID,
        project_id: UUID,
        details: dict | None = None,
    ) -> None:
        m = AuditLogModel(
            id=str(uuid.uuid4()),
            organisation_id=sid(organisation_id),
            project_id=sid(project_id),
            event_type=event_type,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
        )
        self._session.add(m)
        await self._session.flush()
