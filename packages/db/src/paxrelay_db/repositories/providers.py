"""SQLAlchemy implementation of ProviderRepository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_domain import (
    Environment,
    PricingModel,
    Provider,
    ProviderMetrics,
    ProviderStatus,
    Service,
    ServiceDelivery,
    ServiceHealth,
    ServicePricing,
    ServiceProtocol,
    ServiceStatus,
    ServiceVersion,
)
from paxrelay_db.models.providers import (
    ProviderMetricsModel,
    ProviderModel,
    ServiceModel,
    ServiceVersionModel,
)
from paxrelay_db.repositories._common import as_uuid, money, sid


def _to_provider(m: ProviderModel) -> Provider:
    return Provider(
        id=as_uuid(m.id),
        name=m.name,
        slug=m.slug,
        organisation_id=as_uuid(m.organisation_id),
        project_id=as_uuid(m.project_id),
        environment=Environment(m.environment),
        wallet_address=m.wallet_address,
        layerx_account_id=m.layerx_account_id,
        solana_devnet_address=m.solana_devnet_address,
        status=ProviderStatus(m.status),
        description=m.description,
        website_url=m.website_url,
        is_verified=m.is_verified,
        metadata=m.extra_metadata or {},
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_service(m: ServiceModel) -> Service:
    pricing = m.pricing_json or {}
    delivery = m.delivery_json or {}
    health = m.health_json or {}
    return Service(
        id=as_uuid(m.id),
        provider_id=as_uuid(m.provider_id),
        organisation_id=as_uuid(m.organisation_id),
        project_id=as_uuid(m.project_id),
        environment=Environment(m.environment),
        name=m.name,
        slug=m.slug,
        capability=m.capability,
        protocols=[ServiceProtocol(p) for p in (m.protocols or [])],
        pricing=ServicePricing(
            model=PricingModel(pricing.get("model", "per_call")),
            price_per_call=(
                money(
                    pricing["price_per_call"]["amount_atomic"],
                    pricing["price_per_call"]["currency"],
                    pricing["price_per_call"]["decimals"],
                )
                if pricing.get("price_per_call")
                else None
            ),
            price_per_unit=(
                money(
                    pricing["price_per_unit"]["amount_atomic"],
                    pricing["price_per_unit"]["currency"],
                    pricing["price_per_unit"]["decimals"],
                )
                if pricing.get("price_per_unit")
                else None
            ),
            unit=pricing.get("unit"),
            currency=pricing.get("currency", "USDX"),
        ),
        delivery=ServiceDelivery(
            timeout_seconds=delivery.get("timeout_seconds", 30),
            maximum_request_bytes=delivery.get("maximum_request_bytes", 32_768),
            maximum_response_bytes=delivery.get("maximum_response_bytes", 10_485_760),
            idempotent=delivery.get("idempotent", True),
            concurrency_limit=delivery.get("concurrency_limit"),
        ),
        health=ServiceHealth(
            endpoint=health.get("endpoint", "/health"),
            interval_seconds=health.get("interval_seconds", 30),
            timeout_seconds=health.get("timeout_seconds", 5),
            failure_threshold=health.get("failure_threshold", 3),
            last_check_at=health.get("last_check_at"),
            last_check_passing=health.get("last_check_passing"),
            consecutive_health_failures=health.get("consecutive_health_failures", 0),
            last_check_status_code=health.get("last_check_status_code"),
            last_check_error=health.get("last_check_error"),
        ),
        status=ServiceStatus(m.status),
        base_url=m.base_url,
        description=m.description,
        created_at=m.created_at,
        updated_at=m.updated_at,
    )


def _to_service_version(m: ServiceVersionModel) -> ServiceVersion:
    pricing = m.pricing_json or {}
    delivery = m.delivery_json or {}
    return ServiceVersion(
        id=as_uuid(m.id),
        service_id=as_uuid(m.service_id),
        provider_id=as_uuid(m.provider_id),
        version=m.version,
        capability=m.capability,
        pricing=ServicePricing(
            model=PricingModel(pricing.get("model", "per_call")),
            price_per_call=(
                money(
                    pricing["price_per_call"]["amount_atomic"],
                    pricing["price_per_call"]["currency"],
                    pricing["price_per_call"]["decimals"],
                )
                if pricing.get("price_per_call")
                else None
            ),
            price_per_unit=(
                money(
                    pricing["price_per_unit"]["amount_atomic"],
                    pricing["price_per_unit"]["currency"],
                    pricing["price_per_unit"]["decimals"],
                )
                if pricing.get("price_per_unit")
                else None
            ),
            unit=pricing.get("unit"),
            currency=pricing.get("currency", "USDX"),
        ),
        delivery=ServiceDelivery(
            timeout_seconds=delivery.get("timeout_seconds", 30),
            maximum_request_bytes=delivery.get("maximum_request_bytes", 32_768),
            maximum_response_bytes=delivery.get("maximum_response_bytes", 10_485_760),
            idempotent=delivery.get("idempotent", True),
            concurrency_limit=delivery.get("concurrency_limit"),
        ),
        endpoint_url=m.endpoint_url,
        protocol=ServiceProtocol(getattr(m, "protocol", "http")),
        mcp_tool_name=m.mcp_tool_name,
        mcp_input_schema=m.mcp_input_schema,
        openapi_schema=m.openapi_schema,
        is_active=m.is_active,
        published_at=m.published_at,
    )


def _to_metrics(m: ProviderMetricsModel) -> ProviderMetrics:
    return ProviderMetrics(
        service_id=as_uuid(m.service_id),
        provider_id=as_uuid(m.provider_id),
        reputation_score=m.reputation_score,
        success_rate=m.success_rate,
        avg_latency_ms=m.avg_latency_ms,
        availability_score=m.availability_score,
        total_calls=m.total_calls,
        consecutive_failures=m.consecutive_failures,
        health_check_passing=m.health_check_passing,
        measured_at=m.measured_at,
    )


def _pricing_to_json(pricing: ServicePricing) -> dict:
    return {
        "model": pricing.model.value,
        "price_per_call": (
            {
                "amount_atomic": pricing.price_per_call.amount_atomic,
                "currency": pricing.price_per_call.currency.value,
                "decimals": pricing.price_per_call.decimals,
            }
            if pricing.price_per_call
            else None
        ),
        "price_per_unit": (
            {
                "amount_atomic": pricing.price_per_unit.amount_atomic,
                "currency": pricing.price_per_unit.currency.value,
                "decimals": pricing.price_per_unit.decimals,
            }
            if pricing.price_per_unit
            else None
        ),
        "unit": pricing.unit,
        "currency": pricing.currency.value,
    }


def _delivery_to_json(delivery: ServiceDelivery) -> dict:
    return {
        "timeout_seconds": delivery.timeout_seconds,
        "maximum_request_bytes": delivery.maximum_request_bytes,
        "maximum_response_bytes": delivery.maximum_response_bytes,
        "idempotent": delivery.idempotent,
        "concurrency_limit": delivery.concurrency_limit,
    }


def _health_to_json(health: ServiceHealth) -> dict:
    value = {
        "endpoint": health.endpoint,
        "interval_seconds": health.interval_seconds,
        "timeout_seconds": health.timeout_seconds,
        "failure_threshold": health.failure_threshold,
        "consecutive_health_failures": health.consecutive_health_failures,
    }
    if health.last_check_at is not None:
        value["last_check_at"] = health.last_check_at.isoformat()
    if health.last_check_passing is not None:
        value["last_check_passing"] = health.last_check_passing
    if health.last_check_status_code is not None:
        value["last_check_status_code"] = health.last_check_status_code
    if health.last_check_error is not None:
        value["last_check_error"] = health.last_check_error
    return value


class SqlAlchemyProviderRepository:
    """Persists providers, services, versions, and metrics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, provider_id: UUID) -> Provider | None:
        stmt = select(ProviderModel).where(
            ProviderModel.id == sid(provider_id), ProviderModel.deleted_at.is_(None)
        )
        m = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_provider(m) if m is not None else None

    async def list_active(
        self,
        organisation_id: UUID,
        project_id: UUID,
        *,
        limit: int = 100,
    ) -> list[Provider]:
        stmt = (
            select(ProviderModel)
            .where(
                ProviderModel.organisation_id == sid(organisation_id),
                ProviderModel.project_id == sid(project_id),
                ProviderModel.status == "active",
                ProviderModel.deleted_at.is_(None),
            )
            .order_by(ProviderModel.created_at.asc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_provider(m) for m in rows]

    async def list(
        self,
        organisation_id: UUID,
        project_id: UUID,
        *,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
        search: str | None = None,
        environment: str | None = None,
    ) -> list[Provider]:
        """Tenant-scoped provider listing with optional status/search filters.

        Unlike :meth:`list_active`, this returns providers of any status unless
        a ``status`` filter is supplied, so dashboards can surface inactive or
        suspended providers too.
        """
        stmt = select(ProviderModel).where(
            ProviderModel.organisation_id == sid(organisation_id),
            ProviderModel.project_id == sid(project_id),
            ProviderModel.deleted_at.is_(None),
        )
        if environment is not None:
            stmt = stmt.where(ProviderModel.environment == environment)
        if status is not None:
            stmt = stmt.where(ProviderModel.status == status)
        if search is not None:
            pattern = f"%{search}%"
            stmt = stmt.where(
                ProviderModel.name.ilike(pattern) | ProviderModel.slug.ilike(pattern)
            )
        stmt = (
            stmt.order_by(ProviderModel.created_at.desc()).limit(limit).offset(offset)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_provider(m) for m in rows]

    async def save(self, provider: Provider) -> Provider:
        m = await self._session.get(ProviderModel, sid(provider.id))
        if m is None:
            m = ProviderModel(id=sid(provider.id))
            self._session.add(m)
        m.name = provider.name
        m.slug = provider.slug
        m.organisation_id = sid(provider.organisation_id)
        m.project_id = sid(provider.project_id)
        m.environment = provider.environment.value
        m.wallet_address = provider.wallet_address
        m.layerx_account_id = provider.layerx_account_id
        m.solana_devnet_address = provider.solana_devnet_address
        m.status = provider.status.value
        m.description = provider.description
        m.website_url = provider.website_url
        m.is_verified = provider.is_verified
        m.extra_metadata = dict(provider.metadata)
        await self._session.flush()
        await self._session.refresh(m)
        return _to_provider(m)

    async def get_service(self, service_id: UUID) -> Service | None:
        stmt = select(ServiceModel).where(
            ServiceModel.id == sid(service_id), ServiceModel.deleted_at.is_(None)
        )
        m = (await self._session.execute(stmt)).scalar_one_or_none()
        return _to_service(m) if m is not None else None

    async def set_service_status(
        self,
        service_id: UUID,
        *,
        organisation_id: UUID,
        project_id: UUID,
        environment: str,
        status: ServiceStatus,
    ) -> tuple[Service, ServiceStatus] | None:
        """Update one tenant-owned service without replacing health metadata."""
        stmt = (
            select(ServiceModel)
            .where(
                ServiceModel.id == sid(service_id),
                ServiceModel.organisation_id == sid(organisation_id),
                ServiceModel.project_id == sid(project_id),
                ServiceModel.environment == environment,
                ServiceModel.deleted_at.is_(None),
            )
            .with_for_update()
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        if model is None:
            return None

        previous_status = ServiceStatus(model.status)
        # Deprecated services are terminal. The API maps this unchanged result
        # to a conflict instead of silently restoring it to routing.
        if previous_status == ServiceStatus.DEPRECATED:
            return _to_service(model), previous_status

        if previous_status != status:
            model.status = status.value
            await self._session.flush()
            await self._session.refresh(model)
        return _to_service(model), previous_status

    async def list_services(self, provider_id: UUID) -> list[Service]:
        stmt = (
            select(ServiceModel)
            .where(
                ServiceModel.provider_id == sid(provider_id),
                ServiceModel.deleted_at.is_(None),
            )
            .order_by(ServiceModel.created_at.asc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_service(m) for m in rows]

    async def list_services_by_tenant(
        self,
        organisation_id: UUID,
        project_id: UUID,
        *,
        limit: int = 100,
        environment: str | None = None,
    ) -> list[Service]:
        """Tenant-scoped service listing (convenience beyond the Protocol)."""
        stmt = select(ServiceModel).where(
            ServiceModel.organisation_id == sid(organisation_id),
            ServiceModel.project_id == sid(project_id),
            ServiceModel.deleted_at.is_(None),
        )
        if environment is not None:
            stmt = stmt.where(ServiceModel.environment == environment)
        stmt = (
            stmt
            .order_by(ServiceModel.created_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [_to_service(m) for m in rows]

    async def save_service(self, service: Service) -> Service:
        m = await self._session.get(ServiceModel, sid(service.id))
        if m is None:
            m = ServiceModel(id=sid(service.id))
            self._session.add(m)
        m.provider_id = sid(service.provider_id)
        m.organisation_id = sid(service.organisation_id)
        m.project_id = sid(service.project_id)
        m.environment = service.environment.value
        m.name = service.name
        m.slug = service.slug
        m.capability = service.capability
        m.protocols = [p.value for p in service.protocols]
        m.status = service.status.value
        m.base_url = service.base_url
        m.description = service.description
        m.pricing_json = _pricing_to_json(service.pricing)
        m.delivery_json = _delivery_to_json(service.delivery)
        m.health_json = _health_to_json(service.health)
        await self._session.flush()
        await self._session.refresh(m)
        return _to_service(m)

    async def get_service_version(self, version_id: UUID) -> ServiceVersion | None:
        m = await self._session.get(ServiceVersionModel, sid(version_id))
        return _to_service_version(m) if m is not None else None

    async def save_service_version(self, version: ServiceVersion) -> ServiceVersion:
        m = await self._session.get(ServiceVersionModel, sid(version.id))
        if m is None:
            m = ServiceVersionModel(id=sid(version.id))
            self._session.add(m)
        m.service_id = sid(version.service_id)
        m.provider_id = sid(version.provider_id)
        m.version = version.version
        m.capability = version.capability
        m.endpoint_url = version.endpoint_url
        m.protocol = version.protocol.value
        m.mcp_tool_name = version.mcp_tool_name
        m.mcp_input_schema = version.mcp_input_schema
        m.pricing_json = _pricing_to_json(version.pricing)
        m.delivery_json = _delivery_to_json(version.delivery)
        m.openapi_schema = version.openapi_schema
        m.is_active = version.is_active
        m.published_at = version.published_at
        await self._session.flush()
        await self._session.refresh(m)
        return _to_service_version(m)

    async def get_metrics(self, service_id: UUID) -> ProviderMetrics | None:
        stmt = select(ProviderMetricsModel).where(
            ProviderMetricsModel.service_id == sid(service_id)
        )
        m = (await self._session.execute(stmt)).scalars().first()
        return _to_metrics(m) if m is not None else None

    async def save_metrics(self, metrics: ProviderMetrics) -> ProviderMetrics:
        stmt = select(ProviderMetricsModel).where(
            ProviderMetricsModel.service_id == sid(metrics.service_id),
            ProviderMetricsModel.provider_id == sid(metrics.provider_id),
        )
        m = (await self._session.execute(stmt)).scalars().first()
        if m is None:
            m = ProviderMetricsModel(id=sid(metrics.service_id))
            m.service_id = sid(metrics.service_id)
            m.provider_id = sid(metrics.provider_id)
            self._session.add(m)
        m.reputation_score = metrics.reputation_score
        m.success_rate = metrics.success_rate
        m.avg_latency_ms = metrics.avg_latency_ms
        m.availability_score = metrics.availability_score
        m.total_calls = metrics.total_calls
        m.consecutive_failures = metrics.consecutive_failures
        m.health_check_passing = metrics.health_check_passing
        m.measured_at = metrics.measured_at
        await self._session.flush()
        await self._session.refresh(m)
        return _to_metrics(m)

    async def find_eligible_services(
        self,
        capability: str,
        organisation_id: UUID,
        project_id: UUID,
        environment: str,
    ) -> list[tuple[Service, ServiceVersion, ProviderMetrics]]:
        """Return (service, version, metrics) for every active, healthy match.

        Joins services → service_versions → provider_metrics, filtering by
        capability and tenant scope, keeping only active, healthy candidates.
        """
        stmt = (
            select(ServiceModel, ServiceVersionModel, ProviderMetricsModel)
            .join(ProviderModel, ProviderModel.id == ServiceModel.provider_id)
            .join(
                ServiceVersionModel,
                ServiceVersionModel.service_id == ServiceModel.id,
            )
            .join(
                ProviderMetricsModel,
                ProviderMetricsModel.service_id == ServiceModel.id,
            )
            .where(
                ServiceModel.organisation_id == sid(organisation_id),
                ServiceModel.project_id == sid(project_id),
                ServiceModel.environment == environment,
                ServiceModel.capability == capability,
                ServiceModel.status == "active",
                ServiceModel.deleted_at.is_(None),
                ProviderModel.organisation_id == sid(organisation_id),
                ProviderModel.project_id == sid(project_id),
                ProviderModel.environment == environment,
                ProviderModel.status == "active",
                ProviderModel.deleted_at.is_(None),
                ServiceVersionModel.is_active.is_(True),
                ProviderMetricsModel.health_check_passing.is_(True),
            )
            .order_by(ServiceVersionModel.published_at.desc())
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            (_to_service(svc), _to_service_version(ver), _to_metrics(metrics))
            for svc, ver, metrics in rows
        ]
