# PaxRelay API reference

This page describes the HTTP routes currently registered by `apps/api` and
`apps/gateway`. The control-plane API manages tenant resources. The gateway
handles paid calls. They are separate FastAPI applications.

## Base URLs and authentication

Local defaults:

| Service | Base URL | Interactive API docs |
| --- | --- | --- |
| Control-plane API | `http://localhost:8000` | `/docs` |
| Paid-call gateway | `http://localhost:8080` | No OpenAPI route is currently enabled; `/health` is liveness and `/ready` checks dependencies |
| Simulator | `http://localhost:8090` | `/docs` |

Control-plane routes under `/v1` require `Authorization: Bearer <api-key>`.
Keys are stored as SHA-256 hashes and looked up by their `pk_` prefix. The
authenticated key supplies the organisation, project, and environment used for
tenant scoping. Each route also requires its specific API-key scope. `/health`
is a public liveness route; `/ready` checks PostgreSQL and checks Redis when
API rate limiting is enabled. Every response includes an `X-Request-ID` header
for support and log correlation.

Staging and production enable a Redis-backed fixed-window limit of 300 requests
per API key per 60 seconds by default. Configure the limit with
`API_RATE_LIMIT_MAX_REQUESTS` and `API_RATE_LIMIT_WINDOW_SECONDS`. Development
rate limiting is off unless `API_RATE_LIMIT_ENABLED=true` is set. A 429 response
includes `Retry-After` and rate-limit headers. If Redis becomes unavailable
while limiting is enabled, authenticated API requests fail closed with HTTP 503.
Use an edge proxy or gateway to rate-limit invalid or unauthenticated requests;
this API limiter starts after API-key verification.

The gateway also limits authenticated API keys in staging and production,
defaulting to 120 requests per 60 seconds. Configure it with
`GATEWAY_RATE_LIMIT_MAX_REQUESTS` and
`GATEWAY_RATE_LIMIT_WINDOW_SECONDS`. It fails closed with HTTP 503 if Redis is
unavailable. Invalid or unauthenticated requests still need an edge limit.

Write request bodies are limited to 1 MiB by default. Set
`API_MAX_REQUEST_BYTES` to adjust the cap; its allowed range is 1 KiB to 10 MiB.
Oversized requests return HTTP 413 with the standard error envelope.
The gateway separately limits invocation bodies to `GATEWAY_MAX_REQUEST_BYTES`
(1 MiB by default) and provider response bodies to
`GATEWAY_MAX_RESPONSE_BYTES` (10 MiB by default).

Gateway invocation routes require a bearer API key with the `gateway:invoke`
scope and `X-Agent-Id: <uuid>`. The key's active organisation, project, and
environment must match the selected active agent. The header selects an agent
within that authenticated tenant; it does not authenticate the caller.

## Common formats

Monetary values use atomic integer units. USDX has six decimals, so
`1000000` means `1 USDX`.

```json
{
  "amount_atomic": 1000000,
  "currency": "USDX",
  "decimals": 6
}
```

