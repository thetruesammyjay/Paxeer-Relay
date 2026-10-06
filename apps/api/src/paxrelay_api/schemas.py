"""Pydantic request/response schemas for the control-plane API.

These are the wire contracts for the dashboard and SDKs. They deliberately
mirror the domain models but stay separate so the HTTP surface can evolve
independently of the internal domain layer.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from jsonschema import Draft202012Validator, SchemaError
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator

from paxrelay_api.security.scopes import parse_scopes


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------


class MoneyIn(BaseModel):
    """A human-friendly monetary amount accepted on input."""

    amount_atomic: int = Field(ge=0)
    currency: Literal["USDX"] = "USDX"
    decimals: Literal[6] = 6


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
    # EVM checksummed or lowercase 20-byte hex address, or omitted.
    wallet_address: str | None = Field(
        default=None, max_length=42, pattern=r"^0x[0-9a-fA-F]{40}$"
    )
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
    # EVM checksummed or lowercase 20-byte hex address, or omitted.
    wallet_address: str | None = Field(
        default=None, max_length=42, pattern=r"^0x[0-9a-fA-F]{40}$"
    )
    description: str | None = None
    website_url: str | None = Field(
        default=None, max_length=2048, pattern=r"^https?://"
    )


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
    website_url: str | None = None


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


class ServiceHealthConfig(BaseModel):
    """Safe path and timing configuration for read-only health probes."""

    endpoint: str = Field(default="/health", min_length=1, max_length=512)
    interval_seconds: int = Field(default=30, ge=5, le=3600)
    timeout_seconds: int = Field(default=5, ge=1, le=30)
    failure_threshold: int = Field(default=3, ge=1, le=20)

    @field_validator("endpoint")
    @classmethod
    def validate_health_endpoint(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            not value.startswith("/")
            or value.startswith("//")
            or "\\" in value
            or parsed.scheme
            or parsed.netloc
            or parsed.query
            or parsed.fragment
            or any(ord(char) < 0x20 or ord(char) == 0x7F for char in value)
            or any(segment in {".", ".."} for segment in parsed.path.split("/"))
        ):
            raise ValueError(
                "health endpoint must be an absolute path on the service host"
            )
        return value


class ServiceHealthOut(ServiceHealthConfig):
    """Configured probe settings plus the latest worker observation."""

    last_check_at: datetime | None = None
    last_check_passing: bool | None = None
    consecutive_health_failures: int = Field(default=0, ge=0)
    last_check_status_code: int | None = Field(default=None, ge=100, le=599)


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    capability: str = Field(pattern=r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)*(\.\*)?$")
    protocols: list[Literal["http", "mcp"]] = Field(
        default_factory=lambda: ["http"], min_length=1, max_length=1
    )
    mcp_tool_name: str | None = Field(
        default=None, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$"
    )
    mcp_input_schema: dict[str, Any] | None = None
    price_per_call: MoneyIn
    base_url: str = Field(min_length=8, max_length=2048, pattern=r"^https?://")
    endpoint_url: str = Field(min_length=8, max_length=2048, pattern=r"^https?://")
    health: ServiceHealthConfig = Field(default_factory=ServiceHealthConfig)
    version: str = Field(default="1.0.0", min_length=1, max_length=32)
    description: str | None = None

    @model_validator(mode="after")
    def validate_protocol_contract(self) -> "ServiceCreate":
        if self.protocols == ["mcp"]:
            if not self.mcp_tool_name or self.mcp_input_schema is None:
                raise ValueError(
                    "MCP services require mcp_tool_name and mcp_input_schema."
                )
            schema = self.mcp_input_schema
            if schema.get("type") != "object":
                raise ValueError("MCP input schema must have type 'object'.")
            try:
                encoded_schema = json.dumps(
                    schema,
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                ).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise ValueError("MCP input schema must be valid JSON.") from exc
            if len(encoded_schema) > 32_768:
                raise ValueError("MCP input schema must not exceed 32 KiB.")
            for node in _walk_json_schema(schema):
                for key in ("$ref", "$dynamicRef", "$recursiveRef"):
                    reference = node.get(key)
                    if reference is not None and not str(reference).startswith("#"):
                        raise ValueError(
                            "MCP input schema may use only local JSON Schema references."
                        )
            try:
                Draft202012Validator.check_schema(schema)
            except (SchemaError, RecursionError) as exc:
                raise ValueError(
                    "MCP input schema is not a valid Draft 2020-12 schema."
                ) from exc
        elif self.mcp_tool_name is not None or self.mcp_input_schema is not None:
            raise ValueError("MCP metadata is only valid when protocols is ['mcp'].")
        return self


def _walk_json_schema(root: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Visit nested schema objects when checking for remote references."""
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        for key in (
            "properties",
            "$defs",
            "definitions",
            "patternProperties",
            "dependentSchemas",
            "propertyNames",
        ):
            children = node.get(key)
            if isinstance(children, dict):
                stack.extend(
                    value for value in children.values() if isinstance(value, dict)
                )
        for key in (
            "items",
            "contains",
            "additionalProperties",
            "unevaluatedProperties",
            "unevaluatedItems",
            "contentSchema",
            "not",
            "if",
            "then",
            "else",
        ):
            child = node.get(key)
            if isinstance(child, dict):
                stack.append(child)
        for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
            children = node.get(key)
            if isinstance(children, list):
                stack.extend(value for value in children if isinstance(value, dict))


