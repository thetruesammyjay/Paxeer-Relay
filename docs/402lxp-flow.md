# 402LXP paid-call flow

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
    A->>G: POST /v1/invoke + X-Agent-Id
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

The gateway currently reads `X-Agent-Id` as a UUID and requires an active
agent. It finds service versions for the capability, runs hard routing filters
and scoring, then supplies the chosen service's amount and metrics to the
assigned active policy. Policy happens after route selection so it can see the
selected price and provider data.

An allowed request receives a short-lived quote. A quote binds:

- tool-call ID;
- provider and immutable service-version IDs;
- amount and currency;
- chain ID (125) and recipient;
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

The agent submits `POST /v1/invoke/{tool_call_id}` with a JSON object whose
`proof` property is itself a JSON string. The local verifier checks expiry,
quote ID, request hash, amount, recipient, nonce, chain ID 125, and payment
scheme. It then calls the configured adapter. The official adapter additionally
requires a `layerx_transaction_hash` and asks LayerX for that transaction,
checking amount, recipient, and quote ID/memo.

The local checklist fails closed: any mismatch returns HTTP 402 and the
provider is not called. On verification success, the gateway persists a
payment intent and verified payment and marks the quote nonce as used before
forwarding.

## Phase 3: provider execution and receipt

The gateway POSTs the original arguments as JSON to the selected service
version's `endpoint_url`, using the version's configured timeout. A 2xx
response is treated as successful execution. A non-2xx response becomes a
provider error; a timeout and other HTTP errors are classified separately.

For success, PaxRelay stores a receipt containing request and response hashes,
payment and LayerX references, route strategy and score, service/version,
execution status, timestamps, and latency. The receipt is signed locally by
default. For provider failure, the payment can remain verified while the
request is failed; this flow does not currently refund the payment.

## Replay and retry behavior

The gateway checks `(agent_id, idempotency_key)` and returns a replay response
for a previously delivered call. The current service does not replay the full
stored response body and only handles the delivered state in its intake path.
Although the domain has retryable execution states and configuration for
multiple provider attempts, the current invoke path creates one attempt and
does not execute provider failover. Do not rely on automatic retries.

Nonces are recorded as used after verification. The mock adapter also tracks
used nonces in memory; production replay protection must be durable and
concurrency-safe.

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
