# Execution receipts

An execution receipt records the payment, route, and provider execution that
PaxRelay observed for one tool call. It is evidence for troubleshooting and
audit. It does not prove that the provider's response is truthful, correct, or
useful, and it does not by itself prove final settlement on Paxeer L1.

## Receipt contents

The domain receipt (`ExecutionReceipt`) includes:

- receipt version and IDs for the tool call, agent, provider, service, and
  service version;
- capability and hashes of the canonical request and raw provider response;
- payment scheme, currency, atomic amount, payment ID, and optional LayerX/L1
  references;
- execution start/end times, latency, and execution status;
- routing ID, strategy, and score;
- issue time, receipt hash, signature, and signing key ID.

The gateway issues a receipt after a provider returns a 2xx response. It hashes
the canonical argument JSON for `request_hash` and the response bytes for
`response_hash`. Non-2xx provider results and transport failures are stored as
execution failures but do not receive a successful-delivery receipt in the
current invoke path.

## Canonical hashing

Before hashing, the receipt package:

1. Removes `signature`, `receipt_hash`, and `signing_key_id`.
2. Sorts object keys recursively.
3. Encodes timestamps as UTC ISO-8601 strings and UUIDs as strings.
4. Rejects floating-point values.
5. Serialises compact UTF-8 JSON without extra whitespace.
6. Computes a SHA-256 digest, represented as `0x`-prefixed lowercase hex.

Amounts remain integer atomic values. Receipt `score` is a float in the domain
schema, so the current canonicalizer's blanket rejection of floats needs to be
resolved before route scores can be signed reliably.

## Signatures and verification

`LocalReceiptSigner` is intended to sign the receipt hash using an ECDSA key
and attach a `signing_key_id`. The gateway uses a generated development key
when `RECEIPT_SIGNING_PRIVATE_KEY` is absent; that fallback must not be used as
a production identity. There is no KMS/HSM implementation in this checkout.

The current signer and verifier code has unresolved cryptography issues: the
pre-hashed ECDSA algorithm is constructed incorrectly, and signature hex
prefix parsing uses `lstrip` instead of removing only the `0x` prefix. The
canonicalizer also rejects the floating-point route score. Treat signatures as
an unfinished implementation until these issues are corrected and verification
is exercised across independent implementations.

No public receipt-verification API is currently exposed. The control-plane
`GET /v1/receipts` lists tenant receipts; clients must not treat its response
alone as cryptographic verification.

## Persistence and limits

`execution_receipts` stores canonical receipt JSON, receipt hash, signature,
key ID, and issue time. The receipt table links to `tool_calls` for tenant
scoping. The current API returns a flattened receipt summary; the gateway's
direct invocation result contains the nested domain receipt.

The repository has no implemented S3/R2 receipt archive and no on-chain receipt
anchoring. LayerX transaction and batch IDs are references observed during
payment verification, not receipt anchors.

## Verification contract to complete

A future verifier should accept the receipt and a trusted public key selected
by `signing_key_id`, recompute canonical bytes and hash, check the supplied
hash, validate the signature, and report each check separately. Keep the
claimed provider output outside the trust assertion: a valid PaxRelay signature
means PaxRelay signed these recorded facts, not that the provider's content is
correct.
