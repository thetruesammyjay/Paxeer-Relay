# Threat model

This is a source-based threat model for the current pre-alpha checkout. It is
not an independent security review. PaxRelay handles agent identity, payment
proofs, provider requests, and operational records; errors in any one boundary
can cause unauthorised spending, data exposure, or inconsistent delivery.

## Assets

- API keys, database credentials, receipt-signing keys, and webhook secrets.
- Tenant records: agents, wallets, policies, provider configuration, calls,
  payments, receipts, and audit information.
- Payment requirements, proofs, nonces, LayerX transaction identifiers, and
  settlement references.
- Provider endpoint access and the request arguments sent to those endpoints.
- Policy limits and approval decisions.
- Integrity of routing explanations and signed receipt data.

## Actors and trust boundaries

```text
Human operator ── browser ── Next.js ── control-plane API ── PostgreSQL
Agent caller ─────────────── gateway ── payment adapter / provider endpoints
                                      └─ PostgreSQL
Worker ─────────────── database / Redis / network adapters
```

Treat browsers, agent callers, providers, wallet clients, LayerX responses,
and public RPC responses as untrusted. The database and secret store are
trusted only when access is restricted and backups are protected.

## Current high-risk gaps

| Risk | Current behavior | Required mitigation |
| --- | --- | --- |
| Agent impersonation | Gateway requires a hashed bearer API key with `gateway:invoke`, and checks that the selected agent is active and in the key's organisation, project, and environment. Keys remain project-wide, so a gateway key can act as any agent in that project. | Issue dedicated least-privilege gateway keys, keep them secret, and consider per-agent credentials if the product requires that boundary. |
| Cross-agent call completion | The completion path checks that the stored call belongs to the exact authenticated agent before reading its quote or accepting proof. | Preserve this ownership check in every future completion, retry, cancellation, and refund path. |
| Mock payment accepted as real | Production gateway startup rejects `USE_MOCK_ADAPTER=true`; the mock remains available in development. The non-mock adapter has not been validated against authoritative production contracts. | Validate transaction authenticity, confirmations/finality, and replay behavior with Paxeer and LayerX before processing real funds. |
| Missing provider payout destination | Production provider registration requires a wallet and the gateway independently refuses to quote to its development fallback address whenever the live payment adapter is enabled. | Keep payout wallet ownership verification and change review in the provider onboarding process. |
| Provider endpoint SSRF and data exfiltration | Before a quote and again before forwarding, the gateway validates the URL and every DNS answer. Staging/production require HTTPS and globally routable addresses; production also requires an exact hostname allowlist. The socket connects to a captured address, and redirects are disabled. | Enforce outbound egress rules and verify ownership of allowlisted hosts. The gateway does not prove that an allowlisted public hostname belongs to the registered provider. |
| Webhook destination SSRF | The worker resolves each destination, rejects restricted addresses, pins the socket to the checked public IPs in staging/production, requires HTTPS, disables redirects, and bounds request/response size and time. | Enforce outbound egress controls and verify ownership of destinations; internal network policy remains an independent boundary. |
| Unauthenticated API flooding | API and gateway Redis limits start after API-key validation; invalid or unauthenticated requests are not limited by those application counters. | Apply network-level rate limits at the trusted edge to invalid and unauthenticated traffic. |
| Request/response resource abuse | Gateway rejects oversized inbound bodies, caps streamed provider responses and provider timeouts, validates and pins provider destinations, and limits authenticated keys through Redis in staging/production. It has no concurrency limit; edge limits are still needed for invalid credentials. | Add concurrency limits and enforce network-level egress and edge limits. |
| Control-plane oversized request bodies | The API rejects write bodies above a configurable 1 MiB default before route processing. | Keep the cap appropriate for batch payloads and configure request timeouts and edge limits for slow clients. |
| Tenant boundary weakness | Control-plane routes and gateway identity checks enforce organisation, project, and environment boundaries for their current paths. | Preserve these checks in new routes and add cross-tenant tests before release. |
| Existing API keys may lack new scopes | Scope grants are immutable and are not expanded when a new route scope is introduced. | Reprovision an administrator key through the bootstrap command, issue updated least-privilege keys, and revoke the older key. |
| Bootstrap key exposure | The bootstrap command creates a full-scope key and prints it once. | Run it only from a controlled environment, store the value in a secret manager, issue narrower keys, and revoke the bootstrap key. |
| Policy race | For daily/monthly budgets, the gateway locks the agent row before reading spend, includes active unexpired quote reservations, and consumes the reservation in the same transaction as the verified payment. PostgreSQL concurrency behavior still needs integration verification. | Verify simultaneous quote and proof submissions against PostgreSQL; keep budget reservation, payment, and nonce transitions atomic. |
| Approval lifecycle | The gateway persists a tenant-scoped request and requires `approvals:write` for decisions. Decisions are row-locked and bound to the original provider, service version, amount, recipient, and policy version; current budget and policy rules are rechecked before issuing a quote. A worker expires overdue requests every 30 seconds and records the state transition and audit event in one transaction. Decisions are attributed to API keys, but separate-user identity and separation of duties are not enforced. | Use a dedicated approval key, add operator identity and role separation, and verify simultaneous expiration/decision/invoke transitions against PostgreSQL. |
| Receipt signature verification depends on a shared canonicalization contract | Receipt v1 normalizes route-score floats and timestamps, signs a SHA-256 digest with low-S ECDSA, and checks the stored hash and strict DER signature encoding. An independent Node.js verifier and a published signed vector are included. | Run the vector in CI; add trusted-key lookup, rotation, and revocation before external verification or real-fund use. |
| External payment and execution are not atomic | Payment is marked verified before the provider call; provider failure does not refund or dispute it. The worker reads LayerX transaction, settlement, and batch evidence and checks the claimed L1 receipt, but it deliberately does not advance payment states. The endpoint contract, commitment event, and relationship between batch contents and the on-chain commitment still require validation with the network operator. | Define compensation and dispute procedures; validate the adapter contract with authoritative LayerX/Paxeer services and staging records before handling real funds. |

