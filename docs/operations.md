# Operations

This document describes the operational behavior of the current pre-alpha
services and the work still needed before production use.

## Processes and health endpoints

| Process | Local port | Health behavior |
| --- | ---: | --- |
| Web console | 3000 | `GET /api/health` reports the Next.js process only. |
| Control-plane API | 8000 | `GET /health` returns `{"status":"ok"}` without checking PostgreSQL. |
| Gateway | 8080 | `GET /health` returns `{"status":"ok"}` without checking PostgreSQL or upstream services. |
| Simulator | 8090 | `GET /health` reports process status and environment. |
| Worker | none | Long-running process; no HTTP health endpoint is currently exposed. |

Use health routes for liveness only. Do not use them as database, payment, or
provider readiness checks.

## Start and stop local dependencies

From the repository root:

```powershell
docker compose up -d postgres redis
docker compose ps
docker compose logs -f postgres redis
docker compose down
```

The PostgreSQL data volume persists across container restarts. `docker compose
down -v` removes the persisted development database and must only be used when
that data is disposable.

## Request failure interpretation

| Signal | Meaning in current code | Operator action |
| --- | --- | --- |
| Gateway 401 | Missing or malformed `X-Agent-Id`, or unknown agent | Confirm caller identity and that the agent exists. |
| Gateway 403 | Agent inactive, no active policy, or enforced policy denial | Inspect agent state, assignment, price, limits, and explanation. |
| Gateway 402 | Payment is required or submitted proof did not verify | Check quote expiry and every bound proof field. Never bypass verification to force execution. |
| Gateway 502 | Provider returned a non-2xx response, timed out, or could not be reached | Inspect attempt status and provider endpoint. Payment may already be verified. |
| API 401 | Missing, invalid, or expired bearer API key | Reissue a key through an authorised process; raw keys are returned only once. |
| API 422 | Request schema or query validation failed | Use the structured error code/message and correct the named field. |
| API 500 | Unexpected application error | Use server logs and request context; the response intentionally omits stack details. |

## Payment and execution incidents

The gateway verifies and records payment before forwarding to the provider. A
provider failure can therefore leave a verified payment and failed request.
The current implementation has no automatic refund or dispute flow. Preserve
the payment, tool-call, and execution-attempt IDs while investigating; do not
replay a paid operation to a different provider without an explicit recovery
decision.

Current automatic provider failover is not implemented. Worker reconciliation
is also a no-op, so do not assume that payment states will advance from
`verified` to LayerX settlement or L1 anchoring in the background.

## Background work status

The worker starts five periodic job loops:

| Job | Interval | Current behavior |
| --- | ---: | --- |
| Outbox | 5 seconds | Logs a stub tick; does not publish events. |
| Health check | 30 seconds | Logs a stub tick; does not probe service URLs. |
| Provider indexing | 60 seconds | Logs a stub tick; does not refresh metrics. |
| Analytics | Configured, 60 seconds by default | Logs a stub tick; does not aggregate records. |
| Settlement reconciliation | Configured, 30 seconds by default | Logs a stub tick; does not query LayerX or update payment state. |

Do not use worker startup as evidence that any of those business processes are
running.

## Credentials and key operations

- Store `.env`, database credentials, API keys, and receipt signing keys in a
  secret manager outside local development.
- The API stores a SHA-256 hash of each API key and returns the raw key only at
  creation. There is no key-revocation route in the current API; disable or
  revoke through a controlled database operation until a management route is
  implemented.
- `AUTH_SECRET` and `WEBHOOK_SIGNING_SECRET` are required settings. Rotate them
  deliberately and coordinate any consumers that rely on them.
- Replace the gateway's generated development signing-key fallback before
  issuing receipts that users may rely on. The fallback is generated when the
  process imports its app module and is not a stable key across restarts.
- Use different keys and databases for development, staging, and production.

## Backup and recovery

Back up PostgreSQL before schema changes and define a restore procedure before
production. The repository does not currently include automated backup,
retention, point-in-time recovery, or object-storage archival jobs. The
simulator's provider registry is in memory and is intentionally lost on restart.

## Incident response checklist

1. Stop or isolate the affected agent or provider at the operational layer.
2. Preserve tool-call, payment, provider-attempt, and receipt identifiers.
3. Separate verified payment from provider delivery and settlement status.
4. Check whether the gateway ran in mock mode before interpreting transaction
   hashes or settlement data.
5. Review API and gateway logs without copying credentials or payment proofs
   into public tickets.
6. Record the impact, recovery action, and missing control in the incident log.
