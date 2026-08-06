"""Transactional outbox consumer.

Drains OutboxEventModel rows from the DB and publishes them onto the Redis
pub/sub bus so downstream services receive domain events exactly once.
"""

from __future__ import annotations

from paxrelay_worker.jobs import BaseJob


class OutboxJob(BaseJob):
    """Drain the transactional outbox into the Redis event bus."""

    interval_seconds = 5  # drain frequently to keep latency low

    async def tick(self) -> None:
        # TODO: SELECT unprocessed OutboxEventModel rows (ordered by created_at),
        # publish each to the appropriate Redis channel, mark as processed.
        self.log.debug("Outbox tick — stub, no-op until implemented")
