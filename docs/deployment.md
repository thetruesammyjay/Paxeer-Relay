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
version control. The control-plane API requires `AUTH_SECRET`, even though the
current API is still primarily authenticated by API keys. Production also
requires a separate `WEBHOOK_ENCRYPTION_KEY` to protect endpoint signing
secrets at rest.

Apply all database migrations:

```powershell
cd packages/db
uv run --env-file ../../.env alembic upgrade head
```

The PostgreSQL service in `docker-compose.yml` creates a local database named
`paxrelay` with the default development credentials shown in `.env.example`.
Use a separate secret and database for staging or production.

Create the first organisation, project, and scoped API key after migrations:

```powershell
cd apps/api
uv run python -m paxrelay_api.bootstrap `
  --organisation-name "Example Team" `
  --organisation-slug example-team `
  --project-name "Development" `
  --project-slug development
```

The command prints the raw key once. Save it in a secret store. Use the
`--environment production` option only with production secrets and a production
database. The bootstrap key can issue narrower keys; revoke it after setup.

## Start the API and web dashboard

In one terminal:

```powershell
cd apps/api
uv run uvicorn app.main:app --reload
```

The `app.main` module is a local compatibility entry point that exposes the
FastAPI application implemented in `paxrelay_api.main`. The API listens on
`http://localhost:8000`; `/health` reports liveness, `/ready` checks PostgreSQL
and Redis when API rate limiting is enabled, and interactive docs are at
`/docs`. Send API-key scopes that match each route.

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
payment and settlement results. The worker expires policy approvals, fans
supported outbox events into delivery rows, and sends signed webhooks. Settlement
reconciliation, provider health, analytics, and provider indexing remain no-ops.

## Environment variables

The shared template is [`.env.example`](../.env.example). Important settings
include:

