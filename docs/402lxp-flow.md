# 402LXP paid-call flow

> **Implementation status:** This page describes PaxRelay's current internal
> quote-and-proof flow. Its JSON `payment_requirement` is not the published
> LayerX 402LXP HTTP v2 `PAYMENT-REQUIRED` envelope. The live adapter now fails
> closed until official SDK receipt verification is integrated. See the
> [protocol integration status](protocol-integration.md) and the
> [repeatable local demo](DEMO-RUNBOOK.md).

The gateway separates request authorization from payment proof submission. An
agent first asks to invoke a capability. PaxRelay selects an eligible service,
checks policy, and returns an HTTP 402 payment requirement. The agent then
submits proof against the exact quote. Only verified proof allows the gateway
to forward the request.

## Lifecycle

```mermaid
sequenceDiagram
    participant A as Agent
    participant G as PaxRelay gateway
    participant P as Policy and routing
    participant X as Paxeer / LayerX adapter
    participant S as Selected service
    A->>G: POST /v1/invoke + bearer key + X-Agent-Id
    G->>G: Look up completed idempotency key
    G->>P: Find candidate services and select a route
    P-->>G: Provider, service version, price, and score
    G->>P: Evaluate active agent policy
    P-->>G: Allow, deny, or require approval
    G->>G: Persist immutable quote and nonce
    G-->>A: HTTP 402 + payment requirement + tool_call_id
    A->>X: Pay using the presented requirement
    A->>G: POST /v1/invoke/{tool_call_id} + proof
    G->>G: Check quote fields and nonce state
    G->>X: Verify transfer / transaction
    X-->>G: Verification result
    G->>G: Record verified payment and consume nonce
    G->>S: POST original JSON arguments
    S-->>G: Provider response
    G->>G: Hash request/response; issue signed receipt
    G-->>A: Result + receipt
```

## Phase 1: quote and challenge

`POST /v1/invoke` accepts:

```json
{
  "capability": "research.web-search",
  "idempotency_key": "agent-request-001",
  "arguments": {"query": "Paxeer"},
  "constraints": {"maximum_price": {"amount_atomic": 1000000}}
}
```

The gateway requires a bearer API key with `gateway:invoke` and an
`X-Agent-Id` header. The key authenticates a tenant; the header selects an
active agent inside that key's organisation, project, and environment. The
gateway finds service versions for the capability, runs hard routing filters
and scoring, then supplies the chosen service's amount and metrics to the
assigned active policy. Policy happens after route selection so it can see the
selected price and provider data.

When the policy has a daily or monthly budget, the gateway locks that agent's
database row while it reads verified spend and unexpired quote reservations.
Once an allowed quote is saved, its amount is reserved until the quote expires
or its nonce is consumed with a verified payment.

An allowed request receives a short-lived quote. A quote binds:

- tool-call ID;
- provider and immutable service-version IDs;
- amount and currency;
- configured chain ID (125 by default) and recipient;
- canonical request hash;
- a unique random nonce; and
- an expiry time (300 seconds by default).

The response uses HTTP 402 and includes `payment_requirement` and
`tool_call_id`. The requirement identifies `payment_scheme: "402LXP"`,
`network: "paxeer"`, `settlement_layer: "layerx"`, `currency: "USDX"`,
`currency_decimals: 6`, `amount_atomic`, `recipient`, `quote_id`,
`request_hash`, `nonce`, `expires_at`, and `chain_id`.

The request hash is SHA-256 of compact JSON with sorted argument keys. It binds
the proof to the submitted arguments; changing those arguments requires a new
quote.

## Phase 2: proof verification

The agent submits `POST /v1/invoke/{tool_call_id}` with the same bearer key and
agent ID, plus a JSON object whose `proof` property is itself a JSON string.
The gateway confirms that the stored call belongs to that exact agent before
loading its quote. The local verifier checks expiry,
quote ID, request hash, amount, recipient, nonce, the quote's configured chain
ID, and payment scheme. It then calls the configured adapter. The official adapter additionally
requires a `layerx_transaction_hash` and asks LayerX for that transaction,
checking amount, recipient, and quote ID/memo.

The local checklist fails closed: any mismatch returns HTTP 402 and the
provider is not called. A proof must be a JSON object with a decimal integer
amount; malformed JSON shapes and values are rejected without turning into an
internal server error. On verification success, the gateway claims the quote
nonce with a conditional database update, persists the payment intent and
verified payment in the same transaction, then commits before forwarding. A
second submission of the same quote receives HTTP 409. The provider request is
recorded as reserved before the network call begins.

If policy returns `require_approval`, the gateway stores a tenant-scoped
approval request bound to the selected provider, immutable service version,
amount, payment recipient, and policy version. A reviewer with
`approvals:write` can approve or reject it through the control-plane API. The
agent then retries the original request with the same idempotency key. The
gateway checks that the approved snapshot and active policy still match and
recalculates budget usage before it issues a payment quote.

## Phase 3: provider execution and receipt

The gateway POSTs the original arguments as JSON to the selected service
version's `endpoint_url`, using the smaller of its configured timeout and the
gateway-wide timeout cap. It stops reading a response once the configured
response-size cap is exceeded and records that attempt as unknown, because the
provider may already have completed the work. A 2xx response within the cap is
treated as successful execution. Non-2xx responses and timeouts are classified
separately.

For success, PaxRelay stores a receipt containing request and response hashes,
payment and LayerX references, route strategy and score, service/version,
execution status, timestamps, and latency. The receipt is signed locally by
default. For provider failure, the payment can remain verified while the
request is failed; this flow does not currently refund the payment.

## Replay and retry behavior

The gateway takes a PostgreSQL transaction advisory lock for
`(agent_id, idempotency_key)` before checking for an existing request. A repeat
with the same arguments returns the same unexpired payment requirement; reusing
the key with different arguments, capability, or constraints returns HTTP 409.
Terminal failures also return 409, and an expired quote returns 410 so a caller
must choose a new key. A delivered request replays its provider result and
signed receipt from storage when the client repeats either the original invoke
or its completion request. The gateway does not call the provider again.
Results are bounded by `GATEWAY_MAX_RESPONSE_BYTES` and retained in the
`tool_calls` row; apply the same access, backup, and retention controls used for
other stored provider data. Requests completed before migration `0010` do not
have a saved result and return HTTP 409 with `completed_result_unavailable` on
replay. Although the domain has retryable execution states and configuration
for multiple provider attempts, the current invoke path creates one attempt and
does not execute provider failover. Do not rely on automatic retries.

PaxRelay records nonce use in PostgreSQL with an atomic conditional update,
while locking the same agent row used by budget reservations. A verified
payment replaces its active reservation in the same transaction, so concurrent
quotes cannot miss both the reservation and payment. The mock adapter also
tracks used nonces in memory, but that process-local set is not the production
replay control. Recovery of calls left in the reserved state remains
unfinished; the database lock and replay behavior still need verification with
concurrent PostgreSQL submissions.

## Local simulator

`apps/simulator` exposes separate fake payment and settlement endpoints. It
returns fabricated transaction hashes and can return a configured simulated
failure rate. Its in-memory registry resets on restart. It demonstrates
application wiring; it is not a source of payment truth or a production
verification service.

## Status model

The domain keeps request, payment, and execution state separately. For example,
a request may have `request_state=failed`, `payment_state=verified`, and an
execution attempt state of `timeout`. Do not collapse these into a single
success/failure flag in clients or reports.
