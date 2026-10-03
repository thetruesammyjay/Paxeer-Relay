"""Typed response models for the PaxRelay control-plane API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    """Base response model that tolerates fields added by newer API versions."""

    model_config = ConfigDict(extra="ignore")


class Agent(APIModel):
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


class AgentWallet(APIModel):
    id: UUID
    agent_id: UUID
    address: str
    is_primary: bool
    label: str | None


class Provider(APIModel):
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


class Money(APIModel):
    amount_atomic: int
    currency: str
    decimals: int


class Service(APIModel):
    id: UUID
    provider_id: UUID
    name: str
    slug: str
    capability: str
    protocols: list[str]
    status: str
    base_url: str | None
    price_per_call: Money | None
    description: str | None


class Policy(APIModel):
    """Policy metadata returned by the current API routes."""

    id: UUID
    name: str
    description: str | None
    mode: str
    version: int
    is_active: bool


class PolicyAssignment(APIModel):
    """A policy-to-agent assignment record."""

    id: UUID
    agent_id: UUID
    policy_id: UUID
    assigned_at: datetime


class ApprovalRequest(APIModel):
    """A human-review request created by a policy-gated tool call."""

    id: UUID
    tool_call_id: UUID
    agent_id: UUID
    capability: str
    provider_id: UUID | None
    service_version_id: UUID | None
    amount_atomic: int
    currency: str
    decimals: int
    recipient_address: str | None
    request_hash: str | None
    policy_id: UUID | None
    policy_version: int | None
    status: str
    reason: str | None
    decision_reason: str | None
    expires_at: datetime | None
    decided_at: datetime | None
    created_at: datetime
