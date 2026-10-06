"""Deterministic HTTP provider used by the local paid-request demonstration."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field


router = APIRouter(prefix="/demo-provider", tags=["demo provider"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)


@router.post("/search")
async def search(body: SearchRequest) -> dict[str, object]:
    """Return a stable sample response; this route never accesses the internet."""
    return {
        "provider": "PaxRelay local demo provider",
        "query": body.query,
        "results": [
            {
                "title": "PaxRelay request lifecycle",
                "url": "https://example.invalid/paxrelay/request-lifecycle",
                "summary": "A simulated provider response for the local demo.",
            }
        ],
        "simulation": True,
    }
