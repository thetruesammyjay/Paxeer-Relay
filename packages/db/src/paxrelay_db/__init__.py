"""DB package — exports all ORM models, session factory, and base."""

from paxrelay_db.base import Base, SoftDeleteMixin, TenantMixin, TimestampMixin
from paxrelay_db.session import (
    close_database,
    configure_database,
    get_engine,
    get_session,
)
from paxrelay_db.urls import normalize_async_database_url
from paxrelay_db.models.users import Membership, Organisation, User
from paxrelay_db.models.projects import ApiKey, Project
from paxrelay_db.models.agents import AgentModel, WalletModel
from paxrelay_db.models.budget import BudgetReservationModel
from paxrelay_db.models.analytics import (
    AnalyticsRefreshStateModel,
    AnalyticsSpendRollupModel,
)
from paxrelay_db.models.policies import PolicyAssignmentModel, PolicyModel, PolicyRuleModel
from paxrelay_db.models.providers import (
    ProviderMetricsModel,
    ProviderModel,
    ServiceModel,
    ServiceVersionModel,
)
from paxrelay_db.models.payments import (
    PaymentIntentModel,
    PaymentModel,
    QuoteModel,
    RouteDecisionModel,
    ToolCallModel,
)
from paxrelay_db.models.executions import (
    ApprovalRequestModel,
    AuditLogModel,
    ExecutionAttemptModel,
    ExecutionReceiptModel,
    OutboxEventModel,
    SettlementRecordModel,
    WebhookDeliveryModel,
    WebhookEndpointModel,
)

__all__ = [
    # Base
    "Base",
    "SoftDeleteMixin",
    "TenantMixin",
    "TimestampMixin",
    # Session
    "close_database",
    "configure_database",
    "get_engine",
    "get_session",
    "normalize_async_database_url",
    # Users / Orgs
    "Membership",
    "Organisation",
    "User",
    # Projects
    "ApiKey",
    "Project",
    # Agents
    "AgentModel",
    "WalletModel",
    "BudgetReservationModel",
    "AnalyticsSpendRollupModel",
    "AnalyticsRefreshStateModel",
    # Policies
    "PolicyAssignmentModel",
    "PolicyModel",
    "PolicyRuleModel",
    # Providers
    "ProviderMetricsModel",
    "ProviderModel",
    "ServiceModel",
    "ServiceVersionModel",
    # Payments
    "PaymentIntentModel",
    "PaymentModel",
    "QuoteModel",
    "RouteDecisionModel",
    "ToolCallModel",
    # Executions / Receipts / Audit
    "ApprovalRequestModel",
    "AuditLogModel",
    "ExecutionAttemptModel",
    "ExecutionReceiptModel",
    "OutboxEventModel",
    "SettlementRecordModel",
    "WebhookDeliveryModel",
    "WebhookEndpointModel",
]
