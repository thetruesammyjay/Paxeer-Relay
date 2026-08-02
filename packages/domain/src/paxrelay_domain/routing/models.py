"""Provider routing domain models.

All routing is deterministic and explainable:
every decision produces a human-readable explanation
and a machine-readable score breakdown.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from paxrelay_domain.types import CapabilitySlug, MonetaryAmount


class RoutingStrategy(str, Enum):
    """Supported provider selection strategies."""

    BALANCED = "balanced"
    LOWEST_COST = "lowest_cost"
    LOWEST_LATENCY = "lowest_latency"
    HIGHEST_REPUTATION = "highest_reputation"
    HIGHEST_AVAILABILITY = "highest_availability"
    STICKY_SESSION = "sticky_session"
    CUSTOM_WEIGHTED = "custom_weighted"


class RouteConstraints(BaseModel):
    """Hard requirements a provider must satisfy to be eligible."""

    model_config = {"frozen": True}

    maximum_price: MonetaryAmount | None = None
    maximum_latency_ms: int | None = Field(default=None, ge=0)
    minimum_success_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    minimum_reputation: float | None = Field(default=None, ge=0.0, le=1.0)
    required_protocols: list[str] = Field(default_factory=list)
    blocked_providers: list[str] = Field(default_factory=list)
    allowed_providers: list[str] = Field(default_factory=list)
    preferred_provider_id: str | None = Field(
        default=None,
        description="Used by sticky_session strategy.",
    )


class RouteRequest(BaseModel):
    """Input to the routing engine — matches the README JSON example."""

    model_config = {"frozen": True}

    capability: CapabilitySlug
    constraints: RouteConstraints = Field(default_factory=RouteConstraints)
    strategy: RoutingStrategy = RoutingStrategy.BALANCED
    custom_weights: dict[str, float] | None = Field(
        default=None,
        description="Only used when strategy is 'custom_weighted'.",
    )


class RouteScoreBreakdown(BaseModel):
    """Per-dimension normalised scores [0.0, 1.0] for a provider candidate.

    Matches the 'breakdown' field in the README route decision example.
    """

    model_config = {"frozen": True}

    reputation: float = Field(ge=0.0, le=1.0)
    success_rate: float = Field(ge=0.0, le=1.0)
    latency: float = Field(ge=0.0, le=1.0)
    price: float = Field(ge=0.0, le=1.0)
    availability: float = Field(ge=0.0, le=1.0)

    def weighted_total(
        self,
        weights: dict[str, float] | None = None,
    ) -> float:
        """Compute the composite score using given or default weights.

        Default balanced strategy weights (from README):
          reputation × 0.30
          success_rate × 0.25
          latency × 0.20
          price × 0.15
          availability × 0.10
        """
        w = weights or {
            "reputation": 0.30,
            "success_rate": 0.25,
            "latency": 0.20,
            "price": 0.15,
            "availability": 0.10,
        }
        return (
            self.reputation * w.get("reputation", 0.30)
            + self.success_rate * w.get("success_rate", 0.25)
            + self.latency * w.get("latency", 0.20)
            + self.price * w.get("price", 0.15)
            + self.availability * w.get("availability", 0.10)
        )


class RouteDecision(BaseModel):
    """Output from the routing engine — matches the README JSON example."""

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    tool_call_id: UUID | None = None
    provider_id: UUID
    service_id: UUID
    service_version_id: UUID
    score: float = Field(ge=0.0, le=1.0)
    strategy: RoutingStrategy
    breakdown: RouteScoreBreakdown
    explanation: str
    attempt_number: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)
