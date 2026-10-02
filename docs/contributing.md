# Contributing

PaxRelay is pre-alpha and changes quickly. Before adding a feature, check the
current implementation notes in [Technical documentation](TECHNICAL.md) and
the status warnings in the root `README.md` and `PROJECT-STRUCTURE.md`.

## Local development

From the repository root, install dependencies and start local infrastructure:

```powershell
pnpm install
uv sync --all-packages
docker compose up -d postgres redis
```

Start the API from `apps/api`:

```powershell
cd apps/api
uv run uvicorn app.main:app --reload
```

Start the dashboard from `apps/web` in another terminal:

```powershell
cd apps/web
pnpm dev
```

The web dashboard still uses sample data on most pages. Do not assume a visible
screen is backed by an API route unless its hook or API request is connected.

## Change boundaries

- Keep domain rules and value types framework-independent in
  `packages/domain`.
- Keep persistence in `packages/db` repositories and models. Add an Alembic
  migration when the database schema changes.
- Keep Paxeer- and LayerX-specific HTTP behavior in
  `packages/paxeer-adapter`.
- Keep policy evaluation deterministic and provider routing explainable.
- Keep API request/response schemas separate from internal domain models.
- Keep browser data access behind `apps/web/lib/api-client.ts`; never connect a
  browser component directly to PostgreSQL.
- Update documentation when a route, state transition, adapter contract, or
  security boundary changes.

## Before proposing a change

1. Identify whether it changes a public HTTP schema, persisted record, state
   transition, security check, or only presentation.
2. Describe failure and retry behavior. Payment, provider execution, and
   settlement are separate states.
3. Keep monetary values in integer atomic units.
4. Preserve tenant scope on reads, writes, joins, and batch operations.
5. Mark placeholder or simulated behavior clearly in the UI and docs.
6. Add focused tests for changed behavior and record the exact commands run in
   the pull request description.

## Code style and verification

Use the package's existing conventions. Python code is configured for Ruff and
type checking at the repository root; the web app uses TypeScript and package
scripts defined in `apps/web/package.json`. Run relevant checks for code you
change before opening a pull request. Do not claim a test passed unless it was
run against the current change.

The receipt keyring, Python SDK verifier, and cross-language receipt vector are
checked by `.github/workflows/python.yml`. Run the same focused checks locally
from the repository root:

```powershell
uv sync --package paxrelay-receipts --extra test
uv run --package paxrelay-receipts --extra test pytest packages/receipts/tests
uv sync --package paxrelay --extra test
uv run --package paxrelay --extra test pytest packages/sdk-python/tests
node tools/verify-receipt.mjs docs/vectors/receipt-v1.json docs/vectors/receipt-v1-public.pem
```

## Pull requests

Each pull request should explain:

- the user or operational problem;
- what changed and which app/package owns the behavior;
- the verification performed;
- database migrations or environment changes;
- security and tenant-scope implications; and
- any incomplete behavior or follow-up work.

Keep changes focused. Avoid combining a visual redesign, protocol change, and
database migration unless they are required for the same user outcome.
