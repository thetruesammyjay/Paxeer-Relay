"""Provider scoring — normalised [0,1] scores and weighted composites.

All score functions produce values in [0.0, 1.0].
The balanced composite uses the exact weights from the README.
"""

from __future__ import annotations

from paxrelay_domain import (
    MonetaryAmount,
    ProviderMetrics,
    RouteConstraints,
    RouteScoreBreakdown,
    Service,
)


def _normalize(value: float, worst: float, best: float) -> float:
    """Linearly map value from [worst, best] to [0, 1]."""
    if best == worst:
        return 1.0
    return max(0.0, min(1.0, (value - worst) / (best - worst)))


def score_reputation(metrics: ProviderMetrics) -> float:
    return metrics.reputation_score  # Already in [0, 1]


def score_success_rate(metrics: ProviderMetrics) -> float:
    return metrics.success_rate  # Already in [0, 1]


def score_latency(
    metrics: ProviderMetrics,
    reference_max_ms: float = 5000.0,
) -> float:
    """Lower latency → higher score. Normalised against reference_max_ms."""
    if metrics.avg_latency_ms <= 0:
        return 1.0
    # Invert: 0 ms → 1.0, reference_max_ms → 0.0
    return _normalize(metrics.avg_latency_ms, reference_max_ms, 0.0)


def score_price(
    service: Service,
    constraints: RouteConstraints,
) -> float:
    """Lower price → higher score. Normalised against the maximum allowed price."""
    price = service.pricing.price_per_call
    max_price = constraints.maximum_price

    if price is None:
        return 0.5  # Unknown pricing, neutral score
    if max_price is None or max_price.amount_atomic == 0:
        return 1.0  # No constraint, full score

    ratio = price.amount_atomic / max_price.amount_atomic
    return max(0.0, min(1.0, 1.0 - ratio))


def score_availability(metrics: ProviderMetrics) -> float:
    return metrics.availability_score  # Already in [0, 1]


def compute_score_breakdown(
    service: Service,
    metrics: ProviderMetrics,
    constraints: RouteConstraints,
) -> RouteScoreBreakdown:
    """Compute all five dimension scores for one provider candidate."""
    return RouteScoreBreakdown(
        reputation=score_reputation(metrics),
        success_rate=score_success_rate(metrics),
        latency=score_latency(metrics),
        price=score_price(service, constraints),
        availability=score_availability(metrics),
    )
