# PaxRelay architecture

PaxRelay is a set of applications with separate responsibilities. The web
console configures and observes a tenant. The control-plane API manages
resources. The gateway coordinates paid calls. PostgreSQL stores records. A
worker handles approval expiry, outbox fan-out, and webhook delivery. A simulator supplies fake
Paxeer, LayerX, registry, and 402LXP responses for development.

## System context

```text
Operator ───────► Next.js console ───────► Control-plane API ─────► PostgreSQL
                                             ▲                           ▲
                                             │                           │
Agent ──────────► Paid-call gateway ─────────┼───────────────────────────┘
                         │                   │
                         ├──► Provider       │
                         └──► Paxeer adapter │
                                  │          │
                                  ├── LayerX │
                                  ├── Paxeer │
                                  └── Registry

Worker ─────────────► PostgreSQL / Redis / Paxeer adapters
Simulator ──────────► fake 402LXP, LayerX, and registry endpoints
```

The diagram shows intended system boundaries. In the current checkout, the web
pages are largely static prototypes, and the simulator returns fabricated
results. Approval expiry and webhook delivery are active worker jobs; payment
reconciliation, provider health, indexing, and analytics remain placeholders.
The gateway's paid-call orchestration is the most complete request path, but its
default payment adapter is mock mode.

## Applications

### `apps/web`

Next.js App Router dashboard on port 3000. The root route shows a sign-in
presentation. Dashboard pages cover agents, policies, providers, services,
approvals, transactions, receipts, analytics, and settings. Most pages use
sample information. `lib/api-client.ts` provides an HTTP boundary and
`hooks/use-agents.ts` demonstrates a query hook, but those are not connected to
all screens. The browser does not connect directly to PostgreSQL.

### `apps/api`

FastAPI control plane on port 8000. It provides tenant-scoped CRUD and listing
routes for agents, providers, services, policies, API keys, webhooks,
transactions, receipts, and analytics. It uses SQLAlchemy async sessions and
the shared `packages/db` repository layer. The API does not own paid-call
forwarding.

### `apps/gateway`

FastAPI paid-call gateway on port 8080. `/v1/invoke` creates a tool-call record,
selects a service, evaluates the agent's policy, and returns a 402LXP
requirement. `/v1/invoke/{tool_call_id}` verifies a proof, records the verified
payment and atomically consumes its quote nonce, commits that state before
provider dispatch, forwards the JSON arguments to the stored service version,
and issues a receipt after a successful provider response.

The gateway is composed from domain, database, policy, routing, receipt, and
Paxeer adapter packages. Paid-call routes require a tenant API key with the
`gateway:invoke` scope and verify that the selected active agent belongs to the
key's organisation, project, and environment. Production startup rejects mock
payments and local signing defaults. The official adapter's HTTP request and
verification behavior still needs validation against authoritative Paxeer and
LayerX services before it can process real funds.

### `apps/worker`

An async process that starts periodic loops for approval expiration,
reconciliation, provider indexing, analytics, outbox fan-out, and health
checks. Approval expiration marks overdue requests and pending tool calls as
expired and writes audit and domain events transactionally. Outbox fan-out
creates durable delivery rows for active webhook subscriptions. A separate
delivery loop sends HMAC-signed requests with DNS-pinned destinations, bounded
timeouts and bodies, and retry leases. Delivery is at least once, so consumers
must deduplicate by delivery ID. Reconciliation, indexing, analytics, and
health `tick()` methods remain placeholders.

### `apps/simulator`

FastAPI development service on port 8090. It simulates payment requirements,
proof acceptance, settlement records, L1 batch checks, service publication,
and provider history. The service registry is in memory and resets when the
process restarts. It is not a production payment verifier.

### `apps/docs`

Separate Next.js/Fumadocs application on port 3001. It has initial installation
and quickstart content. This site is distinct from the Markdown technical
references in the repository's `docs/` directory.

## Request and data ownership

- **Control-plane API** owns tenant configuration and query endpoints.
- **Gateway** owns per-call orchestration and writes linked tool-call,
  routing, quote, payment, attempt, and receipt records.
- **PostgreSQL** is the durable record store for the API and gateway.
- **Redis** coordinates background work and enforces shared API-key rate limits
  for both the control plane and paid-call gateway in staging and production.
- **Gateway readiness** checks PostgreSQL and Redis when gateway rate limiting
  is enabled; it does not claim external payment or provider health.
- **Paxeer adapter** isolates wallet, 402LXP, LayerX, registry, and settlement
  access behind Python protocols.
- **Provider** receives a JSON POST only after a payment proof passes local
  checks and adapter verification.

## Tenant boundaries

Control-plane bearer keys resolve an organisation, project, environment, and
scope grants. Route guards enforce the required grant. Resource reads,
relationship lookups, lists, receipts, and analytics check all three tenant
values. Continue applying this boundary to every new endpoint. Gateway API keys
now establish the tenant; `X-Agent-Id` selects an active agent within it.

Webhook endpoint secrets have a SHA-256 digest for identification and an
AES-GCM encrypted copy for the delivery worker. Production uses a dedicated
`WEBHOOK_ENCRYPTION_KEY`; the key must remain available while endpoint secrets
are stored. Existing hash-only endpoints are disabled by database migration
`0002` because their original secrets cannot be recovered.

The gateway checks that a completion request's call belongs to the exact
authenticated agent before it reads the quote or accepts payment proof.

## Failure boundaries

Payment, execution, receipt, and L1 settlement are separate states. A payment
can be verified while provider execution fails. A successful provider response
does not establish that its content is correct. A local database transaction
does not make an external payment or provider call atomic; recovery and
reconciliation are required before production operation.

## Code boundaries

```text
HTTP app (FastAPI / Next.js)
        │
        ▼
application services (API routes / gateway invoke service)
        │
        ├──► domain models and ports
        ├──► database repositories
        └──► adapters (Paxeer / LayerX / HTTP provider)
```

Keep FastAPI, SQLAlchemy, and HTTP client details out of
`packages/domain`. Keep protocol-specific code inside `packages/paxeer-adapter`.
Use repository interfaces for persistence and keep policy evaluation and
provider scoring deterministic and side-effect free.
