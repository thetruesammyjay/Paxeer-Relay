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
| `SettlementAdapter` | Read settlement and batch records and verify an L1 commitment. |

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
| LayerX transaction read | `GET /transactions/{transaction_hash}` under LayerX API URL |
| LayerX batch read | `GET /batches/{batch_id}` under LayerX API URL |
| Settlement read | `GET /settlement/{settlement_id}` under RPC URL |
| L1 batch read | `GET /batch/{batch_id}` under RPC URL |

These request shapes are code assumptions and have not been demonstrated
against authoritative production endpoints in this repository. Confirm the
official API paths, authentication, response schemas, finality semantics,
timeouts, and retry behavior before enabling live integration.

## 402LXP requirement and proof checks

The adapter builds a version 1 requirement containing scheme `402LXP`, network
`paxeer`, chain ID 125, settlement layer `layerx`, currency USDX, decimals,
atomic amount, recipient, quote ID, request hash, expiry, and nonce.

Before adapter verification, the gateway compares proof claims to the stored
quote and rejects an expired quote or mismatched quote ID, request hash,
amount, recipient, nonce, chain ID, or scheme. The official adapter then
requires a LayerX transaction hash and queries LayerX to confirm amount,
recipient, and quote ID (or memo).

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
5. Make nonce consumption atomic and durable under concurrent submissions.
6. Define what “verified”, LayerX-settled, and L1-anchored mean and how to
   transition among them.
7. Add adapter contract tests against a controlled simulator and a staging
   endpoint.
8. Fail closed when upstream proof or settlement data is missing or
   contradictory.

Do not switch `USE_MOCK_ADAPTER` off in production merely because the HTTP
adapter can reach a URL. A reachable endpoint does not confirm that its
contract or settlement semantics are correct.