Control-plane errors use a stable envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "The requested resource was not found."
  }
}
```

Request validation errors return HTTP 422 with `validation_error`. Unexpected
errors return HTTP 500 with `internal_error`; stack details are logged with the
request ID and are not returned to callers. The same error envelope is used for
HTTP routing errors and database constraint conflicts.

### Scopes

Scopes are resource/action pairs serialized as alternating colon-separated
values. For example, `agents:read:agents:write:api-keys:read` grants read and
write access to agents and read access to API-key metadata. Supported resources
are `agents`, `providers`, `services`, `policies`, `approvals`, `api-keys`, `receipts`,
`transactions`, `settlements`, `analytics`, `audit-logs`, `webhooks`, and `batch`; actions are
`read` and `write`. The gateway uses the additional `gateway:invoke` grant. An
API key can only create another key with a subset of its own grants. An empty
scope set grants no access.

| Resource | Read routes | Write routes |
| --- | --- | --- |
| `agents` | List/get agents and read wallets | Create agents |
| `providers` | List/get providers | Create providers |
| `services` | List/get services | Publish services |
| `policies` | List/get policies | Create policies and assign them |
| `approvals` | List approval requests | Approve or reject pending requests |
| `api-keys` | List key metadata | Create and revoke keys |
| `gateway` | none | Invoke paid services and submit payment proof |
| `receipts` | List receipts | — |
| `transactions` | List transactions | — |
| `settlements` | Review tenant-scoped reconciliation records | — |
| `analytics` | Read spend and capability summaries | — |
| `audit-logs` | Read recent tenant audit records | — |
| `webhooks` | List/get endpoints | Create/update/delete endpoints |
| `batch` | — | Bulk agent/provider creation (also requires that resource's `write` grant) |

## Control-plane routes

All paths in this section are prefixed with `/v1`. Unless specified otherwise,
successful creates return HTTP 201 and list routes return newest records first.

### Agents

| Method and path | Purpose |
| --- | --- |
| `POST /agents` | Create an agent in the authenticated project. |
| `GET /agents` | List agents; supports `status`, `search`, `limit` (1–100, default 50), and `offset`. |
| `GET /agents/{agent_id}` | Get one agent. |
| `GET /agents/{agent_id}/wallet` | Get the agent's primary wallet record. |

Create body:

```json
{
  "name": "Research Runner",
  "slug": "research-runner",
  "wallet_address": "0x0000000000000000000000000000000000000001",
  "description": "Collects market data"
}
```

`name` is limited to 128 characters. `slug` must start with a lowercase letter
or digit and may contain lowercase letters, digits, `_`, and `-`.

### Providers and services

| Method and path | Purpose |
| --- | --- |
| `POST /providers` | Register a provider in the current project. |
| `GET /providers` | List providers; supports `status`, `search`, `limit` (1–100, default 100), and `offset`. |
| `GET /providers/{provider_id}` | Get one provider. |
| `POST /services/providers/{provider_id}` | Publish a service for a provider and create its initial immutable version and metrics. |
| `GET /services` | List services in the current project. |
| `GET /services/{service_id}` | Get one service. |

Service create bodies contain `name`, `slug`, `capability`, `protocols`,
`price_per_call`, `base_url`, `endpoint_url`, `version`, and an optional
`description`. Capabilities use lowercase dot-separated names such as
`research.web-search`; a trailing `.*` wildcard is accepted by validation.
The gateway sends requests to `endpoint_url`. In staging and production, this
URL must use HTTPS and resolve only to public IP addresses in staging and
production. Production also requires the hostname to match the gateway's exact
allowlist. The gateway checks the URL before issuing a payment challenge,
checks it again before forwarding, pins the connection to the checked IP, and
does not follow redirects. In development and test environments, private
addresses and HTTP are allowed for local simulators.

Production providers must have a valid payment wallet address before their
services can be used for paid calls. The gateway also requires one whenever the
live payment adapter is enabled. Mock-only development can use the demo
destination.

### Policies

| Method and path | Purpose |
| --- | --- |
| `POST /policies` | Create a policy. |
| `GET /policies` | List policies; supports `mode`, `is_active`, `search`, `limit` (1–100, default 50), and `offset`. |
| `GET /policies/{policy_id}` | Get one policy. |
| `POST /policies/{policy_id}/assign` | Assign a policy to an agent using `{"agent_id":"<uuid>"}`. |

The create body accepts `mode`, `maximum_per_call`, `daily_budget`,
`monthly_budget`, `allowed_capabilities`, `allowed_providers`,
`blocked_providers`, and `approval_threshold`. Allowed modes are `observe`,
`warn`, and `enforce`. The route returns policy metadata, not the full rule
configuration.

### Human approvals

| Method and path | Purpose |
| --- | --- |
| `GET /approvals` | List tenant approval requests; supports `pending`, `approved`, `rejected`, `expired`, `consumed`, or `invalidated` status filters. |
| `GET /approvals/{approval_id}` | Read one tenant approval request by ID. |
| `POST /approvals/{approval_id}/decision` | Approve or reject a pending request. |

The decision body is `{"decision":"approved"}` or
`{"decision":"rejected","reason":"..."}`. A decision is recorded once;
repeating the same decision is safe, while attempting the opposite decision
returns HTTP 409. The queue expires overdue pending or approved requests after
`POLICY_APPROVAL_TTL_SECONDS` (900 seconds by default). A worker scans every
30 seconds, updates expired request and tool-call states, and writes an audit
entry in the same database transaction. The request records the
provider, immutable service version, amount, payment recipient, and policy
version that the reviewer approved. After approval, the agent must repeat the
original gateway `POST /v1/invoke` request with the same idempotency key and
same payload. The gateway rechecks the active policy and current budget, then
returns the payment challenge only if the approved snapshot still matches.
The current API records the approving API-key ID; it does not yet authenticate
or attribute decisions to an individual dashboard user.
Approval rows expose the provider and service-version IDs, amount, recipient,
request hash, policy version, expiry, and policy explanation. They do not expose
the invocation arguments or submitted payment proof.

### API keys

| Method and path | Purpose |
| --- | --- |
| `POST /api-keys` | Create a scoped `test` or `live` API key. |
| `GET /api-keys` | List key metadata; raw key values and hashes are never returned. |
| `DELETE /api-keys/{api_key_id}` | Revoke a key immediately; returns HTTP 204. |

The raw key is returned once in `raw_key`; store it securely. The API persists
only the SHA-256 hash and prefix. Keys expire after 90 days by default and can
be configured for up to 365 days. `test` keys belong to development/staging
projects and `live` keys belong to production projects. The key-creation route
requires `api-keys:write`, and every requested grant must already be held by
the calling key. `last_used_at` is refreshed at most once per minute to avoid
serializing concurrent requests on the same key row. Use the one-time bootstrap
command after applying migrations:

```powershell
cd apps/api
uv run python -m paxrelay_api.bootstrap `
  --organisation-name "Example Bank" `
  --organisation-slug example-bank `
  --project-name "Production" `
  --project-slug production `
  --environment production
```

