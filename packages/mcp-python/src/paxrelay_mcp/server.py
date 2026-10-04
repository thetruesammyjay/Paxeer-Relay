"""MCP protocol server for configured PaxRelay paid tools."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from mcp.server.lowlevel import Server
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from paxrelay_mcp.client import PaxRelayMCPAdapter
from paxrelay_mcp.types import IdempotencyKeyFactory, MCPToolOutcome, PaidToolDefinition


def create_server(
    *,
    tools: Sequence[PaidToolDefinition],
    adapter: PaxRelayMCPAdapter | None = None,
    lifespan: Callable[[Any], Any] | None = None,
    idempotency_key_factory: IdempotencyKeyFactory | None = None,
    name: str = "paxrelay",
    version: str = "0.1.0",
) -> Server[Any]:
    """Create a low-level MCP server that routes declared tools through PaxRelay.

    If ``adapter`` is omitted, the server resolves it from the ``paxrelay``
    lifespan value produced by :func:`gateway_adapter_lifespan`.
    """
    tool_definitions = tuple(tools)
    by_name: dict[str, PaidToolDefinition] = {}
    for definition in tool_definitions:
        if definition.name in by_name:
            raise ValueError(f"Duplicate paid MCP tool name: {definition.name}")
        by_name[definition.name] = definition

    async def on_list_tools(_: Any, __: Any) -> ListToolsResult:
        return ListToolsResult(
            tools=[
                Tool(
                    name=definition.name,
                    description=definition.description,
                    input_schema=definition.input_schema,
                    output_schema=MCPToolOutcome.model_json_schema(),
                )
                for definition in tool_definitions
            ]
        )

    async def on_call_tool(context: Any, params: Any) -> CallToolResult:
        definition = by_name.get(params.name)
        if definition is None:
            return _tool_result(
                MCPToolOutcome(
                    status="gateway_error",
                    error={
                        "code": "unknown_tool",
                        "message": "This tool is not configured on the PaxRelay server.",
                    },
                )
            )

        arguments = params.arguments or {}
        if not isinstance(arguments, Mapping):
            arguments = {}
        try:
            idempotency_key = (
                idempotency_key_factory(definition, arguments)
                if idempotency_key_factory is not None
                else _request_idempotency_key(
                    session=context.session,
                    request_id=context.request_id,
                    tool_name=definition.name,
                )
            )
        except Exception:
            return _tool_result(
                MCPToolOutcome(
                    status="gateway_error",
                    error={
                        "code": "idempotency_key_unavailable",
                        "message": "The request could not be assigned a safe retry key.",
                    },
                )
            )

        if not isinstance(idempotency_key, str) or not idempotency_key:
            return _tool_result(
                MCPToolOutcome(
                    status="gateway_error",
                    error={
                        "code": "invalid_idempotency_key",
                        "message": "The configured retry key is empty or invalid.",
                    },
                )
            )

        current_adapter = adapter
        if current_adapter is None:
            lifespan_context = getattr(context, "lifespan_context", None)
            candidate = (
                lifespan_context.get("paxrelay")
                if isinstance(lifespan_context, Mapping)
                else None
            )
            if isinstance(candidate, PaxRelayMCPAdapter):
                current_adapter = candidate

        if current_adapter is None:
            return _tool_result(
                MCPToolOutcome(
                    status="gateway_error",
                    idempotency_key=idempotency_key,
                    error={
                        "code": "adapter_unavailable",
                        "message": "The PaxRelay gateway adapter is not available.",
                    },
                )
            )

        try:
            outcome = await current_adapter.call_tool(
                definition,
                arguments=arguments,
                idempotency_key=idempotency_key,
            )
        except Exception:
            outcome = MCPToolOutcome(
                status="gateway_error",
                idempotency_key=idempotency_key,
                error={
                    "code": "tool_invocation_failed",
                    "message": "The paid tool request could not be completed.",
                },
            )
        return _tool_result(outcome)

    kwargs: dict[str, Any] = {
        "name": name,
        "version": version,
        "on_list_tools": on_list_tools,
        "on_call_tool": on_call_tool,
    }
    if lifespan is not None:
        kwargs["lifespan"] = lifespan
    return Server(**kwargs)


async def run_stdio(server: Server[Any]) -> None:
    """Run a low-level MCP server over stdio until its client disconnects."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def _tool_result(outcome: MCPToolOutcome) -> CallToolResult:
    payload = outcome.model_dump(mode="json")
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            )
        ],
        structured_content=payload,
        is_error=outcome.status
        in {"invalid_arguments", "payment_error", "provider_error", "gateway_error"},
    )


def _request_idempotency_key(
    *,
    session: object,
    request_id: object,
    tool_name: str,
) -> str:
    """Derive a bounded retry key scoped to one MCP session and request."""
    if request_id is None:
        raise ValueError("An MCP request ID is required for safe idempotency.")
    material = f"paxrelay-mcp\0{id(session)}\0{tool_name}\0{request_id}".encode()
    return hashlib.sha256(material).hexdigest()
