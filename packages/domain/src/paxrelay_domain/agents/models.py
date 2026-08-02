"""Agent domain models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from paxrelay_domain.types import Environment, WalletAddress


class AgentStatus(str, Enum):
    """Lifecycle state of a registered agent."""

    ACTIVE = "active"
    PAUSED = "paused"
    REVOKED = "revoked"


class Agent(BaseModel):
    """An autonomous software identity authorised to purchase services.

    An agent is always scoped to an organisation and project, and must
    be associated with a Paxeer wallet address to initiate payments.
    """

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9][a-z0-9_-]*$",
        description="URL-safe identifier unique within a project.",
    )
    organisation_id: UUID
    project_id: UUID
    environment: Environment = Environment.DEVELOPMENT
    wallet_address: WalletAddress | None = Field(
        default=None,
        description="Paxeer wallet or policy-bound smart wallet address.",
    )
    status: AgentStatus = AgentStatus.ACTIVE
    description: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def is_operable(self) -> bool:
        """Return True only when the agent can initiate new payments."""
        return self.status == AgentStatus.ACTIVE

    def with_status(self, status: AgentStatus) -> "Agent":
        return self.model_copy(
            update={"status": status, "updated_at": datetime.utcnow()}
        )


class Wallet(BaseModel):
    """A Paxeer wallet or policy-bound smart wallet associated with an agent."""

    model_config = {"frozen": True}

    id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    address: WalletAddress
    is_primary: bool = True
    label: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
