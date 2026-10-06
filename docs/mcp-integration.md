# MCP integration

The Python package `packages/mcp-python` implements the agent-facing MCP
adapter. It exposes configured PaxRelay capabilities as MCP tools, requests
quotes through the gateway, and returns the result and receipt as structured
tool output. Payment proof remains with the host application's wallet flow.
The gateway supports provider calls over HTTP JSON and MCP Streamable HTTP.
The TypeScript MCP package is not implemented.

## Integration model

PaxRelay has two integration surfaces:

1. **Provider dispatch:** publish an existing MCP tool as a versioned PaxRelay
   service. The gateway checks the payment before calling the tool.
2. **Agent adapter:** let an MCP client discover paid tools, handle the 402LXP
   requirement, submit proof, and return the result and receipt as structured
   tool output.

The control-plane service model records supported `protocols`, immutable
service versions, endpoint URL, and per-call price. A service version pins its
protocol and, for MCP, the tool name and input JSON Schema. Publishing accepts
one protocol: `http` or `mcp`. gRPC remains unsupported.

## Provider-side behavior

The API stores the protocol, MCP tool name, and declared input schema on the
immutable service version. The gateway validates request arguments before
creating a quote. After payment verification and execution reservation, it
opens an MCP Streamable HTTP session, confirms the remote tool and schema still
match the published version, and calls that tool. It does not retry a tool call
after dispatch begins. If the result is uncertain, the execution stays
unknown for reconciliation instead of being replayed.

A provider MCP service must:

- map each MCP tool to a stable capability identifier;
- publish tool name, description, input schema, version, and price;
- preserve the original tool arguments and validate them against the published
  schema before creating a payment quote;
- confirm that the upstream tool name and schema still match the immutable
  published version;
- call the tool only after payment proof is verified and the execution
  reservation has been committed;
- return the provider's result without silently changing its meaning;
- report provider errors and execution timing separately from payment state;
- avoid re-executing a paid request when the provider outcome is uncertain.

Do not place secrets in tool metadata or expose unrestricted provider host
access through a generic tool wrapper.

## Agent-side requirements

A future agent adapter should discover paid-tool metadata, present a clear
amount and network to the wallet/operator, obtain proof from the configured
wallet flow, and submit that proof to
`POST /v1/invoke/{tool_call_id}`. It should preserve the distinction among:

- a tool result;
- a payment-verification error;
- a provider execution error; and
- a receipt describing what PaxRelay observed.

The MCP client must not treat the receipt as proof that the provider's result
is factually correct.

## HTTP gateway boundary

The paid-call control-plane API uses this HTTP request shape:

```json
{
  "capability": "research.web-search",
  "idempotency_key": "stable-client-key",
  "arguments": {"query": "example"},
  "constraints": {}
}
```

It returns a 402 requirement before service execution. Agents use this HTTP
flow regardless of whether the selected provider service uses HTTP JSON or MCP
Streamable HTTP. Use the API and protocol references for the exact request and
proof fields.

## Current implementation

`paxrelay-mcp` provides `PaidToolDefinition`, a `@paid_tool` manifest
decorator, `PaxRelayMCPAdapter`, a low-level MCP server factory, a stdio runner,
and a managed gateway-client lifespan helper. The server publishes each
configured input JSON Schema as declared, advertises a schema for its
structured outcomes, and validates arguments again before invoking the
gateway. It validates local JSON Schema references and rejects remote
references. It maps approval, payment, provider, and gateway outcomes into a
structured response. By default, the server derives an idempotency key from
the MCP session, tool name, and request ID. Configure a durable key factory
for retries that cross a reconnect or server restart. The adapter never
retries a request automatically.

If no proof provider is configured, a tool call returns the 402 payment
requirement for the host to process separately. An optional async proof
provider lets the host handle payment during the same MCP call without giving
PaxRelay wallet keys. The package does not submit transfers itself.

## Remaining implementation sequence

1. Add and run fake MCP server coverage for cancellation, timeout, tool-schema
   drift, response limits, and proof replay.
2. Validate the provider MCP handshake and tool contract with staging
   providers before enabling it for real paid traffic.
3. Add a TypeScript adapter after the Python wire contract is stable.
4. Publish the Python package only after its API and install instructions are
   stable; it is currently a workspace package.
