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
authentication resolves these fields and resource/action scopes from the API
key. Control-plane lists, single-resource lookups, relationships, receipts,
and analytics enforce all three tenant values. Tool calls carry these columns
so related payments and receipts can be scoped through their tool call.

## Identity and access records

| Table | Purpose | Important fields |
| --- | --- | --- |
| `users` | Human identity record | Email, verification, display name, password hash, active state, last login |
| `organisations` | Tenant/account boundary | Name, unique slug, plan, active state |
| `memberships` | User-to-organisation role | User, organisation, role, inviter |
| `projects` | Tenant subdivision | Organisation/project scope, name, slug, active state |
| `api_keys` | Machine authentication credential | Prefix, SHA-256 hash, test/live type, control-plane and `gateway:invoke` scopes, expiry, active state, last use |
| `agents` | Automated caller identity | Tenant scope, name, slug, wallet, status, metadata |
| `wallets` | Wallet associated with an agent | Agent, address, primary flag, label |

The API-key creation route returns the raw key once; only its prefix and hash
are persisted. A CLI bootstraps the first organisation, project, and scoped
key; scoped keys can be inventoried and revoked through the API. Gateway keys
are project-scoped and may select active agents within that project. Human users,
organisations, and memberships exist in the
database model but do not yet have corresponding control-plane routes in this
checkout.

## Service and policy records

| Table | Purpose |
| --- | --- |
| `providers` | Provider identity, status, optional wallet and website |
| `services` | Provider service name, capability, supported protocol, price, endpoint base, delivery and health configuration |
| `service_versions` | Immutable invocation target with protocol, endpoint URL, pricing, delivery configuration, and optional HTTP or MCP schema/tool metadata |
| `provider_metrics` | Reputation, success, latency, availability, call count, failure streak, and health status |
| `analytics_spend_rollups` | Hourly/daily committed spend by organisation, project, environment, agent, capability, currency, and bucket |
| `analytics_refresh_state` | Last successful rollup refresh and coverage window for each worker environment |
| `policies` | Policy metadata and version/mode |
| `policy_rules` | Spending, capability, provider, quality, approval, and session rules |
| `policy_assignments` | Link between an agent and a policy |

Publishing a service through the current API creates a service, an immutable
version snapshot, and an initial metrics row. The initial metrics use perfect
success/reputation/availability values and zero latency. The health worker
updates availability and health state; provider indexing refreshes rolling
success, latency, and failure-streak metrics from execution attempts.

## Call, payment, and execution records

| Table | Purpose |
| --- | --- |
| `tool_calls` | One logical agent request, with tenant scope, capability, arguments, request hash, idempotency key, completed provider result for replay, and independent request/payment/execution states |
| `route_decisions` | Provider/service version selected for the call, strategy, score, breakdown, explanation, and attempt number |
| `quotes` | Immutable payment requirement: amount, recipient, chain, request hash, nonce, and expiry |
| `budget_reservations` | Per-agent amount held against daily/monthly policy budgets while a quote is valid; expired quotes stop counting, and verified payment consumes the reservation atomically |
| `payment_intents` | Intended payment associated with a quote and tool call |
| `payments` | Submitted/verified payment proof, LayerX references, and settlement timestamps |
| `execution_attempts` | Each provider forward attempt, status, HTTP code, timestamps, latency, and retryability |
| `execution_receipts` | Canonical receipt JSON, hashes, signature, signing key ID, and issue time |
| `settlement_records` | LayerX transaction/batch and L1 settlement/anchor details, local/external check times, retry count/lease, reconciliation status, and safe mismatch issue codes |

Provider indexing uses a composite index on execution-attempt service-version,
creation time, and ID so its rolling window queries can find recent attempts
without scanning unrelated execution history.

The analytics worker rebuilds only the configured recent windows in a single
transaction. Hourly rows default to 30 days and daily rows to 400 days. These
rollups are used by analytics queries for complete days after a recent refresh;
the API reads partial-day boundaries from payments directly. The
`analytics_refresh_state` row records the successful refresh time and coverage
window for each worker environment, allowing the API to fall back to source
queries when rollups are stale or unavailable.

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
| `approval_requests` | Tenant-scoped policy decision, bound to the original route, amount, recipient, and policy version |
| `webhook_endpoints` | Tenant URL, event subscriptions, secret digest and authenticated-encrypted secret, active state |
| `webhook_deliveries` | Per-event attempt count, lease, retry time, HTTP status, and terminal outcome |
| `audit_logs` | Tenant/environment-scoped actor/action/resource record with safe event metadata, peer IP, and request ID |
| `outbox_events` | Tenant-scoped transactional events, inserted with supported audited API changes and consumed into webhook delivery rows |

The worker fans supported events into durable webhook delivery rows, then sends
them with at-least-once semantics. A delivery row marked `delivered` records a
2xx response; it does not prove that the subscriber processed the event.

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
