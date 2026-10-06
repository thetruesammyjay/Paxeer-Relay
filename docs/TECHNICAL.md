# PaxRelay technical documentation

This page is the starting point for implementation details and local setup.
For a plain-language introduction, see the root [README](../README.md). For
the full product and technical specification, see
[PROJECT-STRUCTURE.md](../PROJECT-STRUCTURE.md). Feature descriptions in that
specification may describe intended behavior; this documentation identifies
which parts are present in the current checkout.

## Build and run

- [Local setup and deployment](deployment.md) — prerequisites, environment,
  database migration, API and web commands.
- [API reference](api-reference.md) — control-plane, gateway, and simulator
  routes, inputs, outputs, and current limitations.
- [Python SDK guide](../packages/sdk-python/README.md) — connect to the API and
  manage tenant agents, providers, service publication and routing, spend policies, approvals,
  analytics, receipt history, and transaction history from Python.
- [Architecture](architecture.md) — application roles, data flow, and trust
  boundaries.
- [Operations](operations.md) — health checks, worker status, payment failures,
  and incident notes.
- [Contributing](contributing.md) — local workflow and code boundaries.

## Payment and service behavior

- [402LXP flow](402lxp-flow.md) — quote, challenge, proof verification, provider
  execution, and receipt lifecycle.
- [Policy engine](policy-engine.md) — rule order, modes, and enforcement gaps.
- [Provider routing](provider-routing.md) — hard filters, scores, strategies,
  and failover status.
- [Paxeer and LayerX integration](protocol-integration.md) — adapter
  interfaces, assumed endpoints, and verification requirements.
- [MCP integration](mcp-integration.md) — current status and the intended
  provider/agent adapter boundary.
- [Execution receipts](execution-receipts.md) — receipt contents,
  canonicalization, signatures, and verification limits.

## Data and security

- [Data model](data-model.md) — tenant records, payment states, and schema
  changes.
- [Threat model](threat-model.md) — assets, current controls, high-risk gaps,
  and the minimum production gate.

## Local start commands

First install dependencies and start PostgreSQL from the repository root:

```powershell
pnpm install
uv sync --all-packages
docker compose up -d postgres redis
```

Then start each app in its own terminal:

```powershell
cd apps/api
uv run uvicorn app.main:app --reload
```

```powershell
cd apps/web
pnpm dev
```

The dashboard overview at `/dashboard`, `/admin`, and `/creator` reads live,
tenant-scoped production data. Before connecting a key, the browser requests
`GET /v1/context` and accepts only a key that the API confirms belongs to the
`production` environment. Keys for development, test, or staging are rejected.
The overview reads services, transactions, pending approvals, providers,
receipts, and 30-day spend independently. A missing scope or failed endpoint
affects its own section; the rest of the data can still load. These summaries
refresh every 30 seconds and show when they last updated. No overview metric is
filled with sample data.

The workspace requires `services:read`, `transactions:read`,
`approvals:read`, and `analytics:read` for its core metrics. Admin additionally
uses `providers:read`; creator also uses `receipts:read`. `/admin` is scoped to
the connected project, not the whole PaxRelay platform. `/creator` also reads
at project scope because the API does not yet expose per-creator identity or
ownership filters. Do not use these pages as a substitute for a user-session
and role authorization layer.

The `api-session` provider keeps the bearer key in browser memory, shares it
across dashboard pages, clears query data on disconnect or key change, and
does not write the key to browser storage. Production web builds require an
HTTPS API base URL. The sign-in page remains a preview; connecting a production
key is currently the dashboard's access mechanism, not a multi-user SSO
session. Use narrowly scoped project keys and keep this limitation in view for
any customer-facing deployment.

The agents, policies, providers, services, receipts, analytics, approvals,
transactions, and settlement pages also read API endpoints with their matching
scopes. Settings lists project keys with `api-keys:read` and creates or revokes
them with `api-keys:write`.
The agents page reads with `agents:read` and registers agents with
`agents:write`; a key with both scopes can perform both actions in one session.
It links an optional wallet address as agent metadata, not as a connected or
payment-capable wallet. A successful registration refreshes the directory and
offers the full agent ID for copying. The approvals page reads with
`approvals:read` and records decisions with `approvals:write`. Keys stay in
page memory and are not written to browser storage. The policy page reads
summaries with `policies:read`, creates policies and assigns them to agents
with `policies:write`, and loads full rules and assignments on demand. Approval
allows a request to continue to payment checks; it does not submit a payment.
The providers page reads with `providers:read` and registers provider records
with `providers:write`. It collects an optional HTTP(S) website and address;
production registrations require a payment wallet address. Provider website
links are rendered only for HTTP(S) URLs. Registration does not verify provider
ownership, and the directory does not show live health or performance.
The services page reads records with `services:read` and publishes services
with `services:write` for a provider UUID. The form stores USDX prices as exact
six-decimal atomic units, validates protocol and health-check settings, and
requires the user to copy the provider UUID from Providers. Use HTTPS for
staging and production; the gateway checks URLs and the production host
allowlist when forwarding. New services are not routable until a health probe
passes. The list shows the latest probe result, timestamp, and consecutive
failure count. Apply Alembic revision `0014_provider_health_fail_closed`
before rollout; it marks legacy services without a recorded probe as
unavailable until measured. A `services:write` key can pause or resume a
service; pausing prevents new routes while allowing already-issued, unexpired
quotes to finish when the provider remains active and health checks pass. The
status transition is audited and emitted as
`service.disabled` or `service.enabled`.
The receipts page lists up to 100 recent tenant-scoped summaries and displays
the signature and hash fields returned by the API. It does not verify receipt
signatures. Receipt payment amounts are kept as exact atomic-unit integers.
API-key secrets are returned only on creation and remain in page memory for
the one-time copy step; the inventory endpoint returns key metadata only.
The simulator
returns fabricated network results. The worker expires overdue policy
approvals, marks stale paid executions unknown without replaying providers,
fans supported outbox events into durable delivery rows, and sends HMAC-signed
webhook requests with DNS pinning and bounded retries. Reconciliation
checks local payment facts and reads LayerX/Paxeer adapter evidence, but the
external settlement endpoint contract still needs validation with the network
operator. Provider health probes and rolling provider metrics are implemented.
The worker maintains recent hourly and daily spend rollups per tenant, agent,
and capability. Analytics API routes use fresh daily rollups for complete days
and query payment records directly for partial days or when rollups are missing
or stale. Do not use mock output as evidence of a real payment or settlement.