The command prints a one-time key with all currently defined API scopes. Store
it in a secret manager, then create narrower operational keys and revoke the
bootstrap key when it is no longer needed. The command does not run migrations.
New scopes are never added to existing keys automatically. If an older
administrator key predates a resource such as `audit-logs`, provision a fresh
administrator key with the bootstrap command, rotate its credentials into
narrower keys, and revoke the older key.

Example: create a read-only reporting key using a key that already holds both
requested grants:

```json
{
  "name": "reporting",
  "key_type": "test",
  "scopes": "analytics:read:transactions:read"
}
```

Create a separate gateway key with only `gateway:invoke`, then send it as the
bearer credential on both paid-call routes. Its selected agent must belong to
the same organisation, project, and environment as the key. For a development
project, the key request is:

```json
{
  "name": "agent-runtime",
  "key_type": "test",
  "scopes": "gateway:invoke"
}
```

### Transactions, receipts, and analytics

| Method and path | Purpose and filters |
| --- | --- |
| `GET /transactions` | Filter by `agent_id`, `request_state`, `payment_state`, `created_after`, and `created_before`; `limit` defaults to 50 and is capped at 100. |
| `GET /receipts` | Filter by `agent_id` or `tool_call_id`; `limit` defaults to 50 and is capped at 100. |
| `GET /analytics/spend` | One spend aggregate for `period=daily` or `period=monthly` and an optional `start_date` / `end_date` range. |
| `GET /analytics/capabilities` | Spend grouped by capability with optional dates and `limit` (1–100, default 20). |

