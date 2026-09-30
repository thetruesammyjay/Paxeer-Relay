# Paxeer and LayerX protocol integration

PaxRelay isolates network-specific work behind `packages/paxeer-adapter`.
Gateway and worker code should depend on the adapter interfaces rather than
constructing protocol clients directly.

## Adapter interfaces

The package defines four async protocols:

| Interface | Responsibilities |
| --- | --- |
| `WalletAdapter` | Read wallet and wallet policy, verify a session proof, read balance. |
| `PaymentAdapter` | Build a payment requirement, verify payment proof, read payment status. |
| `RegistryAdapter` | Publish a service, find services by capability, read provider history. |
| `SettlementAdapter` | Read settlement and batch records and verify an L1 commitment against a Paxeer JSON-RPC receipt. |

`MockPaxeerAdapter` and `OfficialPaxeerAdapter` implement these surfaces. The
gateway currently selects the mock adapter by default with
`use_mock_adapter=true`.

## Official adapter assumptions

The current official adapter is an HTTP client prototype. It assumes these
relative paths under the configured RPC/API base URLs:

| Operation | Assumed request |
| --- | --- |
| Wallet read | `GET /wallets/{address}` |
| Wallet policy read | `GET /wallets/{address}/policy` |
| Session proof check | `POST /sessions/verify` with `{"proof":"..."}` |
| Balance read | `GET /wallets/{address}/balance?currency=USDX` |
| Service publish | `POST /registry/services` |
| Service search | `GET /registry/services?capability=...` |
| Provider history | `GET /registry/providers/{provider_id}/history` |
| Payment status by local payment ID | No verified route is configured; the adapter returns `unknown`. Reconciliation uses the stored LayerX transaction hash instead. |
| LayerX transaction read | `GET /transactions/{transaction_hash}` under LayerX API URL |
| LayerX batch read | `GET /batches/{batch_id}` under LayerX API URL |
| Paxeer settlement record | `GET /settlement/{settlement_id}` under `PAXEER_SETTLEMENT_API_URL` |

These request shapes are code assumptions and have not been demonstrated
against authoritative production endpoints in this repository. Confirm the
official API paths, authentication, response schemas, finality semantics,
timeouts, and retry behavior before enabling live integration.

The official [Paxeer JSON-RPC reference](https://docs.paxeer.app/api-reference)
documents the standard EVM RPC surface. The [Paxeer and LayerX integration
guide](https://docs.paxeer.app/paxeer-vs-layerx/) directs applications to use a
LayerX receipt for the activity and a Paxeer transaction receipt for its
on-chain operation, with the environment's contract ABI and address. The HTTP
resource paths above are not established by those references.

## L1 receipt verification

The reconciliation worker does not accept `l1_anchored: true` or a matching
commitment returned by an HTTP endpoint as proof of anchoring. It checks the
settlement's claimed L1 transaction with the configured Paxeer JSON-RPC URL:

1. `eth_chainId` must match `PAXEER_CHAIN_ID`.
2. `eth_getTransactionReceipt` must return the claimed transaction hash, a
   successful status, and the claimed block number.
3. `eth_getBlockByNumber` must return the same canonical block hash as the
   receipt, and `eth_blockNumber` must show the configured confirmation depth.
4. The receipt must contain a log from the configured settlement contract with
   the configured event signature topic. The exact 32-byte commitment must
   appear as an indexed event topic or a 32-byte ABI data word.

Production requires `PAXEER_L1_SETTLEMENT_CONTRACT_ADDRESS`,
`PAXEER_L1_COMMITMENT_EVENT_TOPIC`, and
`PAXEER_L1_CONFIRMATION_BLOCKS`. Obtain these values and the finality policy
from the Paxeer operator. The verifier supports an event where the commitment
is emitted as a `bytes32` value; it does not decode arbitrary ABI layouts or
independently recompute a LayerX batch commitment. LayerX and Paxeer REST
resources remain assumed contracts and must be confirmed against authoritative
services. Batch IDs are opaque LayerX references, not EVM transaction hashes.
Until the configuration and response contract are confirmed, do not use
reconciliation as authorization to release funds.

## 402LXP requirement and proof checks

The adapter builds a version 1 requirement containing scheme `402LXP`, network
`paxeer`, chain ID 125, settlement layer `layerx`, currency USDX, decimals,
atomic amount, recipient, quote ID, request hash, expiry, and nonce.

Before adapter verification, the gateway compares proof claims to the stored
quote and rejects an expired quote or mismatched quote ID, request hash,
amount, recipient, nonce, chain ID, or scheme. The official adapter then
requires a 32-byte hexadecimal LayerX transaction hash and queries LayerX to
confirm amount, recipient, and quote ID (or memo). The proof must decode to a
JSON object. Amounts must be integers or decimal integer strings; malformed
claims and malformed LayerX JSON are rejected as failed verification.

The official code currently expects the submitted proof to be JSON containing
those fields. It does not implement wallet signing, transaction submission,
or client-side payment initiation. The agent or its wallet is responsible for
paying outside the gateway flow.

## Mock adapter and simulator

The mock adapter makes no network calls and returns fabricated wallet,
verification, transaction, registry, and settlement data. Its nonce replay
set is process-local. The separate `apps/simulator` service also fabricates
results and keeps its service registry in memory. These tools are suitable for
local flow demonstrations only.

## Integration checklist

Before an adapter can be considered production-ready:

1. Replace assumed endpoints with official, versioned API contracts.
2. Validate chain ID and network identity at startup.
3. Use authenticated TLS connections and bounded timeouts.
4. Parse amounts as integers and verify recipient, currency, quote, chain,
   nonce, expiry, and settlement destination from authoritative data.
5. Verify the gateway's atomic PostgreSQL nonce claim with concurrent
   submissions, then validate LayerX transaction replay semantics against the
   authoritative service.
6. Confirm the settlement event ABI, deployment address, confirmation depth,
   and exact relationship between LayerX batch contents and the committed
   value. Define what “verified”, LayerX-settled, and L1-anchored mean and how
   to transition among them.
7. Add adapter contract tests against a controlled simulator and a staging
   endpoint.
8. Fail closed when upstream proof or settlement data is missing or
   contradictory.

Do not switch `USE_MOCK_ADAPTER` off in production merely because the HTTP
adapter can reach a URL. A reachable endpoint does not confirm that its
contract or settlement semantics are correct.
