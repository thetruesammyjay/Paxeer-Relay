"""Routing strategy implementations."""

from __future__ import annotations

from paxrelay_domain import (
    ProviderMetrics,
    RouteConstraints,
    RouteScoreBreakdown,
    RoutingStrategy,
    Service,
    ServiceVersion,
)
from paxrelay_router.scoring import compute_score_breakdown

# Candidate = (Service, ServiceVersion, ProviderMetrics, RouteScoreBreakdown)
Candidate = tuple[Service, ServiceVersion, ProviderMetrics, RouteScoreBreakdown]


def _rank_balanced(candidates: list[Candidate]) -> list[Candidate]:
    return sorted(candidates, key=lambda c: c[3].weighted_total(), reverse=True)


def _rank_lowest_cost(candidates: list[Candidate]) -> list[Candidate]:
    weights = {"reputation": 0.1, "success_rate": 0.1, "latency": 0.1, "price": 0.6, "availability": 0.1}
    return sorted(candidates, key=lambda c: c[3].weighted_total(weights), reverse=True)


def _rank_lowest_latency(candidates: list[Candidate]) -> list[Candidate]:
    weights = {"reputation": 0.1, "success_rate": 0.1, "latency": 0.6, "price": 0.1, "availability": 0.1}
    return sorted(candidates, key=lambda c: c[3].weighted_total(weights), reverse=True)


def _rank_highest_reputation(candidates: list[Candidate]) -> list[Candidate]:
    weights = {"reputation": 0.7, "success_rate": 0.15, "latency": 0.05, "price": 0.05, "availability": 0.05}
    return sorted(candidates, key=lambda c: c[3].weighted_total(weights), reverse=True)


def _rank_highest_availability(candidates: list[Candidate]) -> list[Candidate]:
    weights = {"reputation": 0.1, "success_rate": 0.1, "latency": 0.1, "price": 0.1, "availability": 0.6}
    return sorted(candidates, key=lambda c: c[3].weighted_total(weights), reverse=True)


def _rank_sticky_session(
    candidates: list[Candidate],
    preferred_provider_id: str | None,
) -> list[Candidate]:
    if preferred_provider_id:
        preferred = [c for c in candidates if str(c[0].provider_id) == preferred_provider_id]
        others = [c for c in candidates if str(c[0].provider_id) != preferred_provider_id]
        return preferred + _rank_balanced(others)
    return _rank_balanced(candidates)


def rank_candidates(
    candidates: list[Candidate],
    strategy: RoutingStrategy,
    custom_weights: dict[str, float] | None = None,
    preferred_provider_id: str | None = None,
) -> list[Candidate]:
    """Return candidates sorted best-first by the given strategy."""
    match strategy:
        case RoutingStrategy.BALANCED:
            return _rank_balanced(candidates)
        case RoutingStrategy.LOWEST_COST:
            return _rank_lowest_cost(candidates)
        case RoutingStrategy.LOWEST_LATENCY:
            return _rank_lowest_latency(candidates)
        case RoutingStrategy.HIGHEST_REPUTATION:
            return _rank_highest_reputation(candidates)
        case RoutingStrategy.HIGHEST_AVAILABILITY:
            return _rank_highest_availability(candidates)
        case RoutingStrategy.STICKY_SESSION:
            return _rank_sticky_session(candidates, preferred_provider_id)
        case RoutingStrategy.CUSTOM_WEIGHTED:
            w = custom_weights or {}
            return sorted(candidates, key=lambda c: c[3].weighted_total(w), reverse=True)
        case _:
            return _rank_balanced(candidates)
