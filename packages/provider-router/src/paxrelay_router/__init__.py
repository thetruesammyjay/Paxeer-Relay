"""paxrelay_router — provider routing engine package."""

from paxrelay_router.router import ProviderRouter
from paxrelay_router.filters import apply_all_filters, ALL_FILTERS
from paxrelay_router.scoring import compute_score_breakdown
from paxrelay_router.strategies import rank_candidates
from paxrelay_router.failover import is_retryable, can_failover
from paxrelay_router.explanations import build_route_explanation

__all__ = [
    "ProviderRouter",
    "apply_all_filters",
    "ALL_FILTERS",
    "compute_score_breakdown",
    "rank_candidates",
    "is_retryable",
    "can_failover",
    "build_route_explanation",
]
