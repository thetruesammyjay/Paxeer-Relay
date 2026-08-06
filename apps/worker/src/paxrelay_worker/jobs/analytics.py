"""Analytics aggregation job.

Materialises hourly and daily spend totals per agent/project into the
analytics tables so dashboard queries are fast.
"""

from __future__ import annotations

from paxrelay_worker.jobs import BaseJob


class AnalyticsJob(BaseJob):
    """Flush in-flight spend data into materialised analytics rows."""

    @property
    def interval_seconds(self) -> int:
        return self.settings.analytics_flush_interval_seconds

    async def tick(self) -> None:
        # TODO: aggregate ToolCallModel rows completed since last flush into
        # hourly/daily spend per (organisation_id, project_id, agent_id).
        self.log.debug("Analytics tick — stub, no-op until implemented")
