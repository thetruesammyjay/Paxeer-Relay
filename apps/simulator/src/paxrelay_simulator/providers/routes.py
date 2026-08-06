"""Provider registry stub routes — simulated Paxeer service registry."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/paxeer/registry", tags=["registry"])

# In-process service registry — reset on restart, fine for local development.
_services: dict[str, dict[str, Any]] = {}


class PublishRequest(BaseModel):
    service_id: str
    name: str
    slug: str
    capability: str
    endpoint_url: str
    price_per_call: dict[str, Any]
    provider_id: str


@router.post("/publish")
async def publish_service(body: PublishRequest) -> dict:
    """Register a simulated service in the in-memory registry."""
    record = body.model_dump()
    _services[body.service_id] = record
    return {"published": True, "service": record}


@router.get("/services")
async def list_services(capability: str | None = None) -> list[dict]:
    """List all simulated services, optionally filtered by capability."""
    items = list(_services.values())
    if capability:
        items = [s for s in items if s.get("capability") == capability]
    return items


@router.get("/provider/{provider_id}/history")
async def provider_history(provider_id: str) -> dict:
    """Return a stub reputation history for a provider."""
    return {
        "provider_id": provider_id,
        "reputation_score": 1.0,
        "success_rate": 1.0,
        "avg_latency_ms": 42.0,
        "total_calls": 0,
    }
