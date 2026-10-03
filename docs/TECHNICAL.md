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
  manage tenant agents, providers, services, spend policies, approvals,
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

The web console is still a prototype and most views use sample data. The
simulator returns fabricated network results. The worker expires overdue policy
approvals, fans supported outbox events into durable delivery rows, and sends
HMAC-signed webhook requests with DNS pinning and bounded retries. Reconciliation
checks local payment facts and reads LayerX/Paxeer adapter evidence, but the
external settlement endpoint contract still needs validation with the network
operator. Provider health probes and rolling provider metrics are implemented;
the analytics materializer remains a placeholder. Analytics API routes provide
tenant-scoped spend and capability aggregates. Do not use mock output as evidence
of a real payment or settlement.
