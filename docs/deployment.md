# Local setup and deployment

This guide covers the supported local development shape and outlines what a
production deployment still needs. PaxRelay is pre-alpha; the current
configuration and adapters are not a production-ready payment service.

## Requirements

- Python 3.12 or newer within the range supported by the locked dependencies.
- `uv` for Python workspace environments.
- Node.js 22 or newer and pnpm 10 or newer for the web workspace.
- Docker Compose for local PostgreSQL and Redis.

## First-time setup

Run these commands from the repository root in PowerShell:

```powershell
Copy-Item .env.example .env
pnpm install
uv sync --all-packages
docker compose up -d postgres redis
```

Edit `.env` and replace development secret placeholders. Keep `.env` out of
version control. The control-plane API requires `AUTH_SECRET` and
`WEBHOOK_SIGNING_SECRET` to be set, even though the current API is still
primarily authenticated by API keys.

Apply the initial database migration:

```powershell
cd packages/db
uv run --env-file ../../.env alembic upgrade head
```

The PostgreSQL service in `docker-compose.yml` creates a local database named
`paxrelay` with the default development credentials shown in `.env.example`.
Use a separate secret and database for staging or production.

## Start the API and web dashboard

In one terminal:

```powershell
cd apps/api
uv run uvicorn app.main:app --reload
```

The `app.main` module is a local compatibility entry point that exposes the
FastAPI application implemented in `paxrelay_api.main`. The API listens on
`http://localhost:8000`; its health endpoint is `/health` and interactive docs
are at `/docs`.

In another terminal:

```powershell
cd apps/web
pnpm dev
```

Next.js listens on `http://localhost:3000`. Its `/api/health` route checks only
the web process. Most console pages still show sample data and do not yet call
the control-plane API.

## Optional local services

```powershell
# Paid-call gateway, from the repository root
uv run --package paxrelay-gateway uvicorn paxrelay_gateway.main:app --reload --port 8080

# Development simulator
uv run --package paxrelay-simulator uvicorn paxrelay_simulator.main:app --reload --port 8090

# Background worker
uv run --package paxrelay-worker python -m paxrelay_worker
```

The gateway defaults to its mock Paxeer adapter. The simulator fabricates
payment and settlement results. Worker loops start, but their scheduled job
handlers are currently no-ops.

## Environment variables

The shared template is [`.env.example`](../.env.example). Important settings
include:

| Variable | Used by | Notes |
| --- | --- | --- |
| `DATABASE_URL` | API, gateway, worker, migrations | Async PostgreSQL URL; local default uses `asyncpg`. |
| `AUTH_SECRET` | Control-plane settings | Required; do not use the template value outside local development. |
| `WEBHOOK_SIGNING_SECRET` | Control-plane settings | Required; the delivery implementation is unfinished. |
| `USE_MOCK_ADAPTER` | Gateway | Defaults to true in code. Do not interpret mock success as payment confirmation. |
| `PAXEER_CHAIN_ID` | Adapter configuration | Current product target is chain ID 125. |
| `RECEIPT_SIGNING_PRIVATE_KEY` | Gateway | Supply a protected signing key outside development. |
| `NEXT_PUBLIC_API_BASE_URL` | Web | Defaults to `http://localhost:8000` in the client wrapper. |

The API reads the repository `.env` and an optional `apps/api/.env` when it is
started from `apps/api`. Shell environment variables take precedence.

## Production deployment outline

The intended topology separates the public web app, control plane, gateway,
worker, PostgreSQL, Redis, and receipt storage. Before exposing any component:

1. Replace the mock payment adapter with an integration validated against the
   target Paxeer and LayerX API contracts.
2. Run migrations as a release step, not on every application start.
3. Use a secret manager for database credentials, signing keys, and webhook
   secrets. Rotate keys through a documented procedure.
4. Add tenant-safe operator authentication and role checks to the dashboard.
5. Enforce provider endpoint allowlists and response/request size limits.
6. Implement settlement reconciliation, webhook delivery, and health jobs.
7. Add readiness checks that verify dependencies separately from liveness.
8. Keep simulator services disabled in production.
9. Test backups, restoration, key loss, provider failure, and delayed settlement.

`/health` is currently a liveness response and does not verify database,
LayerX, or provider availability.
