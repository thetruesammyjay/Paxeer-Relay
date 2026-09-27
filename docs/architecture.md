# PaxRelay architecture

PaxRelay is a set of applications with separate responsibilities. The web
console configures and observes a tenant. The control-plane API manages
resources. The gateway coordinates paid calls. PostgreSQL stores records. A
worker is intended to process background work. A simulator supplies fake
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
pages are largely static prototypes, worker jobs are stubs, and the simulator
returns fabricated results. The gateway's paid-call orchestration is the most
complete request path, but its default payment adapter is mock mode.

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
payment, forwards the JSON arguments to the stored service version, and issues
a receipt after a successful provider response.

The gateway is composed from domain, database, policy, routing, receipt, and
Paxeer adapter packages. `USE_MOCK_ADAPTER` defaults to true in code. The
official adapter uses HTTP request shapes that must be checked against the
deployed Paxeer and LayerX services before production use.

### `apps/worker`

An async process that starts periodic loops for reconciliation, provider
indexing, analytics, outbox delivery, and health checks. The loop framework and
configuration exist, but the job `tick()` methods are placeholders. Do not
expect it to reconcile payments or deliver webhooks yet.

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
- **Redis** is reserved for queues, pub/sub, and coordination; the local compose
  file starts it, but the current API and gateway do not depend on it for the
  main paid-call request.
- **Paxeer adapter** isolates wallet, 402LXP, LayerX, registry, and settlement
  access behind Python protocols.
- **Provider** receives a JSON POST only after a payment proof passes local
  checks and adapter verification.

## Tenant boundaries

Control-plane bearer keys resolve an organisation and project. List queries
generally filter by both. Receipt and analytics queries join back through the
tenant-scoped tool call. Review individual resource lookups before exposing
them to multiple tenants: some current `get` routes check organisation but do
not consistently check project.

Gateway agent identity is currently the caller-supplied `X-Agent-Id` header.
The gateway does not validate that an agent belongs to a separately
authenticated tenant. Treat this as a local development boundary only.

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
