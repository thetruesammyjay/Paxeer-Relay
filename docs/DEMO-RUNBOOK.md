# One repeatable PaxRelay demo

This runbook provides one local end-to-end paid-request demonstration and a
separate read-only check of a real provider's 402LXP offer. The local payment
uses the mock adapter. It does not send funds and is not evidence that LayerX
settled a payment.

## Local simulated request

### 1. Start the local dependencies

From the repository root, install the workspace dependencies and start the
database and Redis:

```powershell
pnpm install
uv sync --all-packages
docker compose up -d postgres redis
```

Set the local `DATABASE_URL` in `packages/db/.env`, then apply migrations using
the repository's Alembic project:

For the Docker database in this repository, the local value is
`postgresql+asyncpg://postgres:postgres@localhost:5432/paxrelay`. Set the same
value in the repository-root `.env`, which the remaining commands below load.
The local Redis URL is `redis://localhost:6379/0`. Set `APP_ENV=development`
and `USE_MOCK_ADAPTER=true` in the root `.env` for this simulated flow.

```powershell
cd packages/db
uv run python -m alembic upgrade head
cd ../..
```

The API, gateway, and worker must use the same local database and Redis
settings. The simulator does not use either service. In the development
environment, set `USE_MOCK_ADAPTER=true`. Do not use this setting for a live
deployment.

### 2. Run the four services

Run each command from the repository root in a separate terminal so all
processes read the root `.env` file. See [local setup](deployment.md) for the
required development values.

```powershell
uv run --package paxrelay-api uvicorn app.main:app --reload --port 8000
```

```powershell
uv run --package paxrelay-gateway uvicorn paxrelay_gateway.main:app --reload --port 8001
```

```powershell
uv run --package paxrelay-simulator uvicorn paxrelay_simulator.main:app --reload --port 8100
```

```powershell
uv run --package paxrelay-worker python -m paxrelay_worker.main
```

To show the same project data in the dashboard, start the web app too:

```powershell
cd apps/web
pnpm dev
```

Check that the simulator responds:

```powershell
Invoke-RestMethod http://127.0.0.1:8100/health
```

### 3. Bootstrap a local project and API key

From the repository root, create a development organisation, project, and
bootstrap API key:

```powershell
uv run --package paxrelay-api python -m paxrelay_api.bootstrap `
  --organisation-name "Local Demo" `
  --organisation-slug local-demo `
  --project-name "Development" `
  --project-slug development `
  --environment development
```

Save the printed key for the next step. It is shown once and has the defined
development scopes needed by the demo script.

### 4. Provision and run one request

Return to the repository root in a new PowerShell terminal and set the local
API URL, gateway URL, simulator URL, and key for that terminal session:

```powershell
$env:PAXRELAY_API_URL = "http://127.0.0.1:8000"
$env:PAXRELAY_GATEWAY_URL = "http://127.0.0.1:8001"
$env:PAXRELAY_SIMULATOR_URL = "http://127.0.0.1:8100"
$env:PAXRELAY_API_KEY = "pk_replace_with_your_development_key"
uv run python tools/demo_mock_paid_request.py
```

The script creates a development agent, provider, service, and policy through
the API. It waits for the worker to record a passing provider health check,
sends a request, receives the gateway's simulated 402 quote, constructs a mock
proof, submits it, and prints the provider result and signed receipt. It
refuses non-loopback API, gateway, and simulator URLs. The final output
includes `"mode": "SIMULATED_ONLY"` and `"payment_submitted": false`.

The service calls `POST /demo-provider/search` on the local simulator. That
route returns deterministic sample data and does not access the internet. The
created agent, provider, service, and policy remain in the development project
so the configured dashboard can display the same API records.

Run the script again to create a fresh idempotency key and a new demonstration
request. The simulator returns fixed sample data and does not call the public
internet.

## Read-only live offer check

Once a provider gives you an HTTPS test-network resource URL, inspect its
402LXP offer without paying:

```powershell
uv run --package paxrelay-paxeer python -m paxrelay_paxeer.offer_cli `
  https://provider.example/v1/search `
  --method POST `
  --json-body '{"query":"PaxRelay"}'
```

This sends one unauthenticated request and checks the `PAYMENT-REQUIRED`
header. It never sends `PAYMENT-SIGNATURE`. A valid result confirms the
published v2 envelope shape only. Do not put credentials or private data in
`--json-body`.

## LayerX testnet paid request

This path sends a real testnet payment. It requires operator-provided test
credentials, a funded test payer, and an already-signed activity produced by
the payer's authorized signer. It does not use a private key stored by
PaxRelay.

