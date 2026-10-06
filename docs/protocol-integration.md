# Paxeer and LayerX protocol integration

PaxRelay keeps network-specific code behind `packages/paxeer-adapter`. The
published LayerX 402LXP HTTP contract is version 2. The previous PaxRelay
payment prototype used a different JSON quote plus guessed REST lookups; those
lookups are not evidence of a LayerX payment.

## Published 402LXP HTTP v2 contract

The official [402LXP HTTP per-call payment contract](https://www.paxeer.app/features/layerx-402lxp-http-payments)
defines this exchange:

1. The resource returns HTTP `402` and a base64 JSON envelope in
   `PAYMENT-REQUIRED`.
2. The envelope has `x402Version: 2`, a resource URL, and 1–32 payment
   alternatives. Each alternative names its scheme, `layerx:<id>` network,
   32-byte asset, atomic amount, 32-byte `payTo` recipient, timeout, and any
   LayerX commitment requirement.
3. The buyer selects an offer without changing it and sends a
   `PAYMENT-SIGNATURE` containing canonical LayerX receipt evidence or an
   allowed signed grant draw.
4. The seller verifies evidence at the required commitment level. A successful
   response carries `PAYMENT-RESPONSE` with settlement reference
   `lxp:<receipt_digest>`.

For the reproducible exact-payment demo, the commitment is `executed`. The
other documented levels are `batched` and `finalised` (the spelling
`finalized` is invalid). An HTTP success, queue acknowledgement, or submitted
activity ID is not payment evidence. The transport is LayerX JSON-RPC at
`POST /rpc`; the merchant settlement route is `POST /v1/settle`.

## What this repository validates today

`packages/paxeer-adapter/src/paxrelay_paxeer/x402_http.py` strictly decodes and
checks a `PAYMENT-REQUIRED` header: protocol version, envelope size, duplicate
JSON keys, resource URL, alternative count, scheme, network, address lengths,
canonical amount, timeout, and commitment value. The command-line probe sends
one request without payment and checks the returned offer:

```powershell
uv run --package paxrelay-paxeer python -m paxrelay_paxeer.offer_cli `
  https://provider.example/v1/search `
  --method POST `
  --json-body '{"query":"PaxRelay"}'
```

The probe never sends `PAYMENT-SIGNATURE` and never pays. Its success means
only that the provider's offer matches the checked envelope shape; it does not
verify a receipt, settle funds, or qualify an endpoint for production.

## Current implementation boundary

The gateway currently returns a PaxRelay-specific JSON `402` body. That body
is not the published HTTP v2 `PAYMENT-REQUIRED` header. The SDK buyer flow,
LayerX receipt resolution and signature verification, payment response
handling, and official JSON-RPC read methods are not integrated yet.

Accordingly:

- `OfficialPaxeerAdapter.create_payment_requirement` retains the legacy
  PaxRelay quote format for compatibility; it is not an official v2 offer.
- `OfficialPaxeerAdapter.verify_payment` now fails closed with
  `layerx_402lxp_v2_verifier_not_integrated`.
- The old undocumented `/transactions/{hash}` and `/batches/{id}` REST reads
  are disabled. They cannot authorize provider execution or reconciliation.
- The remaining wallet, registry, and settlement REST surfaces in the partial
  adapter also need contract confirmation before they can be treated as
  authoritative network data.
- Use `USE_MOCK_ADAPTER=true` only for the clearly labelled local simulation.
  A mock response is not a testnet or real payment.

The official Python SDK is documented in the upstream Paxeer X repository's
[`agent/sdk/python` directory](https://github.com/Sidiora-Labs/Paxeer-X-Network/tree/main/agent/sdk/python)
and [payment guide](https://github.com/Sidiora-Labs/Paxeer-X-Network/blob/main/docs/wiki/PaymentsQuickstart.md).
The integration still needs a pinned SDK release, configured
LayerX test-network RPC and credentials, a test payer with funds, an exact
payment offer, receipt resolution, signed receipt verification, replay-safe
settlement, and an end-to-end staging run. Do not set the adapter to a live
environment and describe it as payment-enabled before those checks pass.

## Paxeer L1 settlement

LayerX executed receipts and Paxeer L1 commitments are separate evidence. The
existing reconciliation verifier checks the configured Paxeer JSON-RPC
receipt for a successful transaction, canonical block, confirmation depth,
configured contract address, and commitment event topic. This only proves the
configured event was emitted. It does not independently decode an arbitrary
contract ABI or recompute the LayerX batch commitment.

Production values for `PAXEER_L1_SETTLEMENT_CONTRACT_ADDRESS`,
`PAXEER_L1_COMMITMENT_EVENT_TOPIC`, and
`PAXEER_L1_CONFIRMATION_BLOCKS` must come from the operator and the deployed
contract. A LayerX activity can be `executed` without an L1 settlement; do not
present an execution receipt as an L1-finalized payment.

## Adapter responsibilities

| Interface | Responsibility |
| --- | --- |
| `WalletAdapter` | Read wallet state and verify a wallet session. |
| `PaymentAdapter` | Build the internal quote and verify payment evidence. |
| `RegistryAdapter` | Publish/search services and read provider history. |
| `SettlementAdapter` | Read payment settlement and verify configured L1 commitment evidence. |

Before a live adapter is qualified, its endpoint paths, authentication,
response schemas, signature and receipt checks, finality semantics, timeout,
retry, and idempotency behavior must be covered by upstream contract fixtures
and a controlled test-network transaction. Network reachability alone is not
contract validation.
