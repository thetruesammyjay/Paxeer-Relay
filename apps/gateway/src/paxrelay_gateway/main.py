"""PaxRelay 402LXP gateway — FastAPI entrypoint.

Exposes the paid-call lifecycle:
  - ``POST /v1/invoke`` — idempotency → route → policy → 402 quote challenge.
  - ``POST /v1/invoke/{tool_call_id}`` — submit proof → verify → forward →
    signed receipt.

Bootstrap:
  1. Read settings (pydantic-settings).
  2. Configure the async database engine on startup (disposed on shutdown).
  3. Construct the Paxeer adapter (mock or official) and the receipt signer.
  4. Register routes and error handlers.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, TypeVar
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_db import close_database, configure_database, get_engine, get_session
from paxrelay_paxeer import MockPaxeerAdapter, OfficialPaxeerAdapter
from paxrelay_policy import PolicyEvaluator
from paxrelay_receipts import LocalReceiptSigner, ReceiptSigner
from paxrelay_router import ProviderRouter

from paxrelay_gateway.config import GatewaySettings, get_settings
from paxrelay_gateway.middleware import RequestBodyLimitMiddleware
from paxrelay_gateway.middleware.auth import AgentAuthError, resolve_agent
from paxrelay_gateway.security.rate_limit import (
    GatewayRateLimitExceeded,
    GatewayRateLimitUnavailable,
)
from paxrelay_gateway.schemas import InvokeProofRequest, InvokeRequest
from paxrelay_gateway.services.invoke import GatewayInvokeService


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

logger = logging.getLogger("paxrelay.gateway")
TBody = TypeVar("TBody", bound=BaseModel)


class Container:
    """Holds the process-wide singletons the routes depend on."""

    def __init__(self, settings: GatewaySettings) -> None:
        self.settings = settings
        self.paxeer: Any = self._build_paxeer(settings)
        self.router = ProviderRouter()
        self.evaluator = PolicyEvaluator()
        self.signer: ReceiptSigner = self._build_signer(settings)

    @staticmethod
    def _build_paxeer(settings: GatewaySettings) -> Any:
        if settings.use_mock_adapter:
            return MockPaxeerAdapter()
        return OfficialPaxeerAdapter(
            rpc_url=settings.paxeer_rpc_url,
            layerx_api_url=settings.layerx_api_url,
            chain_id=settings.paxeer_chain_id,
        )

    @staticmethod
    def _build_signer(settings: GatewaySettings) -> ReceiptSigner:
        key = settings.receipt_signing_private_key
        if not key:
            # Deterministic dev fallback: a fixed generated key so signatures
            # are stable across restarts in local development.
            key = _DEV_PRIVATE_KEY
        return LocalReceiptSigner(key, key_id=settings.receipt_signing_key_id)


# A fixed dev key so local signatures are reproducible across restarts.
# Production MUST inject RECEIPT_SIGNING_PRIVATE_KEY instead.
_DEV_PRIVATE_KEY = LocalReceiptSigner.generate_key_pem()

_container: Container | None = None


def get_container() -> Container:
    assert _container is not None, "container not initialised"
    return _container


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _container
    settings = get_settings()
    app.state.settings = settings
    app.state.redis = None
    configure_database(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    redis_client: Redis | None = None
    try:
        if settings.rate_limiting_enabled:
            redis_client = Redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=settings.readiness_timeout_seconds,
                socket_timeout=settings.readiness_timeout_seconds,
            )
            async with asyncio.timeout(settings.readiness_timeout_seconds):
                await redis_client.ping()
            app.state.redis = redis_client
        _container = Container(settings)
        yield
    finally:
        _container = None
        try:
            if redis_client is not None:
                await redis_client.aclose()
        finally:
            await close_database()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def _invoke_service(session: AsyncSession) -> GatewayInvokeService:
    c = get_container()
    return GatewayInvokeService(
        session=session,
        paxeer=c.paxeer,
        router=c.router,
        evaluator=c.evaluator,
        signer=c.signer,
        quote_ttl_seconds=c.settings.lxp402_quote_ttl_seconds,
        approval_ttl_seconds=c.settings.policy_approval_ttl_seconds,
        max_provider_attempts=c.settings.router_max_provider_attempts,
        max_provider_response_bytes=c.settings.gateway_max_response_bytes,
        max_provider_timeout_seconds=c.settings.gateway_request_timeout_seconds,
        provider_connect_timeout_seconds=c.settings.gateway_connect_timeout_seconds,
        allow_private_provider_endpoints=c.settings.app_env in {"development", "test"},
        require_provider_wallet=not c.settings.use_mock_adapter,
        allowed_provider_hosts=c.settings.provider_endpoint_hosts or None,
        chain_id=c.settings.paxeer_chain_id,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="PaxRelay Gateway", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestBodyLimitMiddleware)

    @app.exception_handler(AgentAuthError)
    async def _agent_auth_handler(
        request: Request,
        exc: AgentAuthError,
    ) -> JSONResponse:
        headers = _response_headers(request)
        if exc.status_code == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "auth", "message": exc.message}},
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        return _validation_error_response(request, exc.errors())

    @app.exception_handler(GatewayRateLimitExceeded)
    async def _rate_limited_handler(
        request: Request,
        exc: GatewayRateLimitExceeded,
    ) -> JSONResponse:
        headers = _response_headers(request)
        headers.update(
            {
                "Retry-After": str(exc.retry_after_seconds),
                "RateLimit-Limit": str(exc.limit),
                "RateLimit-Remaining": "0",
                "RateLimit-Reset": str(exc.retry_after_seconds),
                "X-RateLimit-Reset": str(exc.reset_at),
            }
        )
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "rate_limited",
                    "message": "The gateway request limit has been reached.",
                }
            },
            headers=headers,
        )

    @app.exception_handler(GatewayRateLimitUnavailable)
    async def _rate_limit_unavailable_handler(
        request: Request,
        _: GatewayRateLimitUnavailable,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "rate_limiter_unavailable",
                    "message": "The gateway cannot verify its request limit right now.",
                }
            },
            headers=_response_headers(request),
        )

    @app.post("/v1/invoke")
    async def invoke(
        request: Request,
        agent=Depends(resolve_agent),
        session: AsyncSession = Depends(get_session),
    ) -> JSONResponse:
        body = await _parse_json_body(request, InvokeRequest)
        if isinstance(body, JSONResponse):
            return body
        service = _invoke_service(session)
        result = await service.start(
            agent=agent,
            capability=body.capability,
            idempotency_key=body.idempotency_key,
            arguments=body.arguments,
            constraints=(
                body.constraints.model_dump(exclude_none=True)
                if body.constraints is not None
                else None
            ),
        )
        return JSONResponse(
            status_code=result.status_code,
            content=result.body,
            headers=_response_headers(request),
        )

    @app.post("/v1/invoke/{tool_call_id}")
    async def invoke_complete(
        tool_call_id: UUID,
        request: Request,
        agent=Depends(resolve_agent),
        session: AsyncSession = Depends(get_session),
    ) -> JSONResponse:
        body = await _parse_json_body(request, InvokeProofRequest)
        if isinstance(body, JSONResponse):
            return body
        service = _invoke_service(session)
        result = await service.complete(
            tool_call_id=tool_call_id,
            agent=agent,
            proof=body.proof,
        )
        return JSONResponse(
            status_code=result.status_code,
            content=result.body,
            headers=_response_headers(request),
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", response_model=None)
    async def readiness(request: Request) -> dict[str, object] | JSONResponse:
        settings = request.app.state.settings
        dependencies = {"postgresql": "ok"}
        try:
            async with asyncio.timeout(settings.readiness_timeout_seconds):
                async with get_engine().connect() as connection:
                    await connection.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 - details stay in logs.
            logger.warning("Gateway PostgreSQL readiness failed error_type=%s", type(exc).__name__)
            dependencies["postgresql"] = "error"

        if settings.rate_limiting_enabled:
            dependencies["redis"] = "ok"
            redis_client = getattr(request.app.state, "redis", None)
            try:
                if redis_client is None:
                    raise RuntimeError("Redis client was not initialized")
                async with asyncio.timeout(settings.readiness_timeout_seconds):
                    await redis_client.ping()
            except Exception as exc:  # noqa: BLE001 - details stay in logs.
                logger.warning("Gateway Redis readiness failed error_type=%s", type(exc).__name__)
                dependencies["redis"] = "error"

        if any(state != "ok" for state in dependencies.values()):
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "dependencies": dependencies},
                headers={"Cache-Control": "no-store"},
            )
        return {"status": "ready", "dependencies": dependencies}

    return app


app = create_app()


def _response_headers(request: Request) -> dict[str, str]:
    """Attach no-store and any authenticated-key rate-limit metadata."""
    headers = {"Cache-Control": "no-store"}
    headers.update(getattr(request.state, "gateway_rate_limit_headers", {}))
    return headers


async def _parse_json_body(request: Request, model: type[TBody]) -> TBody | JSONResponse:
    """Validate the capped body after authentication and key rate limiting."""
    try:
        return model.model_validate_json(await request.body())
    except ValidationError as exc:
        return _validation_error_response(request, exc.errors(include_input=False))


def _validation_error_response(
    request: Request,
    errors: list[dict[str, Any]],
) -> JSONResponse:
    details = "; ".join(
        f"{'.'.join(str(part) for part in error.get('loc', ()))}: "
        f"{error.get('msg', 'Invalid value.')}"
        for error in errors[:20]
    )[:1024]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": details or "The request is invalid.",
            }
        },
        headers=_response_headers(request),
    )
