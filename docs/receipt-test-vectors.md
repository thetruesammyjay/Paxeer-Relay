# Receipt v1 test vector

This vector fixes the receipt canonicalization and ECDSA verification format.
The example key is public test material and must never be used to sign real
receipts.

## Input receipt

```json
{
  "id": "11111111-1111-4111-8111-111111111111",
  "version": "1",
  "tool_call_id": "22222222-2222-4222-8222-222222222222",
  "agent_id": "33333333-3333-4333-8333-333333333333",
  "provider_id": "44444444-4444-4444-8444-444444444444",
  "service_id": "55555555-5555-4555-8555-555555555555",
  "service_version": "1.0.0",
  "capability": "research.web-search",
  "request_hash": "0x1111111111111111111111111111111111111111111111111111111111111111",
  "response_hash": "0x2222222222222222222222222222222222222222222222222222222222222222",
  "payment": {
    "scheme": "402LXP",
    "currency": "USDX",
    "amount": {
      "amount_atomic": 9007199254740993,
      "currency": "USDX",
      "decimals": 6
    },
    "payment_id": "66666666-6666-4666-8666-666666666666",
    "layerx_transaction": null,
    "l1_settlement": null
  },
  "execution": {
    "started_at": "2026-10-01T12:00:00+02:00",
    "completed_at": "2026-10-01T12:00:00.125000+02:00",
    "latency_ms": 125,
    "status": "succeeded"
  },
  "routing": {
    "route_id": "77777777-7777-4777-8777-777777777777",
    "strategy": "balanced",
    "score": 0.725
  },
  "issued_at": "2026-10-01T12:00:00+02:00",
  "receipt_hash": "0x72add308d66191144b197068241990fce15e8a627c386b0da9c70c2db9fa3df7",
  "signature": "0x304402206dbe6d421d08846ea478c4acaa14e4237fd0558a41c848a47b1cfdf63778c2c6022073e76dc20a24170970e67f2576a1fb078c8170b059fd064d99c94bbdb9e880b0",
  "signing_key_id": "vector-only-key"
}
```

## Expected canonical bytes

The following is one UTF-8 line with no trailing newline. The signature,
receipt hash, and key ID are omitted. The large `amount_atomic` value remains
an exact integer; implementations must not parse it through an imprecise
floating-point number type.

```text
{"agent_id":"33333333-3333-4333-8333-333333333333","capability":"research.web-search","execution":{"completed_at":"2026-10-01T10:00:00.125000Z","latency_ms":125,"started_at":"2026-10-01T10:00:00.000000Z","status":"succeeded"},"id":"11111111-1111-4111-8111-111111111111","issued_at":"2026-10-01T10:00:00.000000Z","payment":{"amount":{"amount_atomic":9007199254740993,"currency":"USDX","decimals":6},"currency":"USDX","l1_settlement":null,"layerx_transaction":null,"payment_id":"66666666-6666-4666-8666-666666666666","scheme":"402LXP"},"provider_id":"44444444-4444-4444-8444-444444444444","request_hash":"0x1111111111111111111111111111111111111111111111111111111111111111","response_hash":"0x2222222222222222222222222222222222222222222222222222222222222222","routing":{"route_id":"77777777-7777-4777-8777-777777777777","score":0.725,"strategy":"balanced"},"service_id":"55555555-5555-4555-8555-555555555555","service_version":"1.0.0","tool_call_id":"22222222-2222-4222-8222-222222222222","version":"1"}
```

## Expected digest and signature

```text
SHA-256: 0x72add308d66191144b197068241990fce15e8a627c386b0da9c70c2db9fa3df7
Signature: 0x304402206dbe6d421d08846ea478c4acaa14e4237fd0558a41c848a47b1cfdf63778c2c6022073e76dc20a24170970e67f2576a1fb078c8170b059fd064d99c94bbdb9e880b0
Algorithm: ECDSA secp256k1, SHA-256 pre-hash, ASN.1 DER, low-S
```

Public key in PEM SubjectPublicKeyInfo format:

```text
-----BEGIN PUBLIC KEY-----
MFYwEAYHKoZIzj0CAQYFK4EEAAoDQgAEeb5mfvncu6xVoGKVzocLBwKb/NstzijZ
WfKBWxb4F5hIOtp3JqPEZV2k+/wOEQio/Re0SKaFVBmcR9CP+xDUuA==
-----END PUBLIC KEY-----
```

A verifier should recompute the canonical bytes and digest, compare the digest
with `receipt_hash`, then accept the signature only when it matches the
provided public key and is valid low-S DER. Changing the route score, timestamp,
amount, or any other signed field must change the digest.

## Run the Node.js reference verifier

The repository includes an independent JavaScript verifier that uses Node's
built-in cryptography and no additional package dependencies. The fixture files
are `docs/vectors/receipt-v1.json` and
`docs/vectors/receipt-v1-public.pem`. From the repository root, run:

```powershell
node tools/verify-receipt.mjs docs/vectors/receipt-v1.json docs/vectors/receipt-v1-public.pem
```

The command checks the canonical hash, trusted EC public key, strict DER and
low-S signature form, and ECDSA signature. It prints the canonical bytes so
they can be compared with the expected line above. It requires a Node.js
runtime whose `JSON.parse` reviver provides the original numeric token as
`context.source`; otherwise it rejects unsafe integer values rather than
silently rounding them. The example key is public test material only.
