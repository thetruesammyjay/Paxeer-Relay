"""Settlement reconciliation job.

Polls LayerX for pending settlements and marks them as settled/anchored in the DB.
"""

from __future__ import annotations

from paxrelay_worker.jobs import BaseJob


class ReconciliationJob(BaseJob):
    """Reconcile LayerX payment settlements against the local DB."""

    @property
    def interval_seconds(self) -> int:
        return self.settings.settlement_poll_interval_seconds

    async def tick(self) -> None:
        # TODO: query payments in SUBMITTED/VERIFIED state, check LayerX for
        # settlement confirmation, update PaymentModel.state to SETTLED_LAYERX
        # and stamp settled_at, then check for L1 anchoring.
        self.log.debug("Reconciliation tick — stub, no-op until implemented")
