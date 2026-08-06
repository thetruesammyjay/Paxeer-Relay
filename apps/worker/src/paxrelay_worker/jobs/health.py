"""Service health check job.

Performs periodic liveness checks on all registered providers and flips
ServiceModel.status to DEGRADED/OFFLINE when consecutive failures are observed.
"""

from __future__ import annotations

from paxrelay_worker.jobs import BaseJob


class HealthCheckJob(BaseJob):
    """Monitor provider liveness and update service health status."""

    interval_seconds = 30

    async def tick(self) -> None:
        # TODO: load all active services with health_check_url, issue HEAD/GET
        # requests, update ServiceHealth.health_check_passing and
        # ServiceHealth.last_check_at, flip service status on repeated failures.
        self.log.debug("HealthCheck tick — stub, no-op until implemented")