class ServiceStatusUpdate(BaseModel):
    """Operational service state that controls eligibility for new routes."""

    status: Literal["active", "inactive"]


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
    health: ServiceHealthOut
    description: str | None


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    mode: Literal["observe", "warn", "enforce"] = "enforce"
    maximum_per_call: MoneyIn | None = None
    daily_budget: MoneyIn | None = None
    monthly_budget: MoneyIn | None = None
    allowed_capabilities: list[str] = Field(default_factory=list, max_length=100)
    allowed_providers: list[str] = Field(default_factory=list, max_length=100)
    blocked_providers: list[str] = Field(default_factory=list, max_length=100)
    minimum_provider_reputation: float | None = Field(default=None, ge=0, le=1)
    minimum_provider_success_rate: float | None = Field(default=None, ge=0, le=1)
    maximum_accepted_latency_ms: int | None = Field(
        default=None,
        ge=0,
        le=600_000,
    )
    maximum_consecutive_failures: int | None = Field(default=None, ge=1, le=1000)
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


class PolicyRulesOut(BaseModel):
    maximum_per_call: MoneyIn | None = None
    daily_budget: MoneyIn | None = None
    monthly_budget: MoneyIn | None = None
    allowed_capabilities: list[str] = Field(default_factory=list)
    allowed_providers: list[str] = Field(default_factory=list)
    blocked_providers: list[str] = Field(default_factory=list)
    allowed_contracts: list[str] = Field(default_factory=list)
    minimum_provider_reputation: float | None = Field(default=None, ge=0, le=1)
    minimum_provider_success_rate: float | None = Field(default=None, ge=0, le=1)
    maximum_accepted_latency_ms: int | None = Field(default=None, ge=0)
    approval_threshold: MoneyIn | None = None
    maximum_consecutive_failures: int | None = Field(default=None, ge=1)
    maximum_drawdown: MoneyIn | None = None
    session_expiry_seconds: int | None = None
    allowed_currencies: list[str] = Field(default_factory=list)


class PolicyDetailOut(PolicyOut):
    rules: PolicyRulesOut
    assignments: list[PolicyAssignmentOut] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    key_type: str = Field(default="test", pattern=r"^(test|live)$")
    # Colon-paired grants, e.g. "agents:read:agents:write".
    scopes: str = Field(
        min_length=1,
        max_length=512,
        pattern=r"^(?:[a-z][a-z0-9-]*:(?:read|write)|gateway:invoke)(?::(?:[a-z][a-z0-9-]*:(?:read|write)|gateway:invoke))*$",
    )
    expires_in_days: int = Field(default=90, ge=1, le=365)

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: str) -> str:
        parse_scopes(value)
        return value


