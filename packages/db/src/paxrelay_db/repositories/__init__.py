"""Concrete SQLAlchemy repository implementations.

Each class satisfies the corresponding Protocol from
``paxrelay_domain.interfaces.repositories``. Construct them with an
``AsyncSession`` (e.g. the ``get_session`` FastAPI dependency).
"""

from paxrelay_db.repositories.agents import SqlAlchemyAgentRepository
from paxrelay_db.repositories.audit import SqlAlchemyAuditRepository
from paxrelay_db.repositories.payments import (
    SqlAlchemyPaymentRepository,
    SqlAlchemyToolCallRepository,
)
from paxrelay_db.repositories.policies import SqlAlchemyPolicyRepository
from paxrelay_db.repositories.providers import SqlAlchemyProviderRepository
from paxrelay_db.repositories.receipts import SqlAlchemyReceiptRepository
from paxrelay_db.repositories.routing import SqlAlchemyRouteRepository

__all__ = [
    "SqlAlchemyAgentRepository",
    "SqlAlchemyAuditRepository",
    "SqlAlchemyPaymentRepository",
    "SqlAlchemyPolicyRepository",
    "SqlAlchemyProviderRepository",
    "SqlAlchemyReceiptRepository",
    "SqlAlchemyRouteRepository",
    "SqlAlchemyToolCallRepository",
]
