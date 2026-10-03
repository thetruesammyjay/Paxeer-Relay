# Operations

This document describes the operational behavior of the current pre-alpha
services and the work still needed before production use.

## Processes and health endpoints

| Process | Local port | Health behavior |
| --- | ---: | --- |
| Web console | 3000 | `GET /api/health` reports the Next.js process only. |
| Control-plane API | 8000 | `GET /health` is liveness; `GET /ready` checks PostgreSQL and Redis when API rate limiting is enabled. |
| Gateway | 8080 | `GET /health` is liveness; `GET /ready` checks PostgreSQL and Redis when gateway rate limiting is enabled. |
| Simulator | 8090 | `GET /health` reports process status and environment. |
| Worker | none | Long-running process; no HTTP health endpoint is currently exposed. |

Use `/health` for liveness and `/ready` for API or gateway readiness. The API
checks PostgreSQL and Redis when API rate limiting is enabled. The gateway
checks PostgreSQL and Redis when gateway rate limiting is enabled. Neither
readiness check confirms payment-network or provider availability. A not-ready
response is HTTP 503 and does not expose connection details.

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
| Gateway 401 | Missing, invalid, expired, or out-of-tenant credentials | Check the bearer key, `gateway:invoke` grant, environment, and selected agent's tenant. |
| Gateway 403 | Key lacks gateway scope, agent is inactive, no active policy, or policy denial | Issue the minimum required gateway scope or inspect agent state, assignment, price, and policy explanation. |
| Gateway 402 | Payment is required or submitted proof did not verify | Check quote expiry and every bound proof field. Never bypass verification to force execution. |
| Gateway 503 | LayerX or another payment verification dependency could not provide usable evidence | Wait for the dependency to recover, then retry with the same quote and proof. The gateway has not consumed the quote nonce. |
| Gateway 202 | Policy requires human approval | Review the tenant-scoped approval in the API. After approval, the agent must retry the original invoke with the same idempotency key and payload before a payment quote is issued. |
| Gateway 409 | The quote nonce was already claimed, an idempotency key conflicts with stored request data/state, or a pre-migration completed call has no saved result | Do not resubmit a claimed proof or alter a request under the same key. Check the tool-call and execution-attempt records; a reserved call may need reconciliation after a gateway interruption. |
| Gateway 410 | The payment quote expired | Start a new request with a new idempotency key to obtain a fresh quote. |
| Gateway 413 | Invocation body exceeds `GATEWAY_MAX_REQUEST_BYTES` | Reduce the payload or review the configured cap. |
| Gateway 429 | An authenticated API key exceeded the gateway request limit | Wait for `Retry-After` seconds or ask an administrator to review the key quota. |
| Gateway 503 | PostgreSQL or Redis is unavailable, or the selected provider endpoint failed its pre-quote safety check | Check `/ready` for dependency failures. For `provider_endpoint_unavailable`, correct the provider URL, DNS, or production hostname allowlist; no payment challenge was issued. |
| Gateway 502 | Provider returned a non-2xx response, timed out, could not be reached, was rejected during the final destination check, or exceeded the response-size cap | Inspect attempt status and provider endpoint. A final destination rejection or oversized response can happen after payment is verified; an oversized response is recorded as unknown execution. |
| API 401 | Missing, invalid, or expired bearer API key | Reissue a key through the bootstrap or key-management process; raw keys are returned only once. |
| API 403 | The key does not have the required route scope | Ask a key administrator to issue a new key with the minimum required grant. |
| API 429 | An authenticated API key exceeded its configured request limit | Wait for `Retry-After` seconds or ask an administrator to review that key's traffic and configured quota. |
| API 503 | PostgreSQL is unavailable, or Redis is unavailable while rate limiting is enabled | Check dependency health and `/ready`; authenticated requests fail closed if the limiter cannot enforce its limit. |
| API 422 | Request schema or query validation failed | Use the structured error code/message and correct the named field. |
| API 413 | A write request body exceeds `API_MAX_REQUEST_BYTES` | Reduce the payload or review the configured cap; the default is 1 MiB. |
| API 500 | Unexpected application error | Use server logs and request context; the response intentionally omits stack details. |

## Payment and execution incidents

The gateway verifies and records payment before forwarding to the provider. A
provider failure can therefore leave a verified payment and failed request.
The current implementation has no automatic refund or dispute flow. Preserve
the payment, tool-call, and execution-attempt IDs while investigating; do not
replay a paid operation to a different provider without an explicit recovery
decision.

Current automatic provider failover is not implemented. Reconciliation checks
local payment, intent, and quote consistency, reads the stored transaction from
LayerX, and can check a settlement record and batch through the configured
Paxeer settlement adapter. Missing evidence or upstream errors are retried;
contradictions are put in the tenant-scoped review queue. The worker never
advances payment state. Review the external endpoint contract with the network
operator before using the result for financial operations.

## Background work status

The worker starts seven periodic job loops:

| Job | Interval | Current behavior |
| --- | ---: | --- |
| Approval expiration | 30 seconds | Marks overdue pending or approved requests and their still-pending tool calls expired; writes an audit row in the same transaction. A locked row is skipped until the next scan. |
| Outbox fan-out | 5 seconds | Moves supported transactional events into durable webhook delivery rows. |
| Webhook delivery | 2 seconds | Claims due rows, signs and sends bounded HTTP requests, and applies retry or terminal state. |
| Health check | 30 seconds | Probes each due active service's configured health path with a bounded GET, rejects unsafe DNS results, pins requests to checked public IPs outside development/test, and removes a service from routing after its configured consecutive-failure threshold. |
| Provider indexing | 60 seconds | Aggregates terminal provider attempts over the configured rolling window into per-service success rate, average latency, call count, and trailing failure count. |
| Analytics | Configured, 60 seconds by default | Logs a stub tick; does not aggregate records. |
| Settlement reconciliation | Configured, 30 seconds by default | Compares payment, intent, and quote; reads LayerX transaction and settlement/batch evidence; verifies the claimed L1 receipt when configured. Uses a short database claim and exponential retry. Records mismatches and emits a webhook event; does not change payment state. |

