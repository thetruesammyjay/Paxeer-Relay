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

Receipt v1 uses the PaxRelay canonical JSON rules implemented in
`packages/receipts`:

1. Remove the top-level `signature`, `receipt_hash`, and `signing_key_id`
   fields. The key ID is used to select a trusted public key; it is not part
   of the receipt facts being hashed.
2. Sort object keys recursively by UTF-16 code units. Keys must be strings.
3. Encode UUIDs as lowercase, hyphenated strings.
4. Normalize `issued_at`, `execution.started_at`, and
   `execution.completed_at` to UTC ISO-8601 with six fractional digits and a
   `Z` suffix. Naive timestamps in existing records are treated as UTC.
5. Keep integers as exact base-10 JSON integer tokens. This includes atomic
   monetary amounts, even when they exceed JavaScript's safe-integer range.
   Encode finite floats as their shortest round-trip decimal, without
   exponent notation or trailing fractional zeroes. Negative zero becomes
   `0`; NaN and infinity are rejected. The routing score is signed as a JSON
   number, not a string.
6. Serialize compact UTF-8 JSON without extra whitespace, then compute SHA-256
   and represent the digest as `0x` plus 64 lowercase hexadecimal characters.

This is a PaxRelay-specific canonicalization profile, not RFC 8785. Verifiers
must preserve integer precision and apply the published rules exactly. The
cross-language input/output vector and a Node.js reference verifier are in
[`receipt-test-vectors.md`](receipt-test-vectors.md). Run the verifier with the
published fixture before changing the canonicalization contract.

## Signatures and verification

`LocalReceiptSigner` signs the 32-byte SHA-256 receipt digest using ECDSA with
SHA-256 pre-hashing. It supports secp256k1 and P-256 PEM keys. Signatures use
ASN.1 DER, are normalized to low-S form, and are returned as `0x`-prefixed
hex. The verifier requires the receipt's stored hash to match its recomputed
hash, checks any embedded signature against the supplied signature, validates
the DER encoding and low-S form, and verifies with a supported EC public key.

The gateway uses a generated development key when
`RECEIPT_SIGNING_PRIVATE_KEY` is absent; production configuration rejects that
fallback. The Node.js reference verifier is an independent implementation, but
the vector still needs to be run in CI. There is no KMS/HSM implementation or
public receipt-verification API in this checkout. Before processing real funds,
wire vector verification into CI and define trusted-key rotation and revocation.

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

## Verification boundary

`verify_receipt_signature` accepts a receipt, its signature, and one public
key. The caller must select that key using `signing_key_id` and apply any
rotation policy. A valid PaxRelay signature means PaxRelay signed these
recorded facts; it does not prove that the provider's content is correct.

`ReceiptKeyring` provides that key selection for Python consumers. Its version
1 JSON manifest contains public keys with `active`, `retired`, or `revoked`
status and an explicit `not_before` timestamp. Retired keys also require
`not_after`; they remain valid for receipts issued before that time. Revoked
keys are rejected for every receipt because compromise can make claimed issue
times untrustworthy. The keyring rejects overlapping active/retired validity
windows and duplicate key IDs. Distribute manifest updates through a controlled
configuration channel; the package does not fetch trust data from a remote
endpoint or expose a public key-management API.

Construct a keyring with `ReceiptKeyring.from_json(manifest_text)` and verify a
receipt with `keyring.verify(receipt_dict)`. The result is `(valid, reason)`.
`LocalReceiptSigner.public_key_pem` returns the public half of a configured
local signer for adding to the manifest; it never returns the private key.
Keep the active private key in the gateway's secret manager. For routine
rotation, publish the new public key with its activation time and retire the
old key at the same cutover time so existing receipts remain verifiable.
