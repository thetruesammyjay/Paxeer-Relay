"""Worker job base class and shared helpers."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

from paxrelay_worker.config import WorkerSettings


class BaseJob(ABC):
    """Periodic async loop with structured logging and graceful shutdown."""

    interval_seconds: int = 60

    def __init__(self, settings: WorkerSettings) -> None:
        self.settings = settings
        self.log = logging.getLogger(self.__class__.__name__)

    async def run(self) -> None:
        """Loop forever, calling ``tick()`` every ``interval_seconds``."""
        self.log.info("Starting %s", self.__class__.__name__)
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                self.log.info("%s stopping", self.__class__.__name__)
                return
            except Exception as exc:
                self.log.exception("Unhandled error in %s: %s", self.__class__.__name__, exc)
            await asyncio.sleep(self.interval_seconds)

    @abstractmethod
    async def tick(self) -> None:
        """One unit of work per loop iteration."""
