"""Probe configured provider health paths and update routing availability."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from paxrelay_db import get_engine
from paxrelay_db.models.providers import (
    ProviderMetricsModel,
    ProviderModel,
    ServiceModel,
)
from paxrelay_worker.config import WorkerSettings
from paxrelay_worker.jobs import BaseJob
from paxrelay_worker.webhook_transport import (
    UnsafeWebhookDestination,
    WebhookDnsFailure,
    WebhookDnsTimeout,
    pinned_webhook_transport,
    resolve_webhook_destination,
)

@dataclass(frozen=True, slots=True)
class HealthProbe:
    service_id: str
    provider_id: str
    base_url: str | None
    health_config: dict[str, object]


@dataclass(frozen=True, slots=True)
class HealthResult:
    service_id: str
    provider_id: str
    passed: bool
    status_code: int | None = None
    error_code: str | None = None


class HealthCheckJob(BaseJob):
    """Probe due active services using bounded, DNS-pinned HTTP requests."""

    interval_seconds = 30
    availability_alpha = 0.2

    def __init__(self, settings: WorkerSettings) -> None:
        super().__init__(settings)
        self._sessions = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )

    async def tick(self) -> None:
        now = datetime.now(UTC).replace(tzinfo=None)
        probes = await self._due_probes(now)
        if not probes:
            return

        semaphore = asyncio.Semaphore(self.settings.provider_health_concurrency)

        async def run_probe(probe: HealthProbe) -> HealthResult:
            async with semaphore:
                return await self._check(probe)

        results = await asyncio.gather(*(run_probe(probe) for probe in probes))
        await self._record_results(results, now)

        passed = sum(result.passed for result in results)
        self.log.info(
            "Provider health checks completed checked=%d passed=%d failed=%d",
            len(results),
            passed,
            len(results) - passed,
        )

    async def _due_probes(self, now: datetime) -> list[HealthProbe]:
        async with self._sessions() as session:
            statement = (
                select(ServiceModel)
                .join(ProviderModel, ProviderModel.id == ServiceModel.provider_id)
                .where(
                    ServiceModel.environment == self.settings.app_env,
                    ServiceModel.status == "active",
                    ServiceModel.deleted_at.is_(None),
                    ProviderModel.environment == self.settings.app_env,
                    ProviderModel.status == "active",
                    ProviderModel.deleted_at.is_(None),
                )
                .order_by(ServiceModel.id.asc())
            )
            services = (await session.execute(statement)).scalars().all()

        due: list[HealthProbe] = []
        for service in services:
            health = (
                service.health_json if isinstance(service.health_json, dict) else {}
            )
            interval = _bounded_int(health.get("interval_seconds"), 30, 5, 3600)
            last_checked = _parse_timestamp(health.get("last_check_at"))
            if (
                last_checked is not None
                and (now - last_checked).total_seconds() < interval
            ):
                continue
            due.append(
                HealthProbe(
                    service_id=service.id,
                    provider_id=service.provider_id,
                    base_url=service.base_url,
                    health_config=dict(health),
                )
            )
        return due

    async def _check(self, probe: HealthProbe) -> HealthResult:
        timeout = _bounded_int(probe.health_config.get("timeout_seconds"), 5, 1, 30)
        try:
            url = _health_url(
                probe.base_url,
                probe.health_config.get("endpoint", "/health"),
            )
            hostname = _normalise_hostname(urlsplit(url).hostname or "")
            allowed_hosts = self.settings.provider_endpoint_hosts
            if allowed_hosts and hostname not in allowed_hosts:
                raise UnsafeWebhookDestination(
                    "provider hostname is not allowlisted for health checks"
                )

            destination = await resolve_webhook_destination(
                url,
                allow_private=self.settings.app_env in {"development", "test"},
                timeout_seconds=min(float(timeout), 5.0),
            )
            transport = pinned_webhook_transport(destination)
            async with httpx.AsyncClient(
                transport=transport,
                timeout=httpx.Timeout(float(timeout)),
                follow_redirects=False,
                trust_env=False,
            ) as client:
                async with client.stream(
                    "GET",
                    url,
                    headers={"Accept": "application/health+json, application/json"},
                ) as response:
                    return HealthResult(
                        service_id=probe.service_id,
                        provider_id=probe.provider_id,
                        passed=200 <= response.status_code < 300,
                        status_code=response.status_code,
                        error_code=(
                            None
                            if 200 <= response.status_code < 300
                            else "health_http_status"
                        ),
                    )
        except (
            httpx.HTTPError,
            RuntimeError,
            WebhookDnsFailure,
            WebhookDnsTimeout,
            ValueError,
        ) as exc:
            return HealthResult(
                service_id=probe.service_id,
                provider_id=probe.provider_id,
                passed=False,
                error_code=type(exc).__name__,
            )

    async def _record_results(
        self,
        results: list[HealthResult],
        checked_at: datetime,
    ) -> None:
        async with self._sessions() as session:
            for result in results:
                service_stmt = (
                    select(ServiceModel)
                    .where(
                        ServiceModel.id == result.service_id,
                        ServiceModel.environment == self.settings.app_env,
                        ServiceModel.status == "active",
                        ServiceModel.deleted_at.is_(None),
                    )
                    .with_for_update()
                )
                service = (await session.execute(service_stmt)).scalar_one_or_none()
                if service is None:
                    continue

                health = dict(service.health_json or {})
                interval = _bounded_int(health.get("interval_seconds"), 30, 5, 3600)
                last_checked = _parse_timestamp(health.get("last_check_at"))
                if (
                    last_checked is not None
                    and (checked_at - last_checked).total_seconds() < interval
                ):
                    continue
                failure_threshold = _bounded_int(
                    health.get("failure_threshold"), 3, 1, 20
                )
                health_failures = _bounded_int(
                    health.get("consecutive_health_failures"), 0, 0, 1_000_000
                )
                if result.passed:
                    health_failures = 0
                else:
                    health_failures += 1
                health.update(
                    {
                        "last_check_at": checked_at.isoformat(),
                        "last_check_passing": result.passed,
                        "consecutive_health_failures": health_failures,
                        "last_check_status_code": result.status_code,
                        "last_check_error": result.error_code,
                    }
                )
                service.health_json = health

                metrics_stmt = (
                    select(ProviderMetricsModel)
                    .where(
                        ProviderMetricsModel.service_id == result.service_id,
                        ProviderMetricsModel.provider_id == result.provider_id,
                    )
                    .with_for_update()
                )
                metrics = (await session.execute(metrics_stmt)).scalar_one_or_none()
                if metrics is None:
                    self.log.error(
                        "Provider metrics row missing for health check service_id=%s",
                        result.service_id,
                    )
                    continue

                if result.passed:
                    metrics.health_check_passing = True
                elif health_failures >= failure_threshold:
                    metrics.health_check_passing = False

                old_availability = float(metrics.availability_score or 0.0)
                observation = 1.0 if result.passed else 0.0
                metrics.availability_score = (
                    (1.0 - self.availability_alpha) * old_availability
                    + self.availability_alpha * observation
                )
                metrics.measured_at = checked_at

                if not result.passed:
                    self.log.warning(
                        "Provider health check failed service_id=%s failures=%d "
                        "threshold=%d code=%s status=%s",
                        result.service_id,
                        health_failures,
                        failure_threshold,
                        result.error_code or "unknown",
                        result.status_code,
                    )
            await session.commit()


def _health_url(base_url: str | None, endpoint: object) -> str:
    if not isinstance(base_url, str) or not isinstance(endpoint, str):
        raise UnsafeWebhookDestination("health check target is not configured")
    base = urlsplit(base_url)
    path = urlsplit(endpoint)
    if (
        base.scheme not in {"http", "https"}
        or not base.hostname
        or base.username is not None
        or base.password is not None
        or base.query
        or base.fragment
        or not endpoint.startswith("/")
        or endpoint.startswith("//")
        or "\\" in endpoint
        or path.scheme
        or path.netloc
        or path.query
        or path.fragment
        or any(ord(char) < 0x20 or ord(char) == 0x7F for char in endpoint)
        or any(segment in {".", ".."} for segment in path.path.split("/"))
    ):
        raise UnsafeWebhookDestination("health check target is invalid")
    return urlunsplit((base.scheme, base.netloc, path.path, "", ""))


def _normalise_hostname(hostname: str) -> str:
    try:
        return hostname.rstrip(".").encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise UnsafeWebhookDestination("provider hostname is invalid") from exc


def _bounded_int(value: object, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed
