"""Internal HTTP liveness and readiness endpoints for the worker process."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from http import HTTPStatus
from urllib.parse import urlsplit

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from paxrelay_db import get_engine

logger = logging.getLogger("paxrelay.worker.health")


@dataclass
class _JobState:
    interval_seconds: int
    started_at: float | None = None
    last_success_at: float | None = None
    running: bool = False


class WorkerHealthMonitor:
    """Track whether every scheduled job loop is running and making progress."""

    def __init__(self) -> None:
        self._jobs: dict[str, _JobState] = {}

    def register_job(self, name: str, interval_seconds: int) -> None:
        self._jobs.setdefault(name, _JobState(interval_seconds=interval_seconds))

    def job_started(self, name: str) -> None:
        state = self._jobs[name]
        state.started_at = time.monotonic()
        state.running = True

    def job_succeeded(self, name: str) -> None:
        state = self._jobs[name]
        state.last_success_at = time.monotonic()

    def job_failed(self, name: str) -> None:
        # A single failed iteration does not mark the worker unready. Readiness
        # changes only if successful work stops advancing beyond the stale limit.
        if name not in self._jobs:
            logger.error("Health monitor received an unknown worker job")

    def job_stopped(self, name: str) -> None:
        state = self._jobs.get(name)
        if state is not None:
            state.running = False

    def snapshot(self) -> tuple[bool, dict[str, str]]:
        now = time.monotonic()
        statuses: dict[str, str] = {}
        for name, state in sorted(self._jobs.items()):
            if not state.running:
                status = "stopped"
            else:
                progress_at = state.last_success_at or state.started_at
                stale_after = max(30, state.interval_seconds * 3)
                if progress_at is None:
                    status = "starting"
                elif now - progress_at > stale_after:
                    status = "stale"
                elif state.last_success_at is None:
                    status = "starting"
                else:
                    status = "ok"
            statuses[name] = status

        ready = bool(statuses) and all(state == "ok" for state in statuses.values())
        return ready, statuses


class WorkerHealthServer:
    """Small stdlib HTTP server for internal platform health probes."""

    _REQUEST_TIMEOUT_SECONDS = 3.0
    _DATABASE_TIMEOUT_SECONDS = 2.0
    _MAX_REQUEST_LINE_BYTES = 2048
    _MAX_HEADER_LINE_BYTES = 8192
    _MAX_HEADER_COUNT = 32

    def __init__(
        self,
        *,
        host: str,
        port: int,
        monitor: WorkerHealthMonitor,
    ) -> None:
        self.host = host
        self.port = port
        self.monitor = monitor
        self._server: asyncio.Server | None = None
        self._writers: set[asyncio.StreamWriter] = set()
        self._sessions = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port,
            limit=self._MAX_HEADER_LINE_BYTES,
        )
        logger.info("Worker health server listening on %s:%d", self.host, self.port)

    async def close(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        writers = tuple(self._writers)
        for writer in writers:
            writer.close()
        self._writers.clear()
        if writers:
            await asyncio.gather(
                *(writer.wait_closed() for writer in writers),
                return_exceptions=True,
            )

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        self._writers.add(writer)
        try:
            async with asyncio.timeout(self._REQUEST_TIMEOUT_SECONDS):
                request_line = await reader.readline()
                if (
                    not request_line
                    or len(request_line) > self._MAX_REQUEST_LINE_BYTES
                ):
                    await self._write_response(writer, HTTPStatus.BAD_REQUEST, {})
                    return
                try:
                    method, target, version = request_line.decode("ascii").strip().split()
                except (UnicodeDecodeError, ValueError):
                    await self._write_response(writer, HTTPStatus.BAD_REQUEST, {})
                    return
                if version not in {"HTTP/1.0", "HTTP/1.1"}:
                    await self._write_response(writer, HTTPStatus.BAD_REQUEST, {})
                    return

                headers_complete = False
                for _ in range(self._MAX_HEADER_COUNT):
                    header = await reader.readline()
                    if header in {b"\r\n", b"\n"}:
                        headers_complete = True
                        break
                    if (
                        not header
                        or len(header) > self._MAX_HEADER_LINE_BYTES
                        or b":" not in header
                    ):
                        break
                if not headers_complete:
                    await self._write_response(writer, HTTPStatus.BAD_REQUEST, {})
                    return

                if method not in {"GET", "HEAD"}:
                    await self._write_response(writer, HTTPStatus.METHOD_NOT_ALLOWED, {})
                    return
                path = urlsplit(target).path
                if path == "/health":
                    await self._write_response(
                        writer,
                        HTTPStatus.OK,
                        {"status": "ok"},
                        include_body=method == "GET",
                    )
                    return
                if path == "/ready":
                    status, body = await self._readiness()
                    await self._write_response(
                        writer,
                        status,
                        body,
                        include_body=method == "GET",
                    )
                    return
                await self._write_response(writer, HTTPStatus.NOT_FOUND, {})
        except TimeoutError:
            await self._write_response(writer, HTTPStatus.REQUEST_TIMEOUT, {})
        except (ConnectionError, asyncio.IncompleteReadError):
            return
        except Exception:
            logger.exception("Worker health request failed")
            await self._write_response(writer, HTTPStatus.INTERNAL_SERVER_ERROR, {})
        finally:
            self._writers.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, RuntimeError):
                pass

    async def _readiness(self) -> tuple[HTTPStatus, dict[str, object]]:
        jobs_ready, jobs = self.monitor.snapshot()
        database_ready = False
        try:
            async with asyncio.timeout(self._DATABASE_TIMEOUT_SECONDS):
                async with self._sessions() as session:
                    await session.execute(text("SELECT 1"))
            database_ready = True
        except Exception as exc:
            logger.warning(
                "Worker readiness database probe failed error=%s",
                type(exc).__name__,
            )

        ready = database_ready and jobs_ready
        return (
            HTTPStatus.OK if ready else HTTPStatus.SERVICE_UNAVAILABLE,
            {
                "status": "ready" if ready else "not_ready",
                "database": "ok" if database_ready else "unavailable",
                "jobs": jobs,
            },
        )

    @staticmethod
    async def _write_response(
        writer: asyncio.StreamWriter,
        status: HTTPStatus,
        body: dict[str, object],
        *,
        include_body: bool = True,
    ) -> None:
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        response_body = encoded if include_body else b""
        headers = (
            f"HTTP/1.1 {status.value} {status.phrase}\r\n"
            "Content-Type: application/json; charset=utf-8\r\n"
            f"Content-Length: {len(encoded)}\r\n"
            "Cache-Control: no-store\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).encode("ascii")
        writer.write(headers + response_body)
        await writer.drain()
