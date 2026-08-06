"""PaxRelay Simulator — local Paxeer and 402LXP development server.

Exposes stub endpoints that mimic the Paxeer Network and LayerX protocol
so the gateway and SDK can be exercised without a live chain.

Routes:
  POST /lxp402/payment-requirement  — generate a fake payment challenge
  POST /lxp402/verify               — verify and accept any well-formed proof
  GET  /layerx/settlement/{id}      — return a simulated settlement record
  POST /paxeer/registry/publish     — echo back a published service
  GET  /paxeer/registry/services    — list simulated services
  GET  /health                      — liveness probe
"""

from __future__ import annotations

from fastapi import FastAPI

from paxrelay_simulator.config import get_settings
from paxrelay_simulator.lxp402.routes import router as lxp402_router
from paxrelay_simulator.layerx.routes import router as layerx_router
from paxrelay_simulator.providers.routes import router as providers_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PaxRelay Simulator",
        version="0.1.0",
        description="Local dev simulator for the Paxeer Network and 402LXP protocol.",
    )

    app.include_router(lxp402_router)
    app.include_router(layerx_router)
    app.include_router(providers_router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
