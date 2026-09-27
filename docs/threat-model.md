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
| Agent impersonation | Gateway trusts `X-Agent-Id`; no API-key or session-proof authentication is connected. | Authenticate callers cryptographically and bind each credential to an agent and tenant. |
| Cross-agent call completion | The completion route resolves an agent but the invoke service does not compare that agent with the stored tool call's `agent_id`. | Verify call ownership and tenant scope before loading its quote or accepting proof. |
| Mock payment accepted as real | Gateway `use_mock_adapter` defaults to true; mock adapter fabricates transaction results. | Refuse production startup in mock mode and use authoritative transaction verification. |
| Provider endpoint SSRF | A stored service-version endpoint is POSTed to directly; there is no host/IP allowlist or private-network block in the forwarder. | Validate scheme, DNS result, redirects, and destination IP; block loopback, link-local, and private ranges unless explicitly allowed. |
| Request/response resource abuse | Gateway size-limit settings exist, but `forward_request` does not enforce them. | Enforce streaming byte limits, timeouts, concurrency limits, and request validation. |
| Tenant boundary weakness | API list routes often filter organisation and project, but some resource gets check only organisation. | Enforce organisation + project on every read/write and relationship lookup; add cross-tenant tests. |
| API key scopes are not enforced | Keys store a `scopes` string, but verification checks hash, active state, and expiry only. | Parse and enforce scopes per route, or do not present scopes as a security control. |
| No API-key bootstrap or revoke route | Creating a key requires an existing authenticated key; there is no key-revocation route. | Implement secure one-time provisioning and revocation before external use. |
| Policy race | Gateway reads current spend, evaluates a budget, then processes a payment; concurrent requests can evaluate against the same total. | Reserve budget atomically or serialize enforcement per agent/policy. |
| Approval path incomplete | `require_approval` returns 202 and an explanation, but no durable approval request/action is created by the gateway path. | Persist requests, require an authenticated approver, and bind the decision to a quote and expiry. |
| Receipt signature implementation incomplete | Canonicalization rejects route-score floats; signer/verifier have ECDSA and prefix-parsing issues. | Correct and independently verify the canonicalization/signature contract before relying on receipts. |
| External payment and execution are not atomic | Payment is marked verified before the provider call; provider failure does not refund or dispute it. | Define compensation, dispute, and reconciliation procedures and persist every transition. |

## Existing protective controls

- Control-plane API keys are hashed at rest; raw keys are returned once.
- API-key hashes are compared with a constant-time comparison.
- Missing and invalid API keys use generic errors to reduce credential probing.
- The API scopes many list routes to a tenant context and scopes receipts and
  analytics through the owning tool call.
- Payment requirements bind quote ID, request hash, amount, recipient, chain,
  nonce, and expiry. The local verifier fails closed on mismatch.
- Control-plane error responses do not expose unhandled exception details.
- Monetary amounts use integers in atomic units rather than floating point.

These controls reduce specific risks but do not make the system production
ready while the gaps above remain.

## Additional threats to address

### Replay and idempotency

The gateway returns a replay response for an already delivered idempotency key,
but it does not replay the full stored result and does not fully resolve
in-progress or failed calls. Persist nonce consumption atomically and make
idempotency-key behavior explicit for every terminal state.

### Webhook forgery and destination abuse

Webhook secrets are hashed when endpoints are registered, but the delivery
worker is not implemented. Before outbound delivery exists, protect against
server-side request forgery, DNS rebinding, oversized payloads, replayed
signatures, and secret leakage in logs.

### Sensitive data in logs and receipts

Request arguments and raw payment proof are persisted. Define field-level
redaction and retention rules. Do not log bearer keys, private keys, full
payment proofs, or sensitive provider payloads. A signed receipt can still
contain sensitive identifiers, so access control remains necessary.

### Dependency and supply-chain risk

Pin and scan dependencies, protect CI secrets, review generated lockfile
changes, and sign release artifacts before distributing code that can
authorize agent spending.

## Minimum production gate

Do not process real funds until all high-risk gaps have owners and verified
controls. At minimum:

1. Replace `X-Agent-Id` trust and enforce per-route authentication/authorisation.
2. Fix cross-agent completion and complete project-level tenant checks.
3. Disable mock mode at production startup and validate the official adapter
   against authoritative network APIs.
4. Restrict provider destinations and enforce body, response, timeout, and
   concurrency limits.
5. Make budget reservation, idempotency, and nonce use atomic under
   concurrency.
6. Complete payment failure, refund/dispute, settlement reconciliation, and
   approval workflows.
7. Correct receipt canonicalization and signature verification and publish
   test vectors.
8. Complete a security review and incident response exercise.