Analytics defaults to the previous 30 days. `start_date` must precede
`end_date`. Spend counts payment states `verified`, `settled_layerx`, and
`anchored_l1`; it does not mean every counted payment has an L1 anchor. The
current `period` value is echoed in the response; the endpoint does not return
a separate row for each day or month.

### Settlement review

`GET /settlements/reconciliation` requires `settlements:read` and returns
tenant-scoped records. It defaults to `status=mismatch`; request
`status=awaiting_external` to see payments that passed the local consistency
check or need an external retry. Other statuses are `layerx_confirmed` and
`reconciled`; `anchored` remains accepted for older records. Pages use `limit`
(1–100, default 50) and the `before_created_at` / `before_id` cursor pair.

The worker first compares each payment with its local intent, quote, and tool
call. It checks the request hash, agent, amount, currency, recipient, scheme,
chain, and settlement layer. It then reads the transaction by its stored
LayerX hash and compares the transaction hash, amount, recipient, and quote ID.
A matching LayerX transaction is marked
`layerx_confirmed`. A record becomes `reconciled` only when the configured
settlement adapter also confirms the settlement ID, batch, L1 commitment,
transaction membership, block, and L1 transaction hash. Missing evidence and
upstream errors remain retryable; explicit contradictions become `mismatch`
and emit `settlement.mismatch` to subscribed webhooks. Mismatch details contain
issue codes and, for safe scalar comparisons, truncated expected/actual values.
They never include the raw payment proof.

The response includes `attempt_count`, `next_attempt_at`, `last_checked_at`, and
a safe `last_error` code for operations. Payment state is never advanced by
this read-only worker. Production adapter configuration uses `LAYERX_API_URL`
and `PAXEER_SETTLEMENT_API_URL`. The worker checks the claimed L1 transaction
through JSON-RPC and requires a configured contract address, commitment event
topic, and confirmation depth. Confirm these values, the LayerX transaction
and batch endpoints, and the Paxeer settlement endpoint with the network
operator before using external results for financial operations.

### Audit logs

`GET /audit-logs` returns recent successful control-plane changes for the
authenticated organisation, project, and environment. It accepts optional
`event_type`, `resource_type`, and `resource_id` filters plus bounded
`limit`/`offset` pagination. Entries identify the API key that made the change
and include the request ID for log correlation. Event details omit raw keys,
webhook secrets, and request bodies.

### Webhooks and batch operations

| Method and path | Purpose |
| --- | --- |
| `POST /webhooks` | Register an HTTP/HTTPS destination, event types, and a secret. Staging and production require HTTPS. |
| `GET /webhooks` | List the current project's endpoints. |
| `GET /webhooks/{webhook_id}` | Get one endpoint. |
| `PATCH /webhooks/{webhook_id}` | Update URL, event types, shared secret, active state, or description. |
| `DELETE /webhooks/{webhook_id}` | Delete an endpoint; returns HTTP 204. |
| `GET /webhooks/{webhook_id}/deliveries` | List paginated delivery metadata; supports a status filter and cursor. |
| `POST /webhooks/{webhook_id}/deliveries/{delivery_id}/retry` | Queue one failed or cancelled delivery again; returns HTTP 202. |
| `POST /batch/agents` | Create 1–100 agents independently; returns HTTP 207 with per-item results. |
| `POST /batch/providers` | Create 1–100 providers independently; returns HTTP 207 with per-item results. |

