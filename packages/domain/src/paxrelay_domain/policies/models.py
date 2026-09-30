"""Policy domain models.

Policies are versioned and immutable after activation.
Editing an active policy always creates a new version.

The policy engine consumes PolicyEvaluationRequest and produces
PolicyEvaluationResult — both are pure data structures with no
side effects.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from paxrelay_domain.types import CapabilitySlug, Environment, MonetaryAmount


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class PolicyMode(str, Enum):
    """How the policy engine handles violations.

    - OBSERVE: Record violations but do not block.
    - WARN: Permit the action but emit an alert event.
    - ENFORCE: Block the action (production mode).
    """

    OBSERVE = "observe"
    WARN = "warn"
    ENFORCE = "enforce"


class PolicyDecision(str, Enum):
    """Outcome returned by the policy evaluator."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    PAUSE_AGENT = "pause_agent"


# ---------------------------------------------------------------------------
# Policy rules configuration
# ---------------------------------------------------------------------------


class PolicyRules(BaseModel):
    """The complete set of spending and access control rules for a policy.

    All monetary values use MonetaryAmount (atomic integers, no floats).
    Absent fields disable that rule (i.e. no limit applies).
    """

    model_config = {"frozen": True}

    # Spending limits
    maximum_per_call: MonetaryAmount | None = None
    daily_budget: MonetaryAmount | None = None
    monthly_budget: MonetaryAmount | None = None

    # Access control
    allowed_capabilities: list[CapabilitySlug] = Field(
        default_factory=list,
        description=(
            "Wildcard-capable list. An empty list means all capabilities "
            "are permitted. Patterns like 'research.*' are supported."
        ),
    )
    allowed_providers: list[str] = Field(
        default_factory=list,
        description="Empty list means all providers are allowed.",
    )
    blocked_providers: list[str] = Field(default_factory=list)
    allowed_contracts: list[str] = Field(default_factory=list)

    # Provider quality thresholds
    minimum_provider_reputation: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    minimum_provider_success_rate: float | None = Field(
        default=None, ge=0.0, le=1.0
    )
    maximum_accepted_latency_ms: int | None = Field(default=None, ge=0)

    # Human approval
    approval_threshold: MonetaryAmount | None = Field(
        default=None,
        description=(
            "Payments at or above this amount require human approval "
            "before execution."
        ),
    )

    # Emergency stop conditions
    maximum_consecutive_failures: int | None = Field(default=None, ge=1)
    maximum_drawdown: MonetaryAmount | None = None

    # Session settings
    session_expiry_seconds: int | None = Field(default=None, ge=0)

    # Currency restrictions
    allowed_currencies: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Policy and versioning
# ---------------------------------------------------------------------------


class Policy(BaseModel):
    """A versioned, immutable spending and access-control policy.

    Policies are assigned to agents. Once a policy version is activated,
    it must not be mutated — changes require creating a new version.
    """

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    organisation_id: UUID
    project_id: UUID
    environment: Environment = Environment.DEVELOPMENT
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    mode: PolicyMode = PolicyMode.ENFORCE
    rules: PolicyRules = Field(default_factory=PolicyRules)
    version: int = Field(default=1, ge=1)
    is_active: bool = True
    activated_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PolicyAssignment(BaseModel):
    """Links a policy version to an agent."""

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    policy_id: UUID
    assigned_at: datetime = Field(default_factory=datetime.utcnow)
    assigned_by: UUID | None = None


# ---------------------------------------------------------------------------
# Policy evaluation I/O — pure data, no side effects
# ---------------------------------------------------------------------------


class PolicyEvaluationRequest(BaseModel):
    """Input to the policy engine.

    Matches the JSON example in the README exactly.
    """

    model_config = {"frozen": True}

    agent_id: str
    capability: CapabilitySlug
    provider_id: str
    amount: MonetaryAmount
    current_daily_spend: MonetaryAmount
    current_monthly_spend: MonetaryAmount
    provider_reputation: float = Field(ge=0.0, le=1.0)
    provider_success_rate: float = Field(ge=0.0, le=1.0)
    provider_avg_latency_ms: float = Field(default=0.0, ge=0.0)
    consecutive_failures: int = Field(default=0, ge=0)
    agent_status: str = "active"
    emergency_stop: bool = False
    session_valid: bool = True
    extra: dict[str, Any] = Field(default_factory=dict)


class PolicyEvaluationResult(BaseModel):
    """Output from the policy engine.

    Matches the JSON example in the README exactly.
    """

    model_config = {"frozen": True}

    decision: PolicyDecision
    matched_rules: list[str] = Field(default_factory=list)
    explanation: str
    policy_version: int
    policy_id: UUID | None = None
    mode: PolicyMode = PolicyMode.ENFORCE

    def is_allowed(self) -> bool:
        """Return True only when the request should proceed to payment."""
        return self.decision == PolicyDecision.ALLOW

    def requires_approval(self) -> bool:
        return self.decision == PolicyDecision.REQUIRE_APPROVAL
