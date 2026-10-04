"""Abstract repository interfaces for the domain layer.

These are Protocol definitions — structural subtypes, not ABCs.
Implementations live in packages/db. The domain layer never imports
from SQLAlchemy, asyncpg, or any other storage library.

All methods are async to accommodate I/O-bound implementations.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID

from paxrelay_domain.agents.models import Agent, Wallet
from paxrelay_domain.payments.models import (
    ExecutionAttempt,
    Payment,
    PaymentIntent,
    Quote,
    ToolCall,
)
from paxrelay_domain.policies.models import Policy, PolicyAssignment
from paxrelay_domain.providers.models import (
    Provider,
    ProviderMetrics,
    Service,
    ServiceStatus,
    ServiceVersion,
)
from paxrelay_domain.receipts.models import ExecutionReceipt
from paxrelay_domain.routing.models import RouteDecision


# ---------------------------------------------------------------------------
# Agent repository
# ---------------------------------------------------------------------------


@runtime_checkable
class AgentRepository(Protocol):
    async def get(self, agent_id: UUID) -> Agent | None: ...
    async def get_by_slug(self, project_id: UUID, slug: str) -> Agent | None: ...
    async def list(
        self,
        organisation_id: UUID,
        project_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Agent]: ...
    async def save(self, agent: Agent) -> Agent: ...
    async def get_wallet(self, agent_id: UUID) -> Wallet | None: ...
    async def save_wallet(self, wallet: Wallet) -> Wallet: ...


# ---------------------------------------------------------------------------
# Provider repository
# ---------------------------------------------------------------------------


@runtime_checkable
class ProviderRepository(Protocol):
    async def get(self, provider_id: UUID) -> Provider | None: ...
    async def list_active(
        self,
        organisation_id: UUID,
        project_id: UUID,
        *,
        limit: int = 100,
    ) -> list[Provider]: ...
    async def save(self, provider: Provider) -> Provider: ...
    async def get_service(self, service_id: UUID) -> Service | None: ...
    async def list_services(self, provider_id: UUID) -> list[Service]: ...
    async def save_service(self, service: Service) -> Service: ...
    async def set_service_status(
        self,
        service_id: UUID,
        *,
        organisation_id: UUID,
        project_id: UUID,
        environment: str,
        status: ServiceStatus,
    ) -> tuple[Service, ServiceStatus] | None: ...
    async def get_service_version(self, version_id: UUID) -> ServiceVersion | None: ...
    async def save_service_version(self, version: ServiceVersion) -> ServiceVersion: ...
    async def get_metrics(self, service_id: UUID) -> ProviderMetrics | None: ...
    async def save_metrics(self, metrics: ProviderMetrics) -> ProviderMetrics: ...
    async def find_eligible_services(
        self,
        capability: str,
        organisation_id: UUID,
        project_id: UUID,
        environment: str,
    ) -> list[tuple[Service, ServiceVersion, ProviderMetrics]]: ...


# ---------------------------------------------------------------------------
# Policy repository
# ---------------------------------------------------------------------------


@runtime_checkable
class PolicyRepository(Protocol):
    async def get(self, policy_id: UUID) -> Policy | None: ...
    async def get_active_for_agent(self, agent_id: UUID) -> Policy | None: ...
    async def list(self, organisation_id: UUID, project_id: UUID) -> list[Policy]: ...
    async def save(self, policy: Policy) -> Policy: ...
    async def assign(self, assignment: PolicyAssignment) -> PolicyAssignment: ...
    async def lock_agent_for_budget(self, agent_id: UUID) -> bool: ...
    async def reserve_budget(self, agent: Agent, quote: Quote) -> None: ...
    async def get_daily_spend(self, agent_id: UUID) -> int: ...  # atomic integer
    async def get_monthly_spend(self, agent_id: UUID) -> int: ...  # atomic integer


# ---------------------------------------------------------------------------
# Tool call repository
# ---------------------------------------------------------------------------


@runtime_checkable
class ToolCallRepository(Protocol):
    async def get(self, tool_call_id: UUID) -> ToolCall | None: ...
    async def lock_idempotency_key(
        self,
        agent_id: UUID,
        idempotency_key: str,
    ) -> None: ...
    async def get_by_idempotency_key(
        self,
        agent_id: UUID,
        idempotency_key: str,
    ) -> ToolCall | None: ...
    async def list(
        self,
        organisation_id: UUID,
        project_id: UUID,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ToolCall]: ...
    async def save(self, call: ToolCall) -> ToolCall: ...
    async def get_attempts(self, tool_call_id: UUID) -> list[ExecutionAttempt]: ...
    async def save_attempt(self, attempt: ExecutionAttempt) -> ExecutionAttempt: ...


# ---------------------------------------------------------------------------
# Payment repository
# ---------------------------------------------------------------------------


@runtime_checkable
class PaymentRepository(Protocol):
    async def get_quote(self, quote_id: UUID) -> Quote | None: ...
    async def save_quote(self, quote: Quote) -> Quote: ...
    async def get_intent(self, intent_id: UUID) -> PaymentIntent | None: ...
    async def save_intent(self, intent: PaymentIntent) -> PaymentIntent: ...
    async def get(self, payment_id: UUID) -> Payment | None: ...
    async def get_by_tool_call(self, tool_call_id: UUID) -> Payment | None: ...
    async def save(self, payment: Payment) -> Payment: ...
    async def consume_nonce(
        self,
        quote_id: UUID,
        nonce: str,
        agent_id: UUID,
    ) -> bool: ...


# ---------------------------------------------------------------------------
# Receipt repository
# ---------------------------------------------------------------------------


@runtime_checkable
class ReceiptRepository(Protocol):
    async def get(self, receipt_id: UUID) -> ExecutionReceipt | None: ...
    async def get_by_tool_call(self, tool_call_id: UUID) -> ExecutionReceipt | None: ...
    async def save(self, receipt: ExecutionReceipt) -> ExecutionReceipt: ...


# ---------------------------------------------------------------------------
# Route decision repository
# ---------------------------------------------------------------------------


@runtime_checkable
class RouteRepository(Protocol):
    async def save(self, decision: RouteDecision) -> RouteDecision: ...
    async def get(self, route_id: UUID) -> RouteDecision | None: ...


# ---------------------------------------------------------------------------
# Audit log repository
# ---------------------------------------------------------------------------


@runtime_checkable
class AuditRepository(Protocol):
    async def record(
        self,
        event_type: str,
        actor_id: str,
        resource_type: str,
        resource_id: str,
        organisation_id: UUID,
        project_id: UUID,
        details: dict | None = None,
    ) -> None: ...