Webhook event types are checked against the domain event enum. The supplied
secret must be at least 32 characters. The API stores its SHA-256 digest and an
authenticated-encrypted copy; no API response reveals the secret.
`secret_configured` reports whether an endpoint has a recoverable encrypted
secret. Send a new `secret` in a PATCH to rotate it. Audited control-plane
changes with public event types and approval expiration are stored in the
transactional outbox and fanned into durable delivery rows. Currently emitted
types are `agent.created`, `provider.created`, `policy.created`,
`service.published`, `approval.approved`, `approval.rejected`, and
`approval.expired`. The worker sends each event with
`X-PaxRelay-Signature: sha256=<hex>`, an HMAC-SHA256 of
`<unix-timestamp>.<delivery-id>.<event-type>.<raw-request-body>`. It includes
timestamp, event type, event ID, and delivery ID headers. Receivers should use constant-time signature
comparison, reject old timestamps, and deduplicate by delivery ID. Delivery is
at least once. The worker retries timeouts, network failures, HTTP 408, 425,
429, and 5xx responses up to the configured maximum; it does not follow
redirects. Staging and production require HTTPS and public DNS results, which
are pinned for the connection. Migration `0002` disables existing endpoints
whose original secret cannot be recovered from its old digest.

Delivery history returns the event type, state, attempt count, HTTP status,
safe error code, and retry/delivery timestamps. It does not return the event
payload or signing secret. Use `status` to filter and `limit` to set a page size
from 1 to 100 (default 50). When a page has more results, pass its
`next_cursor_created_at` and `next_cursor_id` values as `before_created_at` and
`before_id` to fetch the next page. A retry is available only for `failed` or
`cancelled` rows on an active endpoint with a configured secret. It resets the
attempt count for a new bounded retry cycle, records an audit entry, and queues
work for the worker; it does not send the request inside the API call.

## Paid-call gateway routes

### `POST /v1/invoke`

Required headers: `Authorization: Bearer <api-key>` with the `gateway:invoke`
scope, and `X-Agent-Id: <active-agent-uuid>` for an active agent in the key's
organisation, project, and environment.

```json
{
  "capability": "research.web-search",
  "idempotency_key": "search-2026-09-26-001",
  "arguments": {"query": "Paxeer Network"},
  "constraints": {"maximum_latency_ms": 1500}
}
```

On success the gateway first returns HTTP 402 with a `payment_requirement`
and `tool_call_id`. A missing eligible service returns 503. A missing active
policy or an enforced policy denial returns 403. A policy result that requires
approval returns HTTP 202 with an `approval_id`; a reviewer decides through
the control-plane approval routes above.
Repeating the same idempotency key and request returns its current quote or
state. After successful delivery, it returns the saved `result` and signed
`receipt` with `replayed: true`, without calling the provider again. Repeating
the completion request for a delivered call returns the same saved result.
Reusing the key with different request data returns 409; an expired quote
returns 410 and requires a new key. Calls completed before migration `0010`
have no saved provider result and return `completed_result_unavailable` on
replay.

### `POST /v1/invoke/{tool_call_id}`

Required headers: the same bearer key and `X-Agent-Id` used to create the call.
The tool call must belong to that exact agent. Submit the payment proof as a
JSON string:

```json
{"proof":"{\"quote_id\":\"...\",\"request_hash\":\"...\",\"amount_atomic\":1000000,\"recipient\":\"0x...\",\"nonce\":\"...\",\"chain_id\":125,\"payment_scheme\":\"402LXP\"}"}
```

A verified payment is forwarded to the selected service with the original
arguments as a JSON POST body. A 2xx provider response returns `result` and a
signed `receipt`. Proof failures return HTTP 402; reusing an already consumed
quote returns HTTP 409; provider failures return HTTP 502. Payment verification
and service delivery remain separate states.

## Simulator routes

The development simulator exposes:

- `POST /lxp402/payment-requirement`
- `POST /lxp402/verify`
- `GET /layerx/settlement/{settlement_id}`
- `GET /layerx/batch/{batch_id}`
- `POST /layerx/batch/{batch_id}/verify-l1`
- `POST /paxeer/registry/publish`
- `GET /paxeer/registry/services`
- `GET /paxeer/registry/provider/{provider_id}/history`
- `GET /health`

Simulator routes return fabricated data and are for local development only.
