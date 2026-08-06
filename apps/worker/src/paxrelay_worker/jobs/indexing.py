"""Provider health indexing job.

Fetches live health and latency metrics from registered providers and writes
them back into ProviderMetricsModel so the router has fresh scores.
"""

from __future__ import annotations

from paxrelay_worker.jobs import BaseJob


class ProviderIndexJob(BaseJob):
    """Poll each active provider's health endpoint and update metrics."""

    interval_seconds = 60

    async def tick(self) -> None:
        # TODO: load all active ServiceModels, POST to each service's
        # health_check_url, compute latency + success_rate, upsert
        # ProviderMetricsModel rows.
        self.log.debug("ProviderIndex tick — stub, no-op until implemented")
