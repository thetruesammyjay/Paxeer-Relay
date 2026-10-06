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
version control. The API requires `AUTH_SECRET`; production also requires a
separate `WEBHOOK_ENCRYPTION_KEY`. Staging and production dashboard sign-in
requires an OIDC provider and separate high-entropy web-session and internal
assertion secrets.

Apply all database migrations. Alembic uses an existing shell `DATABASE_URL`;
otherwise it reads the current folder's `.env`, then falls back to the
repository root `.env`. Run the same command from either `apps/api` or
`packages/db`:

```powershell
uv run python -m alembic upgrade head
```

The shared virtual environment is at the repository root. If you invoke its
Python executable directly from `apps/api` or `packages/db`, use
`..\..\.venv\Scripts\python.exe -m alembic upgrade head`.

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
  --project-slug development `
  --owner-email "owner@example.com"
```

The command creates the initial owner membership when `--owner-email` is
provided. This email must match the verified OIDC email used at sign-in.
`--owner-email` is required for staging and production bootstrap. The command
also requires `APP_ENV` to match the selected `--environment`. It prints the
raw machine key once; save it in a secret store. Use the
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
the web process. Development supports a scoped API key in memory for local
work. Staging and production require OIDC sign-in; the web server proxies API
requests and sends a short-lived assertion to FastAPI. Configure the identity
provider callback URL as `https://<web-host>/api/auth/callback/workspace-sso`.
The user's verified email must be provisioned as a project member before the
first sign-in. The selected project and its role are checked by the API on each
request.

Set `APP_ENV` and `NEXT_PUBLIC_APP_ENV` to the same deployment environment.
Set `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, and a unique
`WEB_AUTH_SECRET` on the web service. Set `DASHBOARD_OIDC_ISSUER` to the exact
same issuer and a different `INTERNAL_DASHBOARD_AUTH_SECRET` on both the web
and API services. Set `PAXRELAY_API_BASE_URL` on the web service to the API's
HTTPS origin. The web server does not need a browser-visible API key. Staging
and production API rate limiting and one-use assertion checks require Redis.

## Optional local services

```powershell
# Paid-call gateway, from the repository root
uv run --package paxrelay-gateway uvicorn paxrelay_gateway.main:app --reload --port 8080

# Development simulator
uv run --package paxrelay-simulator uvicorn paxrelay_simulator.main:app --reload --port 8090

# Background worker
uv run --package paxrelay-worker python -m paxrelay_worker
```

The gateway and worker default to their mock Paxeer adapter. The simulator
fabricates payment and settlement results. The worker expires policy approvals,
marks abandoned paid executions as unknown without retrying them, fans supported
outbox events into delivery rows, sends signed webhooks, and reconciles local
payment facts with LayerX transaction reads. It supports
settlement and batch reads through a separately configured adapter endpoint.
Provider health probes and routing-metric indexing are implemented; worker
analytics materialization is implemented as hourly and daily spend rollups.
The worker exposes internal liveness and readiness endpoints on port 8081 by
default; keep that port private to the deployment network. Staging and production require
`USE_MOCK_ADAPTER=false` and exact provider hostnames in
`PROVIDER_ENDPOINT_HOST_ALLOWLIST`. This keeps staging on the configured
network adapter and limits provider requests to approved hosts. Staging must
also set `PAXEER_NETWORK_ENVIRONMENT` to `testnet` or `staging`; it cannot use
the `mainnet` label. This is a startup guard on the declared environment. Verify
the RPC and LayerX endpoint identities and the reported chain ID with the
network operator before submitting any staging payment; the label does not
independently attest the configured endpoints. Staging must provide its own
HTTPS `PAXEER_RPC_URL` and `LAYERX_API_URL`; the default mainnet RPC is rejected.

## Environment variables

The shared template is [`.env.example`](../.env.example). Important settings
include:

| Variable | Used by | Notes |
| --- | --- | --- |
| `DATABASE_URL` | API, gateway, worker, migrations | PostgreSQL URL; common `postgres://` and `postgresql://` provider URLs, including Neon `sslmode` URLs, are normalized for `asyncpg`. |
| `API_CORS_ORIGINS` | Control-plane API | JSON array of exact browser origins allowed to call the API; defaults to `["http://localhost:3000"]` for development. Staging and production require one or more HTTPS origins. |
| `REDIS_URL` | API and gateway | Required in staging/production when rate limiting is enabled. `RAILWAY_REDIS_URL` is also accepted. |
| `REDIS_KEY_PREFIX` | API and gateway | Redis namespace for rate-limit counters; defaults to `paxrelay`. |
| `API_RATE_LIMIT_MAX_REQUESTS` | Control-plane API | Maximum requests per machine key or signed-in user per project and fixed window; defaults to 300. |
| `API_RATE_LIMIT_WINDOW_SECONDS` | Control-plane API | Fixed-window duration in seconds; defaults to 60. |
| `API_RATE_LIMIT_ENABLED` | Control-plane API | Optional development override. Staging and production cannot disable rate limiting or one-use dashboard assertions. |
| `GATEWAY_RATE_LIMIT_MAX_REQUESTS` | Gateway | Maximum requests per key per window; defaults to 120. |
| `GATEWAY_RATE_LIMIT_WINDOW_SECONDS` | Gateway | Fixed-window duration; defaults to 60 seconds. |
| `GATEWAY_RATE_LIMIT_ENABLED` | Gateway | Optional override for development/staging. Production cannot disable rate limiting. |
| `GATEWAY_MAX_CONCURRENT_REQUESTS_PER_KEY` | Gateway | Maximum in-flight authenticated requests per API key; defaults to 10 when gateway Redis limits are enabled. |
| `GATEWAY_CONCURRENCY_LEASE_SECONDS` | Gateway | Recovers in-flight slots after a crashed request; defaults to 600 seconds and must exceed the provider timeout plus payment-verification allowance. |
| `PROVIDER_ENDPOINT_HOST_ALLOWLIST` | Gateway and worker | Comma-separated exact hostnames that provider URLs may target. Required in staging and production; wildcard entries are not supported. |
| `WORKER_HEALTH_HOST` | Worker | Bind address for internal `/health` and `/ready`; defaults to `0.0.0.0`. Keep the listener private to the deployment network. |
| `WORKER_HEALTH_PORT` | Worker | Internal health listener port; defaults to `8081`. |
| `EXECUTION_RECOVERY_INTERVAL_SECONDS` | Worker | Scan interval for paid attempts abandoned by a stopped gateway; defaults to 60 seconds. |
| `EXECUTION_RECOVERY_STALE_SECONDS` | Worker | Age before a reserved or running attempt is marked unknown; defaults to 300 seconds and must be at least 180. |
| `EXECUTION_RECOVERY_BATCH_SIZE` | Worker | Maximum stale attempts recovered per scan; defaults to 100. |
| `API_MAX_REQUEST_BYTES` | Control-plane API | Maximum write-request body size; defaults to 1 MiB and can be set from 1 KiB to 10 MiB. |
| `GATEWAY_MAX_REQUEST_BYTES` | Gateway | Maximum invocation request body; defaults to 1 MiB and can be set from 1 KiB to 10 MiB. |
| `GATEWAY_MAX_RESPONSE_BYTES` | Gateway | Maximum provider response body; defaults to 10 MiB and can be set from 1 KiB to 100 MiB. |
| `GATEWAY_REQUEST_TIMEOUT_SECONDS` | Gateway | Upper bound for provider response time; defaults to 30 seconds, capped at 120. |
| `GATEWAY_CONNECT_TIMEOUT_SECONDS` | Gateway | Provider connection timeout; defaults to 5 seconds, capped at 30. |
| `POLICY_APPROVAL_TTL_SECONDS` | Gateway | How long a policy approval can be acted on; defaults to 900 seconds, range 60 seconds to 24 hours. |
| `AUTH_SECRET` | Control-plane settings | Required; staging and production require a unique, non-template random value of at least 40 characters. |
| `OIDC_ISSUER` | Web | OIDC issuer URL; must match `DASHBOARD_OIDC_ISSUER` exactly. Required in staging/production. |
| `OIDC_CLIENT_ID` | Web | Client ID registered with the identity provider. Required in staging/production. |
| `OIDC_CLIENT_SECRET` | Web | Secret registered with the identity provider; store in the deployment secret manager. |
| `WEB_AUTH_SECRET` | Web | Auth.js session encryption secret; at least 40 random characters in staging/production and different from the API and internal assertion secrets. |
| `INTERNAL_DASHBOARD_AUTH_SECRET` | Web and API | Shared HMAC secret for one-use, 60-second web-to-API assertions; at least 40 random characters and different from both services' session/API secrets. |
| `DASHBOARD_OIDC_ISSUER` | API | Must exactly match the web's `OIDC_ISSUER`; HTTPS required in staging/production. |
| `PAXRELAY_API_BASE_URL` | Web server | Private server-side control-plane API origin; HTTPS required in staging/production. |
| `NEXT_PUBLIC_APP_ENV` | Web browser | Expected tenant environment; set to the same value as `APP_ENV`. |
| `WEBHOOK_ENCRYPTION_KEY` | API and worker | Production requires a unique random value of at least 40 characters. Keep it stable while encrypted webhook secrets exist; rotate it only with a re-encryption rollout. |
| `WEBHOOK_MAX_ATTEMPTS` | Worker | Maximum attempts per delivery; defaults to 8. |
| `WEBHOOK_INITIAL_RETRY_SECONDS` | Worker | Base exponential retry delay; defaults to 30 seconds and caps at one hour. |
| `WEBHOOK_REQUEST_TIMEOUT_SECONDS` | Worker | Total webhook request deadline; defaults to 10 seconds, maximum 60. |
| `WEBHOOK_MAX_REQUEST_BYTES` | Worker | Maximum serialized event size; defaults to 1 MiB. |
| `WEBHOOK_MAX_RESPONSE_BYTES` | Worker | Maximum response body read; defaults to 64 KiB. |
| `WEBHOOK_DELIVERY_BATCH_SIZE` | Worker | Upper bound on rows selected at once; defaults to 50, also limited by delivery concurrency. |
| `WEBHOOK_DELIVERY_CONCURRENCY` | Worker | Maximum concurrent webhook requests; defaults to 10. |
| `WEBHOOK_DELIVERY_LEASE_SECONDS` | Worker | Recovery time for a delivery claimed by a worker that stopped; defaults to 120 seconds. |
| `RECONCILIATION_BATCH_SIZE` | Worker | Maximum settlement rows claimed per scan; defaults to 50. |
| `RECONCILIATION_CONCURRENCY` | Worker | Maximum concurrent adapter lookups; defaults to 10. |
| `RECONCILIATION_CLAIM_LEASE_SECONDS` | Worker | Reclaims rows held by a stopped worker; must exceed five upstream request timeouts. |
| `RECONCILIATION_RETRY_INITIAL_SECONDS` | Worker | Initial retry delay for incomplete or unavailable external evidence; defaults to 30 seconds. |
| `RECONCILIATION_RETRY_MAX_SECONDS` | Worker | Maximum exponential retry delay; defaults to one hour. |
| `PROVIDER_HEALTH_CONCURRENCY` | Worker | Maximum number of simultaneous provider health checks; defaults to 10. |
| `PROVIDER_METRICS_WINDOW_DAYS` | Worker | Rolling history window for provider success and latency metrics; defaults to 7 days. |
| `PROVIDER_METRICS_TRAILING_ATTEMPTS` | Worker | Maximum recent attempts scanned for a failure streak; defaults to 100. |
| `READINESS_TIMEOUT_SECONDS` | API and gateway | PostgreSQL and Redis readiness deadline; defaults to 3 seconds. |
| `APP_ENV` | API, gateway, worker, and web server | Use the same tenant environment for the services; accepted values are `development`, `test`, `staging`, and `production`. The gateway allows private provider URLs and HTTP only in development/test; staging/production require HTTPS and public destination IPs. |
| `USE_MOCK_ADAPTER` | Gateway and worker | Defaults to true for development. Staging and production startup reject true. |
| `PAXEER_NETWORK_ENVIRONMENT` | Gateway and worker | Use `testnet` or `staging` for staging deployments and `mainnet` for production. Staging startup rejects `mainnet`. |
| `LAYERX_API_URL` | Gateway and worker | Required as an HTTPS URL when the official adapter is enabled. The adapter expects `GET /transactions/{transaction_hash}` to return the transaction amount, recipient, and quote ID/memo. |
| `PAXEER_ADAPTER_TIMEOUT_SECONDS` | Worker | Timeout for each individual LayerX or settlement read; defaults to 15 seconds. |
| `PAXEER_SETTLEMENT_API_URL` | Worker | Required as an HTTPS URL when the official adapter is enabled. The adapter expects a read-only `GET /settlement/{settlement_id}` resource. Confirm this assumed path and response fields with the network operator. |
| `PAXEER_L1_SETTLEMENT_CONTRACT_ADDRESS` | Worker | Required in staging and production; deployed contract address used to filter receipt logs. |
| `PAXEER_L1_COMMITMENT_EVENT_TOPIC` | Worker | Required in staging and production; 32-byte event signature topic. The verifier looks for the exact commitment as an indexed topic or 32-byte ABI data word. |
| `PAXEER_L1_CONFIRMATION_BLOCKS` | Worker | Required in staging and production; positive confirmation depth set from the network's finality policy. |
| `PAXEER_CHAIN_ID` | Gateway and worker | The current production target is chain ID 125. Configure the staging network's chain ID for staging. |
| `PAXEER_RPC_URL` | Gateway and worker | Staging and production require HTTPS. Staging must use its configured network's endpoint. |
| `RECEIPT_SIGNING_PRIVATE_KEY` | Gateway | Production requires a protected PEM key; keep it in a secret manager. |
| `RECEIPT_SIGNING_KEY_ID` | Gateway | Must identify the production receipt key and cannot be `local-development`. |
| `RECEIPT_PUBLIC_KEYRING_FILE` | Control-plane API | Optional path to the public version 1 receipt-key manifest served at `GET /v1/receipt-keys`; mount it read-only and replace it atomically for rotation or revocation updates. |
| `NEXT_PUBLIC_API_BASE_URL` | Web browser | Direct API URL for local development API-key mode. Protected deployments use the private `PAXRELAY_API_BASE_URL` server setting. |

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
6. Validate the LayerX and Paxeer read endpoints against authoritative network
   contracts and staging records. Confirm transaction field meanings, batch
   membership, settlement contract address, commitment event topic, and
   confirmation depth. The worker never advances payment state; it records
   only evidence that passed these checks.
7. Configure orchestrator liveness on `/health` and readiness on `/ready`.
8. Keep simulator services disabled in production.
9. Test backups, restoration, key loss, provider failure, and delayed settlement.

The API `/ready` endpoint checks PostgreSQL and Redis when its limiter is
enabled. The gateway `/ready` endpoint checks PostgreSQL and Redis when its
limiter is enabled. Neither checks LayerX, the Paxeer network, or provider
availability.
