"""
paxrelay_domain — Framework-independent business layer for PaxRelay.

This package must not import from:
  - FastAPI
  - SQLAlchemy
  - Redis
  - HTTP clients (httpx, requests)
  - Paxeer SDK implementations

Everything here is pure Pydantic + Python standard library.
"""

from paxrelay_domain.types import (
    PAXEER_CHAIN_ID,
    USDX_DECIMALS,
    CapabilitySlug,
    Currency,
    Environment,
    MonetaryAmount,
    PaymentScheme,
    WalletAddress,
)
from paxrelay_domain.agents.models import Agent, AgentStatus, Wallet
from paxrelay_domain.providers.models import (
    Provider,
    ProviderMetrics,
    ProviderStatus,
    PricingModel,
    Service,
    ServiceDelivery,
    ServiceHealth,
    ServicePricing,
    ServiceProtocol,
    ServiceStatus,
    ServiceVersion,
)
from paxrelay_domain.payments.models import (
    ExecutionAttempt,
    ExecutionState,
    Payment,
    PaymentIntent,
    PaymentState,
    Quote,
    RequestState,
    ToolCall,
)
from paxrelay_domain.policies.models import (
    Policy,
    PolicyAssignment,
    PolicyDecision,
    PolicyEvaluationRequest,
    PolicyEvaluationResult,
    PolicyMode,
    PolicyRules,
)
from paxrelay_domain.routing.models import (
    RouteConstraints,
    RouteDecision,
    RouteRequest,
    RouteScoreBreakdown,
    RoutingStrategy,
)
from paxrelay_domain.receipts.models import (
    ExecutionReceipt,
    ReceiptExecutionSummary,
    ReceiptPaymentSummary,
    ReceiptRoutingSummary,
)
from paxrelay_domain.events.models import (
    DomainEvent,
    EventType,
    agent_created,
    call_succeeded,
    payment_verified,
    policy_violation,
    settlement_mismatch,
)
from paxrelay_domain.interfaces.repositories import (
    AgentRepository,
    AuditRepository,
    PaymentRepository,
    PolicyRepository,
    ProviderRepository,
    ReceiptRepository,
    RouteRepository,
    ToolCallRepository,
)

__all__ = [
    # types
    "PAXEER_CHAIN_ID",
    "USDX_DECIMALS",
    "CapabilitySlug",
    "Currency",
    "Environment",
    "MonetaryAmount",
    "PaymentScheme",
    "WalletAddress",
    # agents
    "Agent",
    "AgentStatus",
    "Wallet",
    # providers
    "Provider",
    "ProviderMetrics",
    "ProviderStatus",
    "PricingModel",
    "Service",
    "ServiceDelivery",
    "ServiceHealth",
    "ServicePricing",
    "ServiceProtocol",
    "ServiceStatus",
    "ServiceVersion",
    # payments
    "ExecutionAttempt",
    "ExecutionState",
    "Payment",
    "PaymentIntent",
    "PaymentState",
    "Quote",
    "RequestState",
    "ToolCall",
    # policies
    "Policy",
    "PolicyAssignment",
    "PolicyDecision",
    "PolicyEvaluationRequest",
    "PolicyEvaluationResult",
    "PolicyMode",
    "PolicyRules",
    # routing
    "RouteConstraints",
    "RouteDecision",
    "RouteRequest",
    "RouteScoreBreakdown",
    "RoutingStrategy",
    # receipts
    "ExecutionReceipt",
    "ReceiptExecutionSummary",
    "ReceiptPaymentSummary",
    "ReceiptRoutingSummary",
    # events
    "DomainEvent",
    "EventType",
    "agent_created",
    "call_succeeded",
    "payment_verified",
    "policy_violation",
    "settlement_mismatch",
    # interfaces
    "AgentRepository",
    "AuditRepository",
    "PaymentRepository",
    "PolicyRepository",
    "ProviderRepository",
    "ReceiptRepository",
    "RouteRepository",
    "ToolCallRepository",
]
