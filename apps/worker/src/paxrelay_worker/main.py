"""PaxRelay Worker — background job runner entry point.

Runs a set of async loops in parallel:
  - settlement reconciliation (polls LayerX and Paxeer L1)
  - provider health indexing (feeds scoring data into paxrelay_db)
  - analytics aggregation (materialises hourly/daily spend rows)
  - outbox fan-out (creates durable webhook delivery rows)
  - webhook delivery (sends signed events with bounded retries)
"""

from __future__ import annotations

import asyncio
import logging

from paxrelay_db import close_database, configure_database
from paxrelay_paxeer import MockPaxeerAdapter, OfficialPaxeerAdapter

from paxrelay_worker.config import get_settings
from paxrelay_worker.jobs.analytics import AnalyticsJob
from paxrelay_worker.jobs.approvals import ApprovalExpirationJob
from paxrelay_worker.jobs.health import HealthCheckJob
from paxrelay_worker.jobs.indexing import ProviderIndexJob
from paxrelay_worker.jobs.outbox import OutboxJob
from paxrelay_worker.jobs.reconciliation import ReconciliationJob
from paxrelay_worker.jobs.webhooks import WebhookDeliveryJob


async def run() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    log = logging.getLogger(__name__)

    configure_database(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    log.info("Worker starting — env=%s", settings.app_env)

    if settings.use_mock_adapter:
        network_adapter = MockPaxeerAdapter()
        log.warning("Worker is using the mock Paxeer adapter")
    else:
        network_adapter = OfficialPaxeerAdapter(
            rpc_url=settings.paxeer_rpc_url,
            layerx_api_url=settings.layerx_api_url or "",
            chain_id=settings.paxeer_chain_id,
            timeout=settings.paxeer_adapter_timeout_seconds,
            settlement_api_url=settings.paxeer_settlement_api_url,
            l1_settlement_contract_address=settings.paxeer_l1_settlement_contract_address,
            l1_commitment_event_topic=settings.paxeer_l1_commitment_event_topic,
            l1_confirmation_blocks=settings.paxeer_l1_confirmation_blocks,
        )

    try:
        await asyncio.gather(
            ReconciliationJob(settings, network_adapter, network_adapter).run(),
            ApprovalExpirationJob(settings).run(),
            ProviderIndexJob(settings).run(),
            AnalyticsJob(settings).run(),
            OutboxJob(settings).run(),
            WebhookDeliveryJob(settings).run(),
            HealthCheckJob(settings).run(),
        )
    finally:
        await close_database()


if __name__ == "__main__":
    asyncio.run(run())
