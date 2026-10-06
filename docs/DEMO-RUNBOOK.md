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

## What remains before a live paid demo

The gateway still emits its legacy JSON challenge, and the official buyer SDK
and LayerX receipt verification are not connected to the invocation path. A
live test therefore cannot be completed by setting `USE_MOCK_ADAPTER=false`:
the live verifier intentionally fails closed. The live path needs all of the
following before a paid request can be claimed:

1. Pin and integrate the official LayerX Python SDK's HTTP buyer middleware.
2. Bind the service offer and payment receipt to the requested resource,
   amount, asset, recipient, network, and required `executed` commitment.
3. Verify canonical receipt bytes and the sequencer signature using the
   official trust inputs; persist idempotency and settlement state before
   invoking the provider.
4. Configure operator-issued test-network RPC credentials and a funded test
   payer, then run the complete request, receipt, replay, and reconciliation
   flow against the upstream test network.

An offer probe is not a paid-request demo, and a local simulated request must
be labelled as simulated in screenshots and presentations.