class ApiKeyOut(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    key_type: str
    scopes: str = ""
    expires_at: datetime | None = None
    created_at: datetime | None = None
    last_used_at: datetime | None = None
    is_active: bool = True
    # The raw key is returned exactly once, at creation time.
    raw_key: str | None = None


# ---------------------------------------------------------------------------
# Receipts
# ---------------------------------------------------------------------------


class ReceiptOut(BaseModel):
    id: UUID
    tool_call_id: UUID
    agent_id: UUID
    provider_id: UUID
    service_id: UUID
    service_version: str
    capability: str
    request_hash: str
    response_hash: str
    payment_amount: int
    payment_currency: str
    layerx_transaction: str | None
    execution_latency_ms: int
    execution_status: str
    receipt_hash: str | None
    signature: str | None
    signing_key_id: str | None
    issued_at: datetime


class ReceiptVerificationKeyOut(BaseModel):
    """One public key and its accepted receipt issue-time window."""

    key_id: str
    public_key_pem: str
    status: Literal["active", "retired", "revoked"]
    not_before: datetime
    not_after: datetime | None


class ReceiptKeyringOut(BaseModel):
    """Public receipt-verification manifest served to SDK consumers."""

    version: Literal[1]
    keys: list[ReceiptVerificationKeyOut]


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------


class TransactionOut(BaseModel):
    id: UUID
    agent_id: UUID
    capability: str
    request_state: str
    payment_state: str
    execution_state: str
    created_at: datetime
    updated_at: datetime


class ExecutionAttemptOut(BaseModel):
    """Safe operational metadata for one provider execution attempt."""

    id: UUID
    tool_call_id: UUID
    provider_id: UUID
    service_version_id: UUID
    attempt_number: int
    execution_state: str
    request_forwarded_at: datetime | None
    response_received_at: datetime | None
    latency_ms: int | None
    http_status_code: int | None
    provider_error_code: str | None
    created_at: datetime
    updated_at: datetime


class ApprovalDecisionIn(BaseModel):
    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, max_length=512)


class ApprovalOut(BaseModel):
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


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class AnalyticsSpendOut(BaseModel):
    period: str
    start_date: datetime
    end_date: datetime
    total_amount_atomic: int
    currency: str
    decimals: int
    transaction_count: int


class AnalyticsCapabilityOut(BaseModel):
    capability: str
    total_amount_atomic: int
    currency: str
    decimals: int
    call_count: int


class AuditLogOut(BaseModel):
    id: UUID
    event_type: str
    actor_id: str
    resource_type: str
    resource_id: str
    details: dict[str, object] | None
    ip_address: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


class WebhookCreate(BaseModel):
    url: str = Field(min_length=1, max_length=2048, pattern=r"^https?://")
    event_types: list[str] = Field(min_length=1, max_length=100)
    secret: SecretStr = Field(min_length=32, max_length=128)
    description: str | None = Field(default=None, max_length=256)


class WebhookUpdate(BaseModel):
    url: str | None = Field(None, min_length=1, max_length=2048, pattern=r"^https?://")
    event_types: list[str] | None = Field(None, min_length=1)
    secret: SecretStr | None = Field(None, min_length=32, max_length=128)
    is_active: bool | None = None
    description: str | None = Field(default=None, max_length=256)


class WebhookOut(BaseModel):
    id: UUID
    url: str
    event_types: list[str]
    secret_configured: bool
    is_active: bool
    description: str | None
    created_at: datetime


class WebhookDeliveryOut(BaseModel):
    id: UUID
    event_type: str
    status: str
    attempt_count: int
    http_status_code: int | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    next_attempt_at: datetime | None
    delivered_at: datetime | None


class WebhookDeliveryPageOut(BaseModel):
    items: list[WebhookDeliveryOut]
    next_cursor_created_at: datetime | None = None
    next_cursor_id: UUID | None = None


class SettlementReconciliationOut(BaseModel):
    id: UUID
    payment_id: UUID
    payment_state: str
    reconciliation_status: str
    layerx_transaction_hash: str | None
    layerx_batch_id: str | None
    l1_settlement_id: str | None
    l1_block_number: int | None
    l1_transaction_hash: str | None
    l1_commitment_hash: str | None
    internal_checked_at: datetime | None
    last_checked_at: datetime | None
    attempt_count: int
    next_attempt_at: datetime | None
    last_error: str | None
    reconciled_at: datetime | None
    mismatch_details: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class SettlementReconciliationPageOut(BaseModel):
    items: list[SettlementReconciliationOut]
    next_cursor_created_at: datetime | None = None
    next_cursor_id: UUID | None = None


# ---------------------------------------------------------------------------
# Batch operations
# ---------------------------------------------------------------------------


class BatchAgentCreate(BaseModel):
    agents: list[AgentCreate] = Field(min_length=1, max_length=100)


class BatchAgentResult(BaseModel):
    success: bool
    agent: AgentOut | None = None
    error: str | None = None


class BatchAgentResponse(BaseModel):
    results: list[BatchAgentResult]
    success_count: int
    failure_count: int


class BatchProviderCreate(BaseModel):
    providers: list[ProviderCreate] = Field(min_length=1, max_length=100)


class BatchProviderResult(BaseModel):
    success: bool
    provider: ProviderOut | None = None
    error: str | None = None


class BatchProviderResponse(BaseModel):
    results: list[BatchProviderResult]
    success_count: int
    failure_count: int
