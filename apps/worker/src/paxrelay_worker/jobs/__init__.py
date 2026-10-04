"""Worker job base class and shared helpers."""

from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from paxrelay_worker.config import WorkerSettings

if TYPE_CHECKING:
    from paxrelay_worker.health import WorkerHealthMonitor


class BaseJob(ABC):
    """Periodic async loop with structured logging and graceful shutdown."""

    interval_seconds: int = 60

    def __init__(self, settings: WorkerSettings) -> None:
        self.settings = settings
        self.log = logging.getLogger(self.__class__.__name__)

    @property
    def health_name(self) -> str:
        """Stable name exposed by worker readiness diagnostics."""
        return _job_name(self.__class__.__name__)

    async def run(self, health_monitor: WorkerHealthMonitor | None = None) -> None:
        """Loop forever, calling ``tick()`` every ``interval_seconds``."""
        job_name = self.health_name
        if health_monitor is not None:
            health_monitor.register_job(job_name, self.interval_seconds)
            health_monitor.job_started(job_name)
        self.log.info("Starting %s", self.__class__.__name__)
        try:
            while True:
                try:
                    await self.tick()
                except asyncio.CancelledError:
                    self.log.info("%s stopping", self.__class__.__name__)
                    return
                except Exception as exc:
                    if health_monitor is not None:
                        health_monitor.job_failed(job_name)
                    self.log.exception(
                        "Unhandled error in %s: %s", self.__class__.__name__, exc
                    )
                else:
                    if health_monitor is not None:
                        health_monitor.job_succeeded(job_name)
                await asyncio.sleep(self.interval_seconds)
        finally:
            if health_monitor is not None:
                health_monitor.job_stopped(job_name)

    @abstractmethod
    async def tick(self) -> None:
        """One unit of work per loop iteration."""


def _job_name(class_name: str) -> str:
    name = class_name.removesuffix("Job")
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
