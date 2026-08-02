"""ProviderRouter — orchestrates filter → score → rank → select → explain."""

from __future__ import annotations

import uuid
from datetime import datetime

from paxrelay_domain import (
    ProviderMetrics,
    RouteDecision,
    RouteRequest,
    RoutingStrategy,
    Service,
    ServiceVersion,
)
from paxrelay_router.filters import apply_all_filters
from paxrelay_router.scoring import compute_score_breakdown
from paxrelay_router.strategies import rank_candidates
from paxrelay_router.explanations import build_route_explanation


class ProviderRouter:
    """Selects the best provider for a given capability and constraints.

    Usage:
        router = ProviderRouter()
        decision = router.select(route_request, candidates, tool_call_id=...)
    """

    def select(
        self,
        request: RouteRequest,
        candidates: list[tuple[Service, ServiceVersion, ProviderMetrics]],
        tool_call_id: uuid.UUID | None = None,
        attempt_number: int = 1,
    ) -> RouteDecision | None:
        """Filter, score and rank candidates; return the best RouteDecision.

        Returns None if no eligible provider is found after filtering.
        """
        if not candidates:
            return None

        # 1. Hard filter — remove ineligible providers
        eligible = [
            (svc, ver, metrics)
            for svc, ver, metrics in candidates
            if apply_all_filters(svc, metrics, request.constraints)
        ]

        if not eligible:
            return None

        # 2. Score — compute dimension scores for each eligible candidate
        scored: list[tuple[Service, ServiceVersion, ProviderMetrics, object]] = [
            (svc, ver, metrics, compute_score_breakdown(svc, metrics, request.constraints))
            for svc, ver, metrics in eligible
        ]

        # 3. Rank — sort by strategy
        ranked = rank_candidates(
            scored,  # type: ignore[arg-type]
            request.strategy,
            custom_weights=request.custom_weights,
            preferred_provider_id=(
                request.constraints.preferred_provider_id
                if request.strategy == RoutingStrategy.STICKY_SESSION
                else None
            ),
        )

        # 4. Select best
        best_svc, best_ver, best_metrics, best_breakdown = ranked[0]
        composite = best_breakdown.weighted_total(request.custom_weights)  # type: ignore[attr-defined]

        # 5. Explain
        explanation = build_route_explanation(
            provider_name=str(best_svc.provider_id),
            strategy=request.strategy,
            breakdown=best_breakdown,  # type: ignore[arg-type]
            composite_score=composite,
        )

        return RouteDecision(
            tool_call_id=tool_call_id,
            provider_id=best_svc.provider_id,
            service_id=best_svc.id,
            service_version_id=best_ver.id,
            score=round(composite, 4),
            strategy=request.strategy,
            breakdown=best_breakdown,  # type: ignore[arg-type]
            explanation=explanation,
            attempt_number=attempt_number,
            created_at=datetime.utcnow(),
        )
