"""Declarative decorators for collecting paid MCP tool manifests."""

from __future__ import annotations

from collections.abc import Iterable
from types import ModuleType
from typing import Any, Callable, TypeVar

from paxrelay_mcp.types import PaidToolDefinition

F = TypeVar("F", bound=Callable[..., Any])
_PAID_TOOL_ATTRIBUTE = "__paxrelay_paid_tool__"


def paid_tool(
    *,
    capability: str,
    description: str,
    input_schema: dict[str, Any],
    name: str | None = None,
    constraints: dict[str, Any] | None = None,
) -> Callable[[F], F]:
    """Attach a paid-tool manifest to a function for registration.

    The decorated function is a declaration and is not called by the adapter;
    the gateway routes the paid invocation to the configured provider.
    """

    def decorate(function: F) -> F:
        definition = PaidToolDefinition(
            name=name or function.__name__,
            capability=capability,
            description=description or function.__doc__ or function.__name__,
            input_schema=input_schema,
            constraints=constraints or {},
        )
        setattr(function, _PAID_TOOL_ATTRIBUTE, definition)
        return function

    return decorate


def get_paid_tool_definition(value: Any) -> PaidToolDefinition:
    """Return a manifest from a definition or decorated declaration."""
    if isinstance(value, PaidToolDefinition):
        return value
    definition = getattr(value, _PAID_TOOL_ATTRIBUTE, None)
    if not isinstance(definition, PaidToolDefinition):
        raise TypeError("Expected a PaidToolDefinition or a function decorated with @paid_tool.")
    return definition


def discover_paid_tools(source: ModuleType | Iterable[Any]) -> list[PaidToolDefinition]:
    """Collect decorated declarations from a module or iterable in stable order."""
    values = vars(source).values() if isinstance(source, ModuleType) else source
    definitions: dict[str, PaidToolDefinition] = {}
    for value in values:
        definition = getattr(value, _PAID_TOOL_ATTRIBUTE, None)
        if isinstance(definition, PaidToolDefinition):
            if definition.name in definitions:
                raise ValueError(f"Duplicate paid MCP tool name: {definition.name}")
            definitions[definition.name] = definition
    return list(definitions.values())
