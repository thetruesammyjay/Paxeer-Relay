"""Request models for gateway invocation endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from paxrelay_domain import RouteConstraints


class InvokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)*(\.\*)?$",
    )
    idempotency_key: str = Field(min_length=1, max_length=128)
    arguments: dict[str, Any]
    constraints: RouteConstraints | None = None


class InvokeProofRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proof: str = Field(min_length=1, max_length=65_536)
