"""Provider hard-filter functions.

Each filter takes a provider candidate and constraints and returns True
if the provider PASSES (is eligible) or False if it should be removed.
All filters are pure functions with no side effects.
"""

from __future__ import annotations

from paxrelay_domain import (
    MonetaryAmount,
    ProviderMetrics,
    ProviderStatus,
    RouteConstraints,
    Service,
    ServiceVersion,
)


def filter_provider_active(
    service: Service,
    metrics: ProviderMetrics,
    constraints: RouteConstraints,
) -> bool:
    """Provider must be active."""
    return service.status.value == "active"


def filter_health_check(
    service: Service,
    metrics: ProviderMetrics,
    constraints: RouteConstraints,
) -> bool:
    """Health check must be passing."""
    return metrics.health_check_passing


def filter_price(
    service: Service,
    metrics: ProviderMetrics,
    constraints: RouteConstraints,
) -> bool:
    """Price must not exceed the agent's maximum."""
    if constraints.maximum_price is None:
        return True
    price = service.pricing.price_per_call
    if price is None:
        return True
    return price <= constraints.maximum_price


def filter_capability(
    service: Service,
    metrics: ProviderMetrics,
    constraints: RouteConstraints,
) -> bool:
    """Capability is already matched at query time — always passes here."""
    return True


def filter_blocked_providers(
    service: Service,
    metrics: ProviderMetrics,
    constraints: RouteConstraints,
) -> bool:
    """Provider must not be on the blocklist."""
    return str(service.provider_id) not in constraints.blocked_providers


def filter_allowed_providers(
    service: Service,
    metrics: ProviderMetrics,
    constraints: RouteConstraints,
) -> bool:
    """If an allowlist is set, provider must be in it."""
    if not constraints.allowed_providers:
        return True
    return str(service.provider_id) in constraints.allowed_providers


def filter_minimum_reputation(
    service: Service,
    metrics: ProviderMetrics,
    constraints: RouteConstraints,
) -> bool:
    """Reputation score must meet the minimum threshold."""
    if constraints.minimum_reputation is None:
        return True
    return metrics.reputation_score >= constraints.minimum_reputation


def filter_minimum_success_rate(
    service: Service,
    metrics: ProviderMetrics,
    constraints: RouteConstraints,
) -> bool:
    """Success rate must meet the minimum threshold."""
    if constraints.minimum_success_rate is None:
        return True
    return metrics.success_rate >= constraints.minimum_success_rate


def filter_maximum_latency(
    service: Service,
    metrics: ProviderMetrics,
    constraints: RouteConstraints,
) -> bool:
    """Average latency must not exceed the maximum."""
    if constraints.maximum_latency_ms is None:
        return True
    return metrics.avg_latency_ms <= constraints.maximum_latency_ms


def filter_protocol(
    service: Service,
    metrics: ProviderMetrics,
    constraints: RouteConstraints,
) -> bool:
    """At least one of the required protocols must be supported."""
    if not constraints.required_protocols:
        return True
    supported = {p.value for p in service.protocols}
    return bool(supported.intersection(set(constraints.required_protocols)))


# All filters applied in order — any False eliminates the candidate
ALL_FILTERS = [
    filter_provider_active,
    filter_health_check,
    filter_price,
    filter_blocked_providers,
    filter_allowed_providers,
    filter_minimum_reputation,
    filter_minimum_success_rate,
    filter_maximum_latency,
    filter_protocol,
]


def apply_all_filters(
    service: Service,
    metrics: ProviderMetrics,
    constraints: RouteConstraints,
) -> bool:
    """Return True only if the candidate passes every filter."""
    return all(f(service, metrics, constraints) for f in ALL_FILTERS)
