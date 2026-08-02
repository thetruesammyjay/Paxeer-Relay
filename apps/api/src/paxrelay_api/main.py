"""PaxRelay control-plane API — FastAPI entrypoint.

Bootstrap sequence:
  1. Read settings (pydantic-settings).
  2. Configure the async database engine on startup (disposed on shutdown).
  3. Register routers and structured error handlers.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from paxrelay_db import close_database, configure_database

from paxrelay_api.config import get_settings
from paxrelay_api.exceptions import register_error_handlers
from paxrelay_api.routes.agents import router as agents_router
from paxrelay_api.routes.keys import router as keys_router
from paxrelay_api.routes.policies import router as policies_router
from paxrelay_api.routes.providers import router as providers_router
from paxrelay_api.routes.services import router as services_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_database(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    try:
        yield
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

    app.include_router(agents_router, prefix="/v1")
    app.include_router(providers_router, prefix="/v1")
    app.include_router(services_router, prefix="/v1")
    app.include_router(policies_router, prefix="/v1")
    app.include_router(keys_router, prefix="/v1")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