| Variable | Used by | Notes |
| --- | --- | --- |
| `DATABASE_URL` | API, gateway, worker, migrations | PostgreSQL URL; common `postgres://` and `postgresql://` provider URLs, including Neon `sslmode` URLs, are normalized for `asyncpg`. |
| `API_CORS_ORIGINS` | Control-plane API | JSON array of exact browser origins allowed to call the API; defaults to `["http://localhost:3000"]` for development. Staging and production require one or more HTTPS origins. |
| `REDIS_URL` | API and gateway | Required in staging/production when rate limiting is enabled. `RAILWAY_REDIS_URL` is also accepted. |
| `REDIS_KEY_PREFIX` | API and gateway | Redis namespace for rate-limit counters; defaults to `paxrelay`. |
| `API_RATE_LIMIT_MAX_REQUESTS` | Control-plane API | Maximum requests per API key per fixed window; defaults to 300. |
| `API_RATE_LIMIT_WINDOW_SECONDS` | Control-plane API | Fixed-window duration in seconds; defaults to 60. |
| `API_RATE_LIMIT_ENABLED` | Control-plane API | Optional override for development/staging. Production cannot disable rate limiting. |
| `GATEWAY_RATE_LIMIT_MAX_REQUESTS` | Gateway | Maximum requests per key per window; defaults to 120. |
| `GATEWAY_RATE_LIMIT_WINDOW_SECONDS` | Gateway | Fixed-window duration; defaults to 60 seconds. |
| `GATEWAY_RATE_LIMIT_ENABLED` | Gateway | Optional override for development/staging. Production cannot disable rate limiting. |
| `PROVIDER_ENDPOINT_HOST_ALLOWLIST` | Gateway | Comma-separated exact hostnames that provider URLs may target. Required in production; wildcard entries are not supported. |
| `API_MAX_REQUEST_BYTES` | Control-plane API | Maximum write-request body size; defaults to 1 MiB and can be set from 1 KiB to 10 MiB. |
| `GATEWAY_MAX_REQUEST_BYTES` | Gateway | Maximum invocation request body; defaults to 1 MiB and can be set from 1 KiB to 10 MiB. |
| `GATEWAY_MAX_RESPONSE_BYTES` | Gateway | Maximum provider response body; defaults to 10 MiB and can be set from 1 KiB to 100 MiB. |
| `GATEWAY_REQUEST_TIMEOUT_SECONDS` | Gateway | Upper bound for provider response time; defaults to 30 seconds, capped at 120. |
| `GATEWAY_CONNECT_TIMEOUT_SECONDS` | Gateway | Provider connection timeout; defaults to 5 seconds, capped at 30. |
| `POLICY_APPROVAL_TTL_SECONDS` | Gateway | How long a policy approval can be acted on; defaults to 900 seconds, range 60 seconds to 24 hours. |
| `AUTH_SECRET` | Control-plane settings | Required; production requires a unique random value of at least 40 characters. |
| `WEBHOOK_ENCRYPTION_KEY` | API and worker | Production requires a unique random value of at least 40 characters. Keep it stable while encrypted webhook secrets exist; rotate it only with a re-encryption rollout. |
| `WEBHOOK_MAX_ATTEMPTS` | Worker | Maximum attempts per delivery; defaults to 8. |
| `WEBHOOK_INITIAL_RETRY_SECONDS` | Worker | Base exponential retry delay; defaults to 30 seconds and caps at one hour. |
| `WEBHOOK_REQUEST_TIMEOUT_SECONDS` | Worker | Total webhook request deadline; defaults to 10 seconds, maximum 60. |
| `WEBHOOK_MAX_REQUEST_BYTES` | Worker | Maximum serialized event size; defaults to 1 MiB. |
| `WEBHOOK_MAX_RESPONSE_BYTES` | Worker | Maximum response body read; defaults to 64 KiB. |
| `WEBHOOK_DELIVERY_BATCH_SIZE` | Worker | Upper bound on rows selected at once; defaults to 50, also limited by delivery concurrency. |
| `WEBHOOK_DELIVERY_CONCURRENCY` | Worker | Maximum concurrent webhook requests; defaults to 10. |
| `WEBHOOK_DELIVERY_LEASE_SECONDS` | Worker | Recovery time for a delivery claimed by a worker that stopped; defaults to 120 seconds. |
| `READINESS_TIMEOUT_SECONDS` | API and gateway | PostgreSQL and Redis readiness deadline; defaults to 3 seconds. |
| `APP_ENV` | API and gateway | Use the same tenant environment for the services; the gateway accepts `development`, `test`, `staging`, or `production`. The gateway allows private provider URLs and HTTP only in development/test; staging/production require HTTPS and public destination IPs. |
| `USE_MOCK_ADAPTER` | Gateway | Defaults to true for development. Production startup rejects true. The official adapter still needs independent validation against the live network contracts. |
| `LAYERX_API_URL` | Gateway | Required as an HTTPS URL in production. |
| `PAXEER_CHAIN_ID` | Gateway | Current production target is chain ID 125. |
| `PAXEER_RPC_URL` | Gateway | Must use HTTPS in production. |
| `RECEIPT_SIGNING_PRIVATE_KEY` | Gateway | Production requires a protected PEM key; keep it in a secret manager. |
| `RECEIPT_SIGNING_KEY_ID` | Gateway | Must identify the production receipt key and cannot be `local-development`. |
| `NEXT_PUBLIC_API_BASE_URL` | Web | Defaults to `http://localhost:8000` in the client wrapper. |

The API reads the repository `.env` and an optional `apps/api/.env` when it is
started from `apps/api`. Shell environment variables take precedence.

## Production deployment outline

The intended topology separates the public web app, control plane, gateway,
worker, PostgreSQL, Redis, and receipt storage. Before exposing any component:

1. Validate the non-mock payment adapter against authoritative Paxeer and
   LayerX API contracts, including chain finality and replay behavior. The
   production configuration rejects mock mode but does not validate external
   payment semantics.
2. Run migrations as a release step, not on every application start.
3. Use a secret manager for database credentials, signing keys, and webhook
   secrets. Rotate keys through a documented procedure.
4. Add tenant-safe operator authentication and role checks to the dashboard.
5. Set `PROVIDER_ENDPOINT_HOST_ALLOWLIST` to exact provider hostnames in
   production and enforce outbound network egress rules. The gateway validates
   DNS answers, pins the selected public IP for each forwarded request, and
   rejects redirects, but it does not verify public hostname ownership. Keep
   request/response size limits enabled.
6. Complete settlement reconciliation and health jobs, and verify webhook
   delivery behavior in staging before enabling production subscriptions.
7. Configure orchestrator liveness on `/health` and readiness on `/ready`.
8. Keep simulator services disabled in production.
9. Test backups, restoration, key loss, provider failure, and delayed settlement.

The API `/ready` endpoint checks PostgreSQL and Redis when its limiter is
enabled. The gateway `/ready` endpoint checks PostgreSQL and Redis when its
limiter is enabled. Neither checks LayerX, the Paxeer network, or provider
availability.
