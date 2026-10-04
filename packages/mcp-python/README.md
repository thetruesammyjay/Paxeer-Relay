# PaxRelay MCP adapter

`paxrelay-mcp` exposes operator-configured PaxRelay capabilities as MCP tools.
It requests a quote through the gateway, optionally asks a host-supplied wallet
callback for payment proof, then returns the provider result and signed receipt
as structured tool output.

The adapter does not hold wallet keys, construct transfers, or interpret a
receipt as proof that a provider's result is factually correct. Use a dedicated
API key with `gateway:invoke` and an agent ID from the same tenant.

## Example

```python
import asyncio
import os

from paxrelay_mcp import (
    PaidToolDefinition,
    create_server,
    gateway_adapter_lifespan,
    run_stdio,
)

tools = [
    PaidToolDefinition(
        name="market_snapshot",
        capability="research.market-snapshot",
        description="Retrieve a market snapshot for a symbol.",
        input_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "minLength": 1, "maxLength": 20}
            },
            "required": ["symbol"],
            "additionalProperties": False,
        },
    )
]

lifespan = gateway_adapter_lifespan(
    api_key=os.environ["PAXRELAY_API_KEY"],
    agent_id=os.environ["PAXRELAY_AGENT_ID"],
    base_url=os.getenv("PAXRELAY_GATEWAY_URL", "http://localhost:8080"),
)

server = create_server(
    adapter=None,
    tools=tools,
    lifespan=lifespan,
)

async def main() -> None:
    await run_stdio(server)


if __name__ == "__main__":
    asyncio.run(main())
```

The low-level MCP server publishes the configured input JSON Schemas unchanged
and validates arguments again before the gateway call. Its output schema
describes the structured status and result returned for every call.

When no `payment_proof_provider` is configured, the tool returns
`status="payment_required"`, the `tool_call_id`, and the payment requirement.
That MCP call then ends. The host can handle the requirement through its own
wallet and gateway flow. An application embedding the adapter can also call
`PaxRelayMCPAdapter.submit_proof(...)` directly. To keep the full paid request
and result inside one MCP call, pass an async proof provider to
`gateway_adapter_lifespan`. The callback receives the tool definition and
challenge; it must use an approved wallet or operator flow and return the
caller-produced proof.

The structured result has a `status` field. Success includes `result` and the
signed `receipt`. Approval, payment, provider, and gateway outcomes remain
distinct. By default, the server derives an idempotency key from the MCP
session, tool name, and request ID, so retransmitting the same request in that
session reuses the original gateway call. For recovery across a reconnect or
server restart, provide an `idempotency_key_factory` based on a durable host
request identifier. Use a new request ID and key for a new intentional action.

## Current boundary

This package implements the agent-facing MCP adapter. The gateway still
forwards provider calls over HTTP. Registering a service with `protocols=["mcp"]`
does not yet connect to an upstream MCP provider; provider-side MCP transport
is a separate integration task.