## Existing protective controls

- Control-plane API keys are hashed at rest; raw keys are returned once.
- API-key hashes are compared with a constant-time comparison.
- Missing, invalid, expired, and malformed API keys use one generic error.
- Every control-plane resource route enforces a resource/action grant and
  checks organisation, project, and environment tenant boundaries.
- API-key hashes are compared in constant time, even when their short lookup
  prefixes collide.
- Gateway keys require `gateway:invoke`, and the selected agent must belong to
  the key's active tenant. Completion requests are bound to the exact agent.
- Redis applies a shared fixed-window request limit per authenticated gateway
  key in staging and production; the gateway fails closed if Redis is unavailable.
- Production gateway startup rejects mock payments, non-HTTPS upstream URLs,
  non-target chain IDs, and local receipt-signing defaults.
- API key listing hides raw values and hashes; revocation disables the key.
- Redis enforces a shared fixed-window request limit for each authenticated
  API key in staging and production; the API fails closed if Redis is unavailable.
- The control-plane API caps write-request bodies before route processing.
- The gateway caps inbound invocation bodies and streamed provider responses,
  bounds provider connection and total request timeouts, rejects unsafe
  provider destinations before issuing quotes, pins checked IPs for forwarding,
  and disables redirects.
- Successful control-plane mutations write tenant-scoped audit records in the
  same database transaction and expose them through an `audit-logs:read` route.
- Error responses include request IDs, while unexpected details stay in logs.
- Payment requirements bind quote ID, request hash, amount, recipient, chain,
  nonce, and expiry. The local verifier fails closed on mismatch.
- Quote nonces are claimed with a conditional database update in the same
  transaction as the verified payment, and that payment is committed before
  the provider request starts.
- Daily and monthly policy checks serialize by agent and include active quote
  reservations; proof acceptance locks that same agent row and converts the
  reservation into recorded spend in one transaction.
- Control-plane error responses do not expose unhandled exception details.
- Monetary amounts use integers in atomic units rather than floating point.

These controls reduce specific risks but do not make the system production
ready while the gaps above remain.

Audit entries are stored in the same PostgreSQL database as the resources they
describe. They are not tamper-evident against a database administrator, and
retention or external archival is not configured.

## Additional threats to address

### Replay and idempotency

The gateway claims each quote nonce with an atomic database update before
recording the payment; duplicate proof submissions receive HTTP 409. The
verified payment and consumed nonce are committed before provider dispatch.
Quote intake takes a transaction advisory lock per agent/idempotency key and
returns the stored quote or state for same-request retries. It rejects key reuse
with a different payload. Successful calls store the bounded provider result
alongside the signed receipt; a replay returns both without forwarding to the
provider again. Results may contain sensitive provider data, so access control,
retention, and backup protections apply. Requests completed before migration
`0010` have no saved result and cannot replay the full response. The gateway
still does not recover every in-progress call. Verify the locking and replay
contract with concurrent PostgreSQL submissions before release.

### Webhook forgery and destination abuse

Webhook secrets have a stored SHA-256 digest and authenticated-encrypted copy;
production uses a dedicated encryption key. Hash-only legacy endpoints are
disabled by migration `0002`. Supported API changes are written to the
transactional outbox with their database changes and fanned into durable
delivery rows. The worker signs requests with HMAC-SHA256, pins resolved IPs,
does not follow redirects, and retries transient failures with a bounded lease
and backoff. Delivery is at least once; subscribers must deduplicate by delivery
ID. Preserve egress restrictions, secret redaction, and timestamp checks at the
receiver.

### Sensitive data in logs and receipts

Request arguments, completed provider results, and raw payment proof are
persisted. Define field-level redaction and retention rules. Do not log bearer
keys, private keys, full payment proofs, or sensitive provider payloads. A
signed receipt can still contain sensitive identifiers, so access control
remains necessary.

### Dependency and supply-chain risk

Pin and scan dependencies, protect CI secrets, review generated lockfile
changes, and sign release artifacts before distributing code that can
authorize agent spending.

## Minimum production gate

Do not process real funds until all high-risk gaps have owners and verified
controls. At minimum:

1. Add per-agent gateway credentials if project-wide keys are too broad, and
   verify tenant scoping across gateway, worker, and control-plane paths.
2. Validate the non-mock adapter against authoritative network APIs before
   enabling real payments.
3. Add provider hostname allowlists, outbound egress rules, gateway concurrency
   limits, and edge rate limits. Body, response, and provider timeout caps are
   now configurable.
4. Verify budget reservation, nonce consumption, and full result replay with
   concurrent PostgreSQL submissions; recover calls left in progress after a
   gateway interruption.
5. Complete payment failure, refund/dispute, and settlement reconciliation;
   verify approval expiration races against PostgreSQL.
6. Run the published receipt canonicalization and signature vector through the
   independent Node.js verifier in CI; define trusted-key rotation and
   revocation before exposing verification to customers.
7. Complete a security review and incident response exercise.
