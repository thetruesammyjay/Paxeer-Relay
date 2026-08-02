"""Domain events — immutable records of significant state transitions.

Every domain event is identified by an event_id, typed via event_type,
and stamped with occurred_at. Consumers must treat these as immutable.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """All event types emitted by PaxRelay, matching the README list exactly."""

    # Agent events
    AGENT_CREATED = "agent.created"
    AGENT_PAUSED = "agent.paused"
    AGENT_RESUMED = "agent.resumed"
    AGENT_REVOKED = "agent.revoked"
    AGENT_BUDGET_WARNING = "agent.budget.warning"
    AGENT_BUDGET_EXHAUSTED = "agent.budget.exhausted"

    # Provider events
    PROVIDER_CREATED = "provider.created"
    PROVIDER_VERIFIED = "provider.verified"
    PROVIDER_UNHEALTHY = "provider.unhealthy"
    PROVIDER_RECOVERED = "provider.recovered"

    # Service events
    SERVICE_PUBLISHED = "service.published"
    SERVICE_DISABLED = "service.disabled"

    # Policy events
    POLICY_CREATED = "policy.created"
    POLICY_UPDATED = "policy.updated"
    POLICY_VIOLATION = "policy.violation"

    # Approval events
    APPROVAL_REQUESTED = "approval.requested"
    APPROVAL_APPROVED = "approval.approved"
    APPROVAL_REJECTED = "approval.rejected"
    APPROVAL_EXPIRED = "approval.expired"

    # Payment events
    PAYMENT_QUOTE_CREATED = "payment.quote.created"
    PAYMENT_SUBMITTED = "payment.submitted"
    PAYMENT_VERIFIED = "payment.verified"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_SETTLED_LAYERX = "payment.settled.layerx"
    PAYMENT_ANCHORED_L1 = "payment.anchored.l1"

    # Tool call events
    CALL_CREATED = "call.created"
    CALL_EXECUTING = "call.executing"
    CALL_SUCCEEDED = "call.succeeded"
    CALL_FAILED = "call.failed"

    # Receipt events
    RECEIPT_CREATED = "receipt.created"
    RECEIPT_VERIFIED = "receipt.verified"

    # Settlement events
    SETTLEMENT_RECONCILED = "settlement.reconciled"
    SETTLEMENT_MISMATCH = "settlement.mismatch"


class DomainEvent(BaseModel):
    """Base class for all PaxRelay domain events."""

    model_config = {"frozen": True}

    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    organisation_id: UUID | None = None
    project_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def create(
        cls,
        event_type: EventType,
        payload: dict[str, Any],
        organisation_id: UUID | None = None,
        project_id: UUID | None = None,
    ) -> "DomainEvent":
        return cls(
            event_type=event_type,
            payload=payload,
            organisation_id=organisation_id,
            project_id=project_id,
        )


# ---------------------------------------------------------------------------
# Convenience factory functions for common events
# ---------------------------------------------------------------------------


def agent_created(agent_id: UUID, organisation_id: UUID, project_id: UUID) -> DomainEvent:
    return DomainEvent.create(
        EventType.AGENT_CREATED,
        {"agent_id": str(agent_id)},
        organisation_id=organisation_id,
        project_id=project_id,
    )


def policy_violation(
    agent_id: UUID,
    rule: str,
    explanation: str,
    organisation_id: UUID,
    project_id: UUID,
) -> DomainEvent:
    return DomainEvent.create(
        EventType.POLICY_VIOLATION,
        {"agent_id": str(agent_id), "rule": rule, "explanation": explanation},
        organisation_id=organisation_id,
        project_id=project_id,
    )


def payment_verified(
    payment_id: UUID,
    tool_call_id: UUID,
    organisation_id: UUID,
    project_id: UUID,
) -> DomainEvent:
    return DomainEvent.create(
        EventType.PAYMENT_VERIFIED,
        {"payment_id": str(payment_id), "tool_call_id": str(tool_call_id)},
        organisation_id=organisation_id,
        project_id=project_id,
    )


def call_succeeded(
    tool_call_id: UUID,
    receipt_id: UUID,
    organisation_id: UUID,
    project_id: UUID,
) -> DomainEvent:
    return DomainEvent.create(
        EventType.CALL_SUCCEEDED,
        {"tool_call_id": str(tool_call_id), "receipt_id": str(receipt_id)},
        organisation_id=organisation_id,
        project_id=project_id,
    )


def settlement_mismatch(
    payment_id: UUID,
    expected: dict[str, Any],
    actual: dict[str, Any],
    organisation_id: UUID,
    project_id: UUID,
) -> DomainEvent:
    return DomainEvent.create(
        EventType.SETTLEMENT_MISMATCH,
        {
            "payment_id": str(payment_id),
            "expected": expected,
            "actual": actual,
        },
        organisation_id=organisation_id,
        project_id=project_id,
    )