Approval expiration, outbox fan-out, webhook delivery, and reconciliation
perform business work. The worker writes a tenant-scoped
review record when persisted or external payment facts disagree. Records
without enough evidence remain `awaiting_external` or `layerx_confirmed` with
`next_attempt_at` and `last_error` shown in the API. `reconciled` means the
configured adapter confirmed all required L1 evidence; it does not change the
payment state. Inspect records at `GET /v1/settlements/reconciliation` with a
key holding `settlements:read`.
An `adapter_not_configured` error means the worker lacks its L1 settlement
contract address, commitment event topic, or confirmation depth; production
startup rejects missing values. A `mismatch` status needs analyst review.
Approval status updates can lag the configured expiry by up to one scan
interval plus processing time. Webhook delivery is at least once: a worker may
send successfully and stop before persisting the response, so receivers should
deduplicate by `X-PaxRelay-Delivery-Id`. Requests have a 10-second default
timeout, 1 MiB body limit, and 64 KiB response limit. Retryable failures use
exponential backoff, capped at one hour, for up to eight attempts by default.
The analytics aggregation loop remains a placeholder and does not materialize
hourly or daily spend rows. Health probing and provider indexing update routing
metrics, but do not validate payment-network availability or guarantee that a
provider's paid operation will succeed.

Webhook signatures use HMAC-SHA256 over the exact request bytes prefixed by the
Unix timestamp, delivery ID, and event type:
`timestamp + "." + delivery_id + "." + event_type + "." + raw_body`. The signature is
sent as `X-PaxRelay-Signature: sha256=<hex>` with `X-PaxRelay-Timestamp`,
`X-PaxRelay-Event`, `X-PaxRelay-Event-Id`, and `X-PaxRelay-Delivery-Id`.
Receivers should verify the signature in constant time, enforce a timestamp
window, and deduplicate delivery IDs. Staging and production require HTTPS and
globally routable DNS answers; the worker pins the connection to checked IPs
and does not follow redirects.

Use `GET /v1/webhooks/{webhook_id}/deliveries` to inspect recent outcomes. For
`failed` or `cancelled` rows, correct the endpoint configuration if needed and
call `POST /v1/webhooks/{webhook_id}/deliveries/{delivery_id}/retry`. The API
returns HTTP 202 after it resets the attempt counter, records the operator key
in the audit log, and queues a new delivery cycle. The worker performs the send
asynchronously.

## Credentials and key operations

- Store `.env`, database credentials, API keys, and receipt signing keys in a
  secret manager outside local development.
- Keep the receipt verification keyring manifest under controlled versioning.
  Add a new public key before its signing cutover, mark the former key retired
  with that cutover as `not_after`, and distribute the updated manifest to all
  verifiers. The API can serve the public-only file configured by
  `RECEIPT_PUBLIC_KEYRING_FILE` at `GET /v1/receipt-keys`; mount it read-only
  and replace it atomically. The endpoint reads the file on each request and
  disables caching. Mark compromised keys revoked and distribute that update
  promptly; revoked keys invalidate receipts signed with that key.
- The API stores a SHA-256 hash of each API key and returns the raw key only at
  creation. API keys have per-resource scopes, a 90-day default expiry, an
  inventory endpoint, and a revocation endpoint. A key cannot grant scopes it
  does not hold itself.
- Paid-call routes require a tenant API key with `gateway:invoke`. The
  `X-Agent-Id` value must identify an active agent in that key's tenant. Create
  a dedicated gateway key and revoke bootstrap keys after provisioning.
- Gateway key `last_used_at` updates run after the paid-call response in a
  separate short transaction, so provider calls do not hold the key row lock.
- Bootstrap an organisation/project and its first API key with
  `python -m paxrelay_api.bootstrap` after applying database migrations. The
  command prints the full-scope key once. Store it safely, issue narrower keys,
  then revoke the bootstrap key when it is no longer needed.
- Migration `0002` disables webhook endpoints created before encrypted secret
  storage. Recreate or rotate those endpoints after the migration. The worker
  requires the matching `WEBHOOK_ENCRYPTION_KEY` to sign deliveries.
- Successful control-plane writes and each successful item in a batch are
  recorded in `audit_logs` in the same transaction as the change. Entries
  include the API-key actor, request ID, and ASGI peer address, but not request
  bodies or secret values. The API exposes tenant-scoped lookup at
  `GET /v1/audit-logs`; define retention and external archival before production.
- `AUTH_SECRET` is required. `WEBHOOK_ENCRYPTION_KEY` is also required in
  production and must be distinct from `AUTH_SECRET`. Keep it stable while
  encrypted webhook secrets exist. Rotation requires re-encrypting stored
  endpoint secrets before removing the old key.
Production startup rejects placeholder, short, or reused values. Approval records
expire after `POLICY_APPROVAL_TTL_SECONDS`. The worker marks overdue requests
expired every 30 seconds and records the transition in the audit log; the
approved route, price, destination, and policy version are rechecked before the
gateway issues a quote.
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
