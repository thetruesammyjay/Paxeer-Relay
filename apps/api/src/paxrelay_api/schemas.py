"""Pydantic request/response schemas for the control-plane API.

These are the wire contracts for the dashboard and SDKs. They deliberately
mirror the domain models but stay separate so the HTTP surface can evolve
independently of the internal domain layer.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class MoneyIn(BaseModel):
    """A human-friendly monetary amount accepted on input."""

    amount_atomic: int = Field(ge=0)
    currency: str = "USDX"
    decimals: int = 6


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    wallet_address: str | None = None
    description: str | None = None


class AgentOut(BaseModel):
    id: UUID
    name: str
    slug: str
    organisation_id: UUID
    project_id: UUID
    environment: str
    wallet_address: str | None
    status: str
    description: str | None
    created_at: datetime


class WalletOut(BaseModel):
    id: UUID
    agent_id: UUID
    address: str
    is_primary: bool
    label: str | None


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


class ProviderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    wallet_address: str | None = None
    description: str | None = None
    website_url: str | None = None


class ProviderOut(BaseModel):
    id: UUID
    name: str
    slug: str
    organisation_id: UUID
    project_id: UUID
    environment: str
    wallet_address: str | None
    status: str
    is_verified: bool
    description: str | None


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    capability: str = Field(pattern=r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)*(\.\*)?$")
    protocols: list[str] = Field(default_factory=lambda: ["http"])
    price_per_call: MoneyIn
    base_url: str
    endpoint_url: str
    version: str = "1.0.0"
    description: str | None = None


class ServiceOut(BaseModel):
    id: UUID
    provider_id: UUID
    name: str
    slug: str
    capability: str
    protocols: list[str]
    status: str
    base_url: str | None
    price_per_call: MoneyIn | None
    description: str | None


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    mode: str = "enforce"
    maximum_per_call: MoneyIn | None = None
    daily_budget: MoneyIn | None = None
    monthly_budget: MoneyIn | None = None
    allowed_capabilities: list[str] = Field(default_factory=list)
    allowed_providers: list[str] = Field(default_factory=list)
    blocked_providers: list[str] = Field(default_factory=list)
    approval_threshold: MoneyIn | None = None


class PolicyOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    mode: str
    version: int
    is_active: bool


class PolicyAssignIn(BaseModel):
    agent_id: UUID


class PolicyAssignmentOut(BaseModel):
    id: UUID
    agent_id: UUID
    policy_id: UUID
    assigned_at: datetime


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    key_type: str = Field(default="test", pattern=r"^(test|live)$")
    scopes: str = ""


class ApiKeyOut(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    key_type: str
    # The raw key is returned exactly once, at creation time.
    raw_key: str | None = None
