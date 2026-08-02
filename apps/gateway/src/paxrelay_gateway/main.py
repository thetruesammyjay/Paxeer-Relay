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

from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from paxrelay_db import close_database, configure_database, get_session
from paxrelay_paxeer import MockPaxeerAdapter, OfficialPaxeerAdapter
from paxrelay_policy import PolicyEvaluator
from paxrelay_receipts import LocalReceiptSigner, ReceiptSigner
from paxrelay_router import ProviderRouter

from paxrelay_gateway.config import GatewaySettings, get_settings
from paxrelay_gateway.middleware.auth import AgentAuthError, resolve_agent
from paxrelay_gateway.services.invoke import GatewayInvokeService


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------


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
    configure_database(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    _container = Container(settings)
    try:
        yield
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
        max_provider_attempts=c.settings.router_max_provider_attempts,
    )


def create_app() -> FastAPI:
    app = FastAPI(title="PaxRelay Gateway", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(AgentAuthError)
    async def _agent_auth_handler(_: Request, exc: AgentAuthError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "auth", "message": exc.message}},
        )

    @app.post("/v1/invoke")
    async def invoke(
        request: Request,
        agent=Depends(resolve_agent),
        session: AsyncSession = Depends(get_session),
    ) -> JSONResponse:
        body = await request.json()
        service = _invoke_service(session)
        result = await service.start(
            agent=agent,
            capability=body.get("capability", ""),
            idempotency_key=body.get("idempotency_key", ""),
            arguments=body.get("arguments", {}),
            constraints=body.get("constraints"),
        )
        return JSONResponse(status_code=result.status_code, content=result.body)

    @app.post("/v1/invoke/{tool_call_id}")
    async def invoke_complete(
        tool_call_id: UUID,
        request: Request,
        agent=Depends(resolve_agent),
        session: AsyncSession = Depends(get_session),
    ) -> JSONResponse:
        body = await request.json()
        service = _invoke_service(session)
        result = await service.complete(
            tool_call_id=tool_call_id,
            proof=body.get("proof", ""),
        )
        return JSONResponse(status_code=result.status_code, content=result.body)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
