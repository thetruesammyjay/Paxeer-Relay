"""Human-readable route explanation generator."""

from __future__ import annotations

from paxrelay_domain import RouteScoreBreakdown, RoutingStrategy


def build_route_explanation(
    provider_name: str,
    strategy: RoutingStrategy,
    breakdown: RouteScoreBreakdown,
    composite_score: float,
) -> str:
    """Generate a human-readable explanation for a routing decision."""
    dominant = _dominant_factor(breakdown)
    strategy_label = strategy.value.replace("_", " ")

    return (
        f"Selected via {strategy_label} strategy (score {composite_score:.3f}). "
        f"{dominant} "
        f"Reputation {breakdown.reputation:.3f}, "
        f"success rate {breakdown.success_rate:.3f}, "
        f"latency score {breakdown.latency:.3f}, "
        f"price score {breakdown.price:.3f}, "
        f"availability {breakdown.availability:.3f}."
    )


def _dominant_factor(breakdown: RouteScoreBreakdown) -> str:
    scores = {
        "strong delivery history": breakdown.success_rate,
        "low latency": breakdown.latency,
        "competitive price": breakdown.price,
        "high reputation": breakdown.reputation,
        "high availability": breakdown.availability,
    }
    best = max(scores, key=lambda k: scores[k])
    return f"Selected for its {best}."
