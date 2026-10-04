"""MCP adapters for paid PaxRelay capabilities."""

from paxrelay_mcp.client import PaxRelayMCPAdapter
from paxrelay_mcp.decorators import (
    discover_paid_tools,
    get_paid_tool_definition,
    paid_tool,
)
from paxrelay_mcp.middleware import gateway_adapter_lifespan
from paxrelay_mcp.server import create_server, run_stdio
from paxrelay_mcp.types import (
    IdempotencyKeyFactory,
    MCPToolOutcome,
    PaidToolDefinition,
    PaymentProofProvider,
)

__all__ = [
    "IdempotencyKeyFactory",
    "MCPToolOutcome",
    "PaidToolDefinition",
    "PaymentProofProvider",
    "PaxRelayMCPAdapter",
    "create_server",
    "discover_paid_tools",
    "gateway_adapter_lifespan",
    "get_paid_tool_definition",
    "paid_tool",
    "run_stdio",
]
