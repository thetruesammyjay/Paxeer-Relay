"""Configuration and result types for the PaxRelay MCP adapter."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator, Mapping
from typing import Any, Literal, Protocol
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ConfigDict, Field, field_validator

from paxrelay.models import PaymentChallenge


class PaidToolDefinition(BaseModel):
    """Operator-configured mapping from an MCP tool name to a capability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    capability: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)*(\.\*)?$",
    )
    description: str = Field(min_length=1, max_length=2048)
    input_schema: dict[str, Any]
    constraints: dict[str, Any] = Field(default_factory=dict)

    @field_validator("input_schema")
    @classmethod
    def validate_input_schema(cls, value: dict[str, Any]) -> dict[str, Any]:
        if value.get("type") != "object":
            raise ValueError("input_schema must have type 'object'.")
        for node in _walk_schema(value):
            for reference_key in ("$ref", "$dynamicRef", "$recursiveRef"):
                reference = node.get(reference_key)
                if reference is not None and not str(reference).startswith("#"):
                    raise ValueError(
                        "input_schema supports only local JSON Schema references."
                    )
        Draft202012Validator.check_schema(value)
        return value

class MCPToolOutcome(BaseModel):
    """Structured application outcome returned from an MCP tool call."""

    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "succeeded",
        "payment_required",
        "approval_pending",
        "invalid_arguments",
        "payment_error",
        "provider_error",
        "gateway_error",
    ]
    idempotency_key: str | None = None
    tool_call_id: UUID | None = None
    payment_requirement: dict[str, Any] | None = None
    approval: dict[str, Any] | None = None
    result: Any = None
    receipt: dict[str, Any] | None = None
    replayed: bool = False
    error: dict[str, Any] | None = None


class PaymentProofProvider(Protocol):
    """Obtain proof through the host application's wallet or approval flow."""

    def __call__(
        self,
        *,
        tool: PaidToolDefinition,
        challenge: PaymentChallenge,
    ) -> Awaitable[str]: ...


IdempotencyKeyFactory = Callable[[PaidToolDefinition, Mapping[str, Any]], str]


def validate_tool_arguments(
    tool: PaidToolDefinition,
    arguments: Mapping[str, Any],
) -> None:
    """Validate arguments using the configured JSON Schema without network refs."""
    validator = Draft202012Validator(
        tool.input_schema,
        format_checker=FormatChecker(),
    )
    validator.validate(dict(arguments))


def _walk_schema(root: Mapping[str, Any]) -> Iterator[Mapping[str, Any]]:
    stack: list[Mapping[str, Any]] = [root]
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
            if isinstance(children, Mapping):
                stack.extend(value for value in children.values() if isinstance(value, Mapping))
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
            if isinstance(child, Mapping):
                stack.append(child)
        for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
            children = node.get(key)
            if isinstance(children, list):
                stack.extend(value for value in children if isinstance(value, Mapping))
