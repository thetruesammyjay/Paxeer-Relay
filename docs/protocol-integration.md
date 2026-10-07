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

## PaxRelay implementation

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

The gateway's live adapter now builds an official v2 exact-payment offer and
returns it in both the JSON body and the base64 `PAYMENT-REQUIRED` response
header. It supports `exact` offers with `executed` commitment and USDX only.
The standard `PAYMENT-SIGNATURE` header is accepted on a retry to
`POST /v1/invoke`; the existing `POST /v1/invoke/{tool_call_id}` route also
accepts the header or a JSON `proof` field. A successful invocation includes a
`PAYMENT-RESPONSE` header with the verified receipt and `lxp:` settlement
reference.

The official LayerX Python SDK is pinned to source commit
`e9e8b0e06da53f42c6e8607242941f214c508b59` from its repository's
[`agent/sdk/python` directory](https://github.com/Sidiora-Labs/Paxeer-X-Network/tree/e9e8b0e06da53f42c6e8607242941f214c508b59/agent/sdk/python).
PaxRelay uses its `BuyerMiddleware`, HTTP envelope codec, and
`verify_payment_receipt` verifier. The upstream distribution is installed from
the pinned source rather than PyPI's unrelated package with the same name.
The SDK does not expose a public decoder for the receipt fields needed to
construct `AuthorizedReceiptBatch`; the integration uses the SDK's private
decoder and therefore pins that exact source commit.

Receipt verification uses the operator-pinned sequencer public key and binds
the signed receipt to the quoted amount, USDX asset, provider's LayerX account,
configured network, resource URL, and (in staging) the configured test payer.
It also requires the receipt to be a successful Asset `SEND` operation, so a
matching transfer produced by another module cannot satisfy the offer.
The exact payment nonce remains single-use in PaxRelay's database. A verified
payment is committed before any provider request is made.

`tools/layerx_buyer_prepare.py` creates the buyer header with the upstream
`BuyerMiddleware`. It reads the operator's test RPC endpoint and API key from
environment variables and accepts a canonical activity that has already been
signed by the payer's authority. It never reads a private key. It prints a
preflight summary by default; adding `--submit` sends the activity and asks the
SDK to verify the resulting receipt before printing `payment_signature`.

This code integration is ready for controlled staging configuration, but no
funded testnet transaction has been run from this workspace: the local
environment does not contain LayerX test credentials, a funded payer, a signed
test activity, or a verified testnet sequencer key. The following non-mock
surfaces remain separate operator contracts and are not evidence for this
402LXP path: wallet REST, registry REST, L1 settlement REST, and LayerX batch
reconciliation reads. Keep real-value production payment release dependent on
network-operator validation and a successful staging run.

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

## Solana Devnet x402

The gateway has a separate experimental x402 V2 `exact` adapter for Solana
Devnet. It emits the standard `PAYMENT-REQUIRED` header, checks the buyer's
`PAYMENT-SIGNATURE` against the persisted quote and exact resource URL, asks the
configured facilitator to verify and settle, and includes its result in
`PAYMENT-RESPONSE`. The selected Solana destination is stored on the provider
as `solana_devnet_address`; settlement signature, network, and asset are kept
in payment and receipt records.

The only accepted network is
`solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1`, with Devnet USDC mint
`4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU`. A gateway instance checks the
facilitator's `/supported` response before advertising the rail. A facilitator
must support the exact scheme and network, and its replay, fee-payer, and
confirmation behavior must be reviewed before use. The rail is off by default
and startup rejects it in production. The gateway and buyer helper enforce a
0.01-USDC Devnet spending cap; this is a demo safeguard, not a production
agent signing policy.

The gateway currently stores policy spend in USDX atomic units. For this
Devnet-only path, it uses the same six-decimal atomic amount against test USDC.
This is only a demo denomination mapping. It is not a production exchange rate,
does not imply USDX and USDC are redeemable at parity, and must not be enabled
for real-value payment accounting.

No funded Devnet transfer has been run in this workspace. See the
[Solana Devnet paid request procedure](DEMO-RUNBOOK.md#solana-devnet-x402-paid-request)
for operator configuration and its current validation limits.

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
