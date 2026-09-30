"""PaxRelay control-plane API — FastAPI entrypoint.

Bootstrap sequence:
  1. Read settings (pydantic-settings).
  2. Configure the async database engine on startup (disposed on shutdown).
  3. Register routers and structured error handlers.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy import text
from starlette.middleware.cors import CORSMiddleware

from paxrelay_db import close_database, configure_database, get_engine

from paxrelay_api.config import get_settings
from paxrelay_api.exceptions import register_error_handlers
from paxrelay_api.middleware import RequestBodyLimitMiddleware, RequestIdMiddleware
from paxrelay_api.routes.agents import router as agents_router
from paxrelay_api.routes.approvals import router as approvals_router
from paxrelay_api.routes.audit_logs import router as audit_logs_router
from paxrelay_api.routes.analytics import router as analytics_router
from paxrelay_api.routes.batch import router as batch_router
from paxrelay_api.routes.keys import router as keys_router
from paxrelay_api.routes.policies import router as policies_router
from paxrelay_api.routes.providers import router as providers_router
from paxrelay_api.routes.receipts import router as receipts_router
from paxrelay_api.routes.services import router as services_router
from paxrelay_api.routes.transactions import router as transactions_router
from paxrelay_api.routes.webhooks import router as webhooks_router

logger = logging.getLogger("paxrelay.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = getattr(app.state, "settings", None) or get_settings()
    app.state.settings = settings
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    configure_database(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    redis_client: Redis | None = None
    app.state.redis = None
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
        yield
    finally:
        try:
            if redis_client is not None:
                await redis_client.aclose()
        finally:
            await close_database()


def create_app() -> FastAPI:
    """Build the FastAPI application with routers attached."""
    app = FastAPI(
        title="PaxRelay API",
        version="0.1.0",
        description="Control plane for agents, providers, services, and policies.",
        lifespan=lifespan,
    )

    register_error_handlers(app)
    settings = get_settings()
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Idempotency-Key",
            "X-Agent-Id",
            "X-Request-Id",
        ],
        expose_headers=["Retry-After", "X-Request-Id"],
        max_age=600,
    )
    app.add_middleware(RequestBodyLimitMiddleware)
    app.add_middleware(RequestIdMiddleware)

    app.include_router(agents_router, prefix="/v1")
    app.include_router(approvals_router, prefix="/v1")
    app.include_router(providers_router, prefix="/v1")
    app.include_router(services_router, prefix="/v1")
    app.include_router(policies_router, prefix="/v1")
    app.include_router(keys_router, prefix="/v1")
    app.include_router(receipts_router, prefix="/v1")
    app.include_router(transactions_router, prefix="/v1")
    app.include_router(analytics_router, prefix="/v1")
    app.include_router(audit_logs_router, prefix="/v1")
    app.include_router(webhooks_router, prefix="/v1")
    app.include_router(batch_router, prefix="/v1")

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness only: confirms this API process can serve HTTP."""
        return {"status": "ok"}

    @app.get("/ready", response_model=None)
    async def readiness(request: Request) -> dict[str, object] | JSONResponse:
        """Readiness: check PostgreSQL without exposing connection details."""
        settings = getattr(request.app.state, "settings", None) or get_settings()
        dependencies = {"postgresql": "ok"}
        try:
            async with asyncio.timeout(settings.readiness_timeout_seconds):
                async with get_engine().connect() as connection:
                    await connection.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001 - readiness reports only dependency state.
            logger.warning(
                "API readiness dependency unavailable request_id=%s dependency=postgresql error_type=%s",
                getattr(request.state, "request_id", "-"),
                type(exc).__name__,
            )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "dependencies": {"postgresql": "unavailable"},
                },
            )
        if settings.rate_limiting_enabled:
            redis_client = getattr(request.app.state, "redis", None)
            try:
                if redis_client is None:
                    raise RuntimeError("Redis client was not initialized")
                async with asyncio.timeout(settings.readiness_timeout_seconds):
                    await redis_client.ping()
            except Exception as exc:  # noqa: BLE001 - report dependency state only.
                logger.warning(
                    "API readiness dependency unavailable request_id=%s dependency=redis error_type=%s",
                    getattr(request.state, "request_id", "-"),
                    type(exc).__name__,
                )
                return JSONResponse(
                    status_code=503,
                    content={
                        "status": "not_ready",
                        "dependencies": {**dependencies, "redis": "unavailable"},
                    },
                )
            dependencies["redis"] = "ok"
        return {"status": "ready", "dependencies": dependencies}

    return app


app = create_app()
