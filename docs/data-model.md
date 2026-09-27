# Data model

The Python domain models define application-level records. The SQLAlchemy
models in `packages/db` persist those records in PostgreSQL. Alembic migration
`0001_initial.py` is the current schema baseline. Update domain types, database
models, repositories, migrations, and API schemas together when changing a
persisted field.

## Tenant and environment scope

The primary control-plane boundary is:

```text
Organisation
  └── Project
        ├── API keys
        ├── Agents and wallets
        ├── Providers and services
        ├── Policies and assignments
        └── Tool calls and operational evidence
```

Tenant-owned database rows carry `organisation_id`, `project_id`, and usually
`environment` (`development`, `staging`, or `production`). Control-plane
authentication resolves these fields from the API key. List queries should
filter by both organisation and project. Tool calls carry these columns so
related payments and receipts can be scoped through their tool call.

Some current single-resource routes check organisation ownership without
checking project ownership. Treat project isolation as a security requirement
and audit every `get` and relationship lookup before enabling multiple projects
per organisation.

## Identity and access records

| Table | Purpose | Important fields |
| --- | --- | --- |
| `users` | Human identity record | Email, verification, display name, password hash, active state, last login |
| `organisations` | Tenant/account boundary | Name, unique slug, plan, active state |
| `memberships` | User-to-organisation role | User, organisation, role, inviter |
| `projects` | Tenant subdivision | Organisation/project scope, name, slug, active state |
| `api_keys` | Machine authentication credential | Prefix, SHA-256 hash, test/live type, scopes, expiry, active state, last use |
| `agents` | Automated caller identity | Tenant scope, name, slug, wallet, status, metadata |
| `wallets` | Wallet associated with an agent | Agent, address, primary flag, label |

The API-key creation route returns the raw key once; only its prefix and hash
are persisted. Human users, organisations, and memberships exist in the
database model but do not yet have corresponding control-plane routes in this
checkout.

## Service and policy records

| Table | Purpose |
| --- | --- |
| `providers` | Provider identity, status, optional wallet and website |
| `services` | Provider service name, capability, supported protocol, price, endpoint base, delivery and health configuration |
| `service_versions` | Versioned invocation target, endpoint URL, pricing, delivery configuration, and optional schema |
| `provider_metrics` | Reputation, success, latency, availability, call count, failure streak, and health status |
| `policies` | Policy metadata and version/mode |
| `policy_rules` | Spending, capability, provider, quality, approval, and session rules |
| `policy_assignments` | Link between an agent and a policy |

Publishing a service through the current API creates a service, an immutable
version snapshot, and an initial metrics row. The initial metrics use perfect
success/reputation/availability values and zero latency until a real health
measurement exists. The worker that should refresh those values is currently
a placeholder.

## Call, payment, and execution records

| Table | Purpose |
| --- | --- |
| `tool_calls` | One logical agent request, with tenant scope, capability, arguments, request hash, idempotency key, and independent request/payment/execution states |
| `route_decisions` | Provider/service version selected for the call, strategy, score, breakdown, explanation, and attempt number |
| `quotes` | Immutable payment requirement: amount, recipient, chain, request hash, nonce, and expiry |
| `payment_intents` | Intended payment associated with a quote and tool call |
| `payments` | Submitted/verified payment proof, LayerX references, and settlement timestamps |
| `execution_attempts` | Each provider forward attempt, status, HTTP code, timestamps, latency, and retryability |
| `execution_receipts` | Canonical receipt JSON, hashes, signature, signing key ID, and issue time |
| `settlement_records` | LayerX transaction/batch and eventual L1 anchoring details |

The domain keeps the state machines separate:

| Dimension | Representative values |
| --- | --- |
| Request | `created`, `policy_pending`, `approval_pending`, `payment_required`, `payment_verified`, `executing`, `delivered`, `failed`, `expired`, `cancelled` |
| Payment | `unpaid`, `quoted`, `submitted`, `verified`, `settled_layerx`, `anchored_l1`, `refunded`, `disputed`, `failed`, `expired` |
| Execution | `not_started`, `reserved`, `running`, `succeeded`, `provider_error`, `timeout`, `cancelled`, `unknown` |

Do not infer service success from payment success or L1 finality from a
LayerX-verified record. A call can be paid and still fail at the provider.

## Operations and event records

| Table | Purpose |
| --- | --- |
| `approval_requests` | Durable human decision request model; current gateway policy response does not yet create a complete approval workflow |
| `webhook_endpoints` | Tenant URL, event subscriptions, hashed secret, active state |
| `webhook_deliveries` | Per-event delivery attempt and outcome |
| `audit_logs` | Actor/action/resource audit record |
| `outbox_events` | Transactional event queue for background publication |

The schema has webhook delivery and outbox tables, but the worker handlers that
should deliver events are stubs. Their existence in PostgreSQL does not mean
the event pipeline is operational.

## Monetary and identifier rules

- Store money as integer atomic units. Do not use binary floating point for
  amounts.
- The current domain currency is USDX with six decimal places.
- Use UUIDs for API-visible entities. SQLAlchemy models store UUID strings in
  PostgreSQL UUID columns.
- Capability identifiers are lowercase dot-separated strings, optionally
  ending in `.*` for a wildcard policy pattern.
- EVM addresses must be 20-byte hex strings with a `0x` prefix. Domain values
  normalise them to lowercase.
- Request and response bodies are hashed. The current gateway computes a
  sorted-key compact JSON encoding for arguments, then SHA-256 hashes those
  bytes.

## Schema change workflow

1. Change the domain model and its validation first.
2. Change the SQLAlchemy model and repository mapping.
3. Create an Alembic migration under
   `packages/db/src/paxrelay_db/migrations/versions/`.
4. Update API request/response schemas and documentation.
5. Check tenant filtering, unique keys, state transitions, and rollback
   behavior.
6. Apply the migration to a disposable development database before release.

The current database package provides the initial schema. There is no seed-data
script in the current checkout, so local UI sample records should not be
mistaken for seeded database rows.
