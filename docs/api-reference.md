# PaxRelay API reference

This page describes the HTTP routes currently registered by `apps/api` and
`apps/gateway`. The control-plane API manages tenant resources. The gateway
handles paid calls. They are separate FastAPI applications.

## Base URLs and authentication

Local defaults:

| Service | Base URL | Interactive API docs |
| --- | --- | --- |
| Control-plane API | `http://localhost:8000` | `/docs` |
| Paid-call gateway | `http://localhost:8080` | No OpenAPI route is currently enabled |
| Simulator | `http://localhost:8090` | `/docs` |

Control-plane routes under `/v1` require `Authorization: Bearer <api-key>`.
Keys are stored as SHA-256 hashes and looked up by their `pk_` prefix. The
authenticated key supplies the organisation, project, and environment used for
tenant scoping. `/health` is public and returns `{"status":"ok"}`.

The gateway currently authenticates an agent through `X-Agent-Id: <uuid>` and
checks that the agent is active. This is a development identity mechanism, not
production authentication. See [Threat model](threat-model.md).

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
errors return HTTP 500 with `internal_error`; stack details are not returned.

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

### API keys

| Method and path | Purpose |
| --- | --- |
| `POST /api-keys` | Create a `test` or `live` API key. |

The raw key is returned once in `raw_key`; store it securely. The API persists
only the SHA-256 hash and prefix. Keys currently expire after one year. The
route is itself protected by an existing API key, so first-key bootstrapping
is not provided by this checkout. Key `scopes` are stored but are not enforced
by the current authentication dependency.

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

### Webhooks and batch operations

| Method and path | Purpose |
| --- | --- |
| `POST /webhooks` | Register an HTTP or HTTPS destination, event types, and a secret. |
| `GET /webhooks` | List the current project's endpoints. |
| `GET /webhooks/{webhook_id}` | Get one endpoint. |
| `PATCH /webhooks/{webhook_id}` | Update URL, event types, active state, or description. |
| `DELETE /webhooks/{webhook_id}` | Delete an endpoint; returns HTTP 204. |
| `POST /batch/agents` | Create 1–100 agents independently; returns HTTP 207 with per-item results. |
| `POST /batch/providers` | Create 1–100 providers independently; returns HTTP 207 with per-item results. |

Webhook event types are checked against the domain event enum. The supplied
secret is hashed at creation and is not returned. A delivery worker is not yet
implemented, so registering an endpoint does not currently guarantee a
delivery.

## Paid-call gateway routes

### `POST /v1/invoke`

Required header: `X-Agent-Id: <active-agent-uuid>`.

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
approval is currently returned as 202 with a decision and explanation; a
complete persisted approval workflow is not exposed here.

### `POST /v1/invoke/{tool_call_id}`

Required header: `X-Agent-Id: <active-agent-uuid>`. Submit the payment proof as
a JSON string:

```json
{"proof":"{\"quote_id\":\"...\",\"request_hash\":\"...\",\"amount_atomic\":1000000,\"recipient\":\"0x...\",\"nonce\":\"...\",\"chain_id\":125,\"payment_scheme\":\"402LXP\"}"}
```

A verified payment is forwarded to the selected service with the original
arguments as a JSON POST body. A 2xx provider response returns `result` and a
signed `receipt`. Proof failures return HTTP 402; provider failures return
HTTP 502. Payment verification and service delivery remain separate states.

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
