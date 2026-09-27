# MCP integration

Model Context Protocol (MCP) support is part of PaxRelay's product direction,
but usable MCP adapters are not implemented in the current checkout. The
Python MCP package contains empty module files, and the TypeScript MCP package
is absent. The gateway currently exposes a generic HTTP JSON invocation rather
than an MCP server or client.

## Intended integration shape

PaxRelay needs two integration surfaces:

1. **Provider adapter:** expose an existing MCP tool through a PaxRelay service
   and apply the payment check before the tool executes.
2. **Agent adapter:** let an MCP client discover paid tools, handle the 402LXP
   requirement, submit proof, and return the result and receipt as structured
   tool output.

The control-plane service model already has a `capability`, supported
`protocols`, immutable service versions, endpoint URL, per-call price, and
optional schema field. The current API accepts protocol names but does not
implement an MCP protocol transport.

## Provider-side requirements

A future provider package should:

- map each MCP tool to a stable capability identifier;
- publish tool name, description, input schema, version, and price;
- preserve the original tool arguments and validate them against the published
  schema;
- call the tool only after payment proof is verified;
- return the provider's result without silently changing its meaning;
- report provider errors and execution timing separately from payment state;
- avoid re-executing the same idempotency key unless the provider operation is
  known to be safe to retry.

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

The gateway's current request shape is:

```json
{
  "capability": "research.web-search",
  "idempotency_key": "stable-client-key",
  "arguments": {"query": "example"},
  "constraints": {}
}
```

It returns a 402 requirement before service execution. This HTTP flow is the
current integration boundary; it is not an MCP transport implementation. Use
the API and protocol references for the exact request and proof fields.

## Implementation sequence

1. Restore and implement the Python provider and client package modules.
2. Add a tool manifest mapping and stable capability naming rules.
3. Define how 402 challenges and payment errors map to MCP tool responses.
4. Add cancellation and timeout behavior without losing payment state.
5. Add integration examples against `apps/simulator` and a fake MCP server.
6. Add a TypeScript implementation only after the wire contract is stable.
7. Document package support and installation only after publishable packages
   exist. The current repository does not publish `paxrelay` or an MCP CLI.