### 1. Configure the gateway

Keep `USE_MOCK_ADAPTER=false` and `APP_ENV=staging`. In the private root `.env`,
set the staging Paxeer RPC URL, `PAXEER_NETWORK_ENVIRONMENT=testnet` (or the
operator's staging label), and these LayerX values:

```dotenv
LAYERX_NETWORK_ID=<test network id>
LAYERX_USDX_ASSET_ID=<registered USDX asset id as 64 hex characters>
LAYERX_SEQUENCER_PUBLIC_KEY=<test sequencer public key as 64 hex characters>
LAYERX_TESTNET_PAYER_ACCOUNT=<funded test payer account as 64 hex characters>
GATEWAY_PUBLIC_BASE_URL=https://<public gateway host>
```

Keep buyer credentials out of the gateway environment. Copy
`.layerx-buyer.env.example` to `.layerx-buyer.env`, set its operator RPC URL
and API key, and keep that file on the machine running the buyer helper. The
key must be authorized for `activity:write`.

```powershell
Copy-Item .layerx-buyer.env.example .layerx-buyer.env
```

Do not commit either private environment file. Apply migration
`0019_layerx_testnet_accounts`, register the staging provider with its LayerX
account ID, and publish a positive USDX per-call price. Confirm the RPC URL,
asset, payer, provider account, and sequencer key with the network operator
before submitting an activity.

Point `packages/db/.env` at the staging database, then apply the migrations:

```powershell
cd packages/db
uv run python -m alembic upgrade head
cd ../..
```

### 2. Request the exact offer

Set the staging capability, agent ID, and test API key for the request, then
ask the gateway for a quote. The helper requires the 402LXP header to contain
one valid exact-payment offer bound to that gateway:

```powershell
$gatewayBase = "https://<public gateway host>"
$env:PAXRELAY_AGENT_ID = "<staging agent UUID>"
$env:PAXRELAY_AGENT_API_KEY = "pk_<staging key>"
$invoke = @{
  capability = "<published capability>"
  idempotency_key = [guid]::NewGuid().ToString()
  arguments = @{}
}
$invoke | ConvertTo-Json -Depth 20 | Set-Content .\invoke.json -Encoding utf8
uv run --env-file .layerx-buyer.env --package paxrelay-paxeer python tools/request_layerx_offer.py `
  --gateway-base-url $gatewayBase `
  --agent-id $env:PAXRELAY_AGENT_ID `
  --request-file .\invoke.json `
  --output .\payment-required.txt
```

The quote is bound to the exact `/v1/invoke/{tool_call_id}` resource, provider
account, amount, asset, network, `executed` commitment, and configured test
payer. Use the offer values to prepare the signed activity.

### 3. Prepare and submit payment

Have the authorized test payer signer create a canonical signed activity that
matches the offer. Save its lowercase canonical hex to a file. First run the
buyer helper without `--submit`; it prints the offer facts and activity ID,
without contacting LayerX:

```powershell
uv run --env-file .layerx-buyer.env --package paxrelay-paxeer python tools/layerx_buyer_prepare.py `
  --payment-required-file .\payment-required.txt `
  --signed-activity-file .\signed-activity.hex
```

Check that the signer prepared the activity for the exact amount, asset,
recipient and payer printed by the preflight. When those facts are confirmed,
rerun with `--submit`. The official LayerX SDK buyer submits the activity,
waits for the `executed` receipt, verifies it against the pinned sequencer key,
and prints the `payment_signature` value. A `pending` result is not payment
proof; retain the same activity ID and resolve its receipt before retrying.

```powershell
$buyer = uv run --env-file .layerx-buyer.env --package paxrelay-paxeer python tools/layerx_buyer_prepare.py `
  --payment-required-file .\payment-required.txt `
  --signed-activity-file .\signed-activity.hex `
  --submit | ConvertFrom-Json
```

Send that exact proof to the resource URL shown during preflight. A successful
gateway response includes the signed PaxRelay execution receipt and the
standard `PAYMENT-RESPONSE` header:

```powershell
$offer = [System.Text.Encoding]::UTF8.GetString(
  [Convert]::FromBase64String((Get-Content .\payment-required.txt -Raw).Trim())
) | ConvertFrom-Json
$headers = @{
  Authorization = "Bearer $env:PAXRELAY_AGENT_API_KEY"
  "X-Agent-Id" = $env:PAXRELAY_AGENT_ID
  "PAYMENT-SIGNATURE" = $buyer.payment_signature
}
$result = Invoke-WebRequest `
  -Uri $offer.resource.url `
  -Method Post `
  -Headers $headers `
  -ContentType "application/json" `
  -Body "{}"
if ($result.StatusCode -ne 200) { throw "Paid invocation failed with HTTP $($result.StatusCode)" }
$result.Headers["PAYMENT-RESPONSE"]
$result.Content | ConvertFrom-Json
```

Keep the signed activity, receipt, and `PAYMENT-RESPONSE` together for the
staging record. If the gateway reports an already-recorded payment, it returns
the same verified settlement header and does not call the provider again. Do
not retry an ambiguous RPC submission with a newly signed activity; use the
same activity ID to check status and recover its receipt.

This workspace has not submitted the staging payment because no operator
testnet values, funded payer, signer-produced activity, or trusted testnet
sequencer key are configured here. The local simulator remains a separate,
payment-free demonstration. A successful LayerX payment does not prove Paxeer
L1 anchoring or qualify the separate reconciliation endpoints.

## Solana Devnet x402 paid request

This is a separate, opt-in test rail. It uses x402 V2 `exact` on Solana
Devnet, the Devnet USDC mint, and a facilitator configured by the operator.
Solana's official documentation identifies Devnet as
`solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1` and requires checking the facilitator's
`/supported` endpoint for the exact scheme and network before advertising an
offer ([Solana x402 guide](https://solana.com/docs/payments/agentic-payments/x402),
[facilitator guide](https://solana.com/docs/tools/x402-facilitator)). This
workspace does not verify that the default facilitator currently supports this
network; PaxRelay fails closed if the configured facilitator does not.

Devnet tokens have no production value. This rail is rejected in production.
For the demo only, PaxRelay maps each USDX atomic unit in the service price to
the same number of Devnet USDC atomic units. That is a test convention, not a
price conversion or a claim of parity. The buyer helper refuses offers above
10,000 atomic units (0.01 Devnet USDC).

### Configure and start the gateway

Apply migration `0020_solana_devnet_payment_rail` to the configured database.
In the gateway environment, set:

```dotenv
APP_ENV=development
USE_MOCK_ADAPTER=true
SOLANA_X402_ENABLED=true
SOLANA_X402_FACILITATOR_URL=https://x402.org/facilitator
SOLANA_X402_MAX_AMOUNT_ATOMIC=10000
SOLANA_DEVNET_RPC_URL=https://api.devnet.solana.com
GATEWAY_PUBLIC_BASE_URL=http://127.0.0.1:8001
```

The facilitator URL is configurable. Confirm it advertises `exact` for the
Devnet network before using it. When running from `apps/gateway` with the root
`.env` file, start the gateway with:

```powershell
uv run --env-file ../../.env uvicorn paxrelay_gateway.main:app --reload --port 8001
```

Register a provider with its **Solana Devnet wallet address** in the provider
dashboard. Ensure the provider has a published, active service, and the agent
has an active policy and `gateway:invoke` permission. The provider address is a
receiving wallet destination; registering it does not prove wallet ownership.

### Prepare a disposable buyer

Copy the buyer template and set a disposable Devnet keypair, active agent
credentials, gateway URL, and funded Devnet account. The account needs the
Devnet USDC required by the offer and SOL for any transaction fees not covered
by the facilitator.

```powershell
Copy-Item .solana-buyer.env.example .solana-buyer.env
```

`SOLANA_DEVNET_PRIVATE_KEY` accepts a base58 secret key or the one-line JSON
secret-key array produced by Solana CLI. Keep this local file private; never
reuse a mainnet keypair. The gateway enforces a maximum payment of `10000`
atomic units (0.01 Devnet USDC), and the helper applies the same limit before
signing.

From `apps/gateway`, run one paid request for a published capability:

```powershell
uv run --env-file ../../.solana-buyer.env python ../../tools/solana_devnet_paid_request.py `
  --capability "research.web-search" `
  --arguments-json '{"query":"PaxRelay Devnet demo"}'
```

The helper checks the challenge version, network, mint, amount cap, and exact
resource URL before it creates a signed payload. It retries the resource with
`PAYMENT-SIGNATURE`, then prints the signed PaxRelay receipt and
`PAYMENT-RESPONSE`. The gateway verifies and settles the transfer through the
configured facilitator before calling the provider. Save the printed
idempotency key. If the result is ambiguous, pass the same key with the same
capability and arguments; do not start a second paid request with a new key
until you have checked the first request's result.

This code path is implemented but has not been exercised with a funded Devnet
buyer or a facilitator that has been confirmed to support the configured
network. A successful Devnet payment is not production payment qualification
and does not change the pending LayerX operator validation.
