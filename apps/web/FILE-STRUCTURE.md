# PaxRelay web dashboard file structure

This guide maps the Next.js application in `apps/web`: URL routes, the three
dashboard workspaces, shared interface code, icon packages, and the browser-to-
API boundary.

In this document, **Current** means the file or route exists in the checkout.
**Live** means the page reads or changes records from the selected API project.
**Preview** means the product behavior is still presentation-only. **Planned**
means the route or workflow does not exist yet.

## Dashboard workspaces

The app contains three distinct workspaces. The route shell chooses its
navigation from the current URL.

| Workspace | Route | Purpose | Data scope |
| --- | --- | --- | --- |
| PaxRelay workspace | `/dashboard` | Project requests, spend, service health, and approvals | Project and environment verified from the signed-in member's active role |
| Admin dashboard | `/admin` | Project providers, services, requests, approvals, and settlement review | Tenant-scoped to the selected project; no cross-customer directory exists |
| Creator dashboard | `/creator` | Project services, requests, spend, and receipts | Project-scoped; individual creator ownership is not yet exposed by the API |

`/dashboard`, `/admin`, and `/creator` load live API data and refresh every 30 seconds. They show loading, empty, permission, partial-data, and API-error states instead of sample metrics. In staging and production, Auth.js uses OIDC sign-in and the API verifies project role access on every request. Admin data is scoped to the selected project, not the whole PaxRelay platform. Creator data is also project-scoped because the API does not yet expose per-creator ownership or authorization. API-key entry remains a development-only workflow. The PaxRelay workspace keeps its existing resource routes, such as `/agents`, `/policies`, and `/transactions`.

## Current application tree

```text
apps/web/
├── app/
│   ├── (auth)/
│   │   ├── layout.tsx                 # Public sign-in route-group layout
│   │   └── sign-in/page.tsx           # Company OIDC sign-in entry point
│   ├── admin/
│   │   ├── page.tsx                   # Live tenant-scoped production operations dashboard
│   │   └── settlements/page.tsx       # Read-only settlement review route
│   ├── agents/page.tsx                # Live tenant agent directory
│   ├── analytics/page.tsx             # Spend and capability analytics
│   ├── api/
│   │   └── health/route.ts            # Next.js process health response
│   ├── approvals/page.tsx             # Live approval queue and decisions
│   ├── creator/
│   │   └── page.tsx                   # Live project-scoped provider operations dashboard
│   ├── dashboard/page.tsx             # Live production project overview
│   ├── for-providers/page.tsx         # Public service-provider introduction
│   ├── for-teams/page.tsx             # Public agent-operator introduction
│   ├── how-it-works/page.tsx          # Public request lifecycle explanation
│   ├── page.tsx                       # Public product landing page
│   ├── policies/page.tsx              # Live tenant policy workspace
│   ├── providers/page.tsx             # Live tenant provider directory
│   ├── receipts/page.tsx              # Live tenant receipt summaries
│   ├── services/page.tsx              # Live tenant service directory
│   ├── settings/page.tsx              # Project API-key and member-role controls
│   ├── transactions/page.tsx          # Request and payment activity
│   ├── globals.css                    # Tokens, shared components, dashboard and mobile styles
│   └── layout.tsx                     # Root metadata and AppShell
├── components/
│   ├── app-shell.tsx                  # Role-aware desktop shell, workspace switcher, mobile nav and More sheet
│   ├── agent-create-form.tsx           # Register an agent, validate its identity fields, and copy its new ID
│   ├── agent-directory.tsx            # Scoped agent registration, live list, filters, and empty/error states
│   ├── analytics-dashboard.tsx        # Scoped live spend and capability analytics
│   ├── approval-queue.tsx             # Scoped approval review and confirmed decisions
│   ├── api-key-inventory.tsx           # Scoped key inventory, creation, and confirmed revocation
│   ├── icons.tsx                      # Existing small inline icons used by older PaxRelay screens
│   ├── marketing-chrome.tsx           # Shared sticky public header and footer
│   ├── policy-create-form.tsx          # Create policies with exact USDX limits and access rules
│   ├── policy-detail-row.tsx            # Full policy rule view and agent assignment
│   ├── policy-directory.tsx            # Scoped live policy summaries and filters
│   ├── provider-create-form.tsx         # Register provider details and copy its ID
│   ├── provider-directory.tsx          # Scoped provider registration, live records, filters, and website links
│   ├── receipt-directory.tsx           # Scoped receipt summaries and signature evidence
│   ├── service-publish-form.tsx         # Publish service, provider, pricing, protocol, and health settings
│   ├── service-directory.tsx           # Scoped services, prices, protocols, and latest health result
│   ├── service-status-control.tsx       # Confirmed tenant service pause/resume with quote-expiry explanation
│   ├── reveal.tsx                     # Reduced-motion-aware scroll reveals
│   ├── scoped-api-key-access.tsx       # In-memory scoped API key entry
│   ├── settlement-review.tsx          # Reconciliation queue and evidence details
│   ├── status-badge.tsx               # Shared status label
│   └── transaction-activity.tsx       # Scoped live request and payment activity
├── hooks/
│   ├── use-agents.ts                  # Session-scoped agent query and registration request
│   ├── use-analytics.ts                # Session-scoped analytics API queries
│   ├── use-api-keys.ts                 # Session-scoped key inventory and mutations
│   ├── use-approvals.ts               # Session-scoped queue and decision mutation
│   ├── use-policies.ts                # Session-scoped policy list, detail, and mutation calls
│   ├── use-providers.ts               # Session-scoped provider list and registration request
│   ├── use-receipts.ts                # Session-scoped receipt list query
│   ├── use-services.ts                # Session-scoped service query, publish, and status requests
│   ├── use-settlement-reconciliation.ts # Typed reconciliation API query
│   └── use-transactions.ts             # Session-scoped transaction API query
├── lib/
│   ├── api-client.ts                  # Typed browser HTTP boundary
│   ├── providers.tsx                  # React Query provider setup
│   └── utils.ts                       # Shared client helpers
├── public/
│   ├── PaxRelay-ico.png               # Compact mark and favicon source
│   ├── PaxRelay-logo.png              # Full wordmark
│   ├── favicon.svg                    # Existing SVG favicon
│   └── paxeer-relay-mark.svg          # Existing SVG compact mark
├── DESIGN.md                          # Caldera style and dashboard interaction guidance
├── FILE-STRUCTURE.md                  # This application map
├── next.config.ts                     # Next.js settings
├── package.json                       # Web scripts and direct dependencies
├── postcss.config.js                  # PostCSS setup
├── tailwind.config.ts                 # Tailwind setup
└── tsconfig.json                      # TypeScript settings and path aliases
```

The `app/` directory uses Next.js App Router conventions. A `page.tsx` creates
a URL. A route-group directory such as `(auth)` groups files without adding a
segment to the URL. Root `layout.tsx` wraps pages with the shared application
shell and imports the global stylesheet.

`app/admin/settlements/page.tsx` composes `components/settlement-review.tsx`.
The page uses `hooks/use-settlement-reconciliation.ts` for typed requests and
cursor state; the hook calls the FastAPI route through `lib/api-client.ts`.
`app/analytics/page.tsx` composes `components/analytics-dashboard.tsx`, which
uses `hooks/use-analytics.ts` to read the current project's spend and
capability totals from FastAPI.
`app/transactions/page.tsx` composes `components/transaction-activity.tsx` and
uses `hooks/use-transactions.ts` to show recent request, payment, and execution
states. Both read-only pages use `components/scoped-api-key-access.tsx` to keep
scoped keys in page memory.
`app/agents/page.tsx` composes `components/agent-directory.tsx`, which uses
`hooks/use-agents.ts` to list agents with `agents:read` and register an agent
with `agents:write`. A key with both scopes can complete both actions in one
session. The create form derives an editable lowercase slug from the name,
validates an optional EVM wallet address, and keeps the description optional.
Registration links an address as metadata; it does not connect a wallet or
authorize payment. A successful create is added to the live list, and the new
full agent ID can be copied for policy assignment. The key remains in page
memory, results use a unique connection cache key, and disconnecting or
leaving the page clears those cached results.
`app/policies/page.tsx` composes `components/policy-directory.tsx`, which uses
`hooks/use-policies.ts` to read policy summaries with a `policies:read` key.
`components/policy-create-form.tsx` creates policies with `policies:write`,
exact USDX limits, a mode, optional capability/provider lists, and provider
reputation, success-rate, and average-latency thresholds.
`components/policy-detail-row.tsx` loads one policy's complete rule set and
current agent assignments on demand. It can assign a policy with
`policies:write`; the operator copies an agent UUID from the Agents page.
Money values remain exact atomic-unit integers across the API boundary.
`app/approvals/page.tsx` composes `components/approval-queue.tsx` and
`hooks/use-approvals.ts`. It reads the tenant queue with `approvals:read` and
submits explicit approve or reject decisions with `approvals:write`. The UI
requires a second confirmation and can attach an audit note; approval allows
the request to continue to payment checks but does not submit payment.
`app/providers/page.tsx` composes `components/provider-directory.tsx`, which
uses `hooks/use-providers.ts` to list records visible to a `providers:read` key
and register providers with `providers:write`. A successful registration
refreshes the directory and exposes the provider UUID for copying. The form
captures an editable slug, an optional HTTP(S) website, description, and
payment wallet address; production registrations require a wallet address.
The API returns provider website URLs, which the directory renders only when
they use HTTP or HTTPS. Search and lifecycle state are API-backed; verification
filtering uses the latest returned records. Provider health and performance
are not in this API response.
`app/services/page.tsx` composes `components/service-directory.tsx`, which
uses `hooks/use-services.ts` to list up to 100 recent services visible to a
`services:read` key. `components/service-publish-form.tsx` publishes a service
for a copied provider UUID with `services:write`. It collects capability,
protocols, exact USDX price, service URLs, version, description, and bounded
health-check settings. The amount is converted to atomic units without passing
through JavaScript floating point. Use HTTPS for staging and production; at
invocation, the gateway checks URLs and the production host allowlist before
forwarding. New services stay out of routing until the first health probe
passes. The directory shows configured probe settings separately from the
latest worker result, timestamp, and consecutive failure count. Search,
status, and protocol filters use the returned list. A `services:write` key can
pause or resume a service with `PATCH /v1/services/{service_id}/status`. The
control confirms the change and explains that already-issued, unexpired quotes
can still complete after a pause. Status updates refresh the tenant service
list; deprecated services have no pause or resume action.
`app/receipts/page.tsx` composes `components/receipt-directory.tsx`, which
uses `hooks/use-receipts.ts` to read up to 100 tenant-scoped summaries with a
`receipts:read` key. It preserves `payment_amount` as an exact integer and
shows the returned hashes and signature metadata. The page does not verify
signatures because this endpoint returns a summary rather than the complete
canonical receipt.
`app/settings/page.tsx` composes `components/api-key-inventory.tsx` and
`hooks/use-api-keys.ts`. It lists up to 100 project keys with `api-keys:read`,
and creates or revokes keys with `api-keys:write`. New raw secrets stay in page
memory and are shown once. The current API does not expose general workspace
preferences such as network defaults or receipt-retention settings.

### Live production overview data flow

The overview pages at `/dashboard`, `/admin`, and `/creator` compose
`components/live-dashboard.tsx`. `hooks/use-live-dashboard.ts` requests only the
resources shown in the selected overview and handles each response separately:

- All three views read `/v1/services`, `/v1/transactions`, and
  `/v1/analytics/spend`.
- `/dashboard` also reads `/v1/approvals`.
- `/admin` reads `/v1/providers` and `/v1/approvals`.
- `/creator` reads `/v1/receipts`.

Each view refreshes every 30 seconds. A missing scope, API error, empty list,
or partial response is shown in the affected metric or section. The admin and
creator views are project-scoped because the API does not provide cross-project
admin inventory or creator-member ownership filters.

`components/api-session-control.tsx` is in the shared header. It calls the
production-only session in `lib/api-session.tsx`, which verifies the key with
`GET /v1/context`, exposes the verified project and scopes, and clears cached
query data when the key changes or disconnects. `lib/providers.tsx` wraps the
application in TanStack Query and the API session provider. API requests pass
through `lib/api-client.ts`; production builds require an HTTPS API base URL.

## Route map

| URL | File | Purpose and status |
| --- | --- | --- |
| `/` | `app/page.tsx` | Public product landing page with product overview and links to dashboard workspaces. |
| `/sign-in` | `app/(auth)/sign-in/page.tsx` | Company OIDC sign-in; users need a pre-provisioned verified email and active project membership. |
| `/how-it-works` | `app/how-it-works/page.tsx` | Public explanation of the request, policy, payment, provider response, and receipt flow. |
| `/for-teams` | `app/for-teams/page.tsx` | Public introduction for teams that operate AI agents. |
| `/for-providers` | `app/for-providers/page.tsx` | Public introduction for online service providers. |
| `/dashboard` | `app/dashboard/page.tsx` | Live production project overview for services, transactions, approvals, and spend. |
| `/admin` | `app/admin/page.tsx` | Project-scoped providers, service health, requests, approvals, and settlement review. |
| `/admin/settlements` | `app/admin/settlements/page.tsx` | Tenant-scoped reconciliation review; reads API data with a `settlements:read` key. |
| `/creator` | `app/creator/page.tsx` | Project-scoped services, requests, spend, and receipts; not filtered to an individual creator. |
| `/agents` | `app/agents/page.tsx` | Reads up to 100 agents with `agents:read`; registers agents with `agents:write`; supports local search, status filtering, and copying full agent IDs. |
| `/policies` | `app/policies/page.tsx` | Reads up to 100 policy summaries with `policies:read`; creates policies and assigns agents with `policies:write`; expands a policy row to show its complete rules and current assignments. |
| `/approvals` | `app/approvals/page.tsx` | Reads up to 100 recent requests with `approvals:read`; approve/reject requires `approvals:write`, a confirmation step, and supports an optional audit note. |
| `/transactions` | `app/transactions/page.tsx` | Reads up to 100 recent request records with request/payment state filters and a `transactions:read` key. |
| `/providers` | `app/providers/page.tsx` | Reads up to 100 provider records with `providers:read`; registers providers with `providers:write`; supports search, lifecycle filters, verification filtering, and copying full provider IDs. Website links are limited to HTTP(S). Health and performance metrics are not returned by this endpoint. |
| `/services` | `app/services/page.tsx` | Reads recent service records with `services:read`; publishes a service for a provider UUID and pauses/resumes a service with `services:write`; supports search, status, and protocol filters. Shows configured probe settings and the latest worker result, timestamp, and failure streak. |
| `/receipts` | `app/receipts/page.tsx` | Reads up to 100 tenant-scoped receipt summaries with a `receipts:read` key; supports local search and execution-state filtering. Shows signature metadata but does not verify signatures. |
| `/analytics` | `app/analytics/page.tsx` | Reads the last 30 days of spend and capability totals from the API with an `analytics:read` key. |
| `/settings` | `app/settings/page.tsx` | Lists, creates, and revokes project API keys and manages project members and roles. New key secrets are shown once in page memory. General preferences are not exposed by the API. |
| `/api/health` | `app/api/health/route.ts` | Next.js process health. It does not check FastAPI or the database. |
| `/api/auth/[...nextauth]` | `app/api/auth/[...nextauth]/route.ts` | Auth.js OIDC callback and encrypted session endpoints. |
| `/api/paxrelay/[...path]` | `app/api/paxrelay/[...path]/route.ts` | Same-origin API proxy; authenticates the session and signs short-lived assertions for FastAPI. |

The admin and creator pages have overview sections for their mobile and desktop
navigation. Current section destinations use URL fragments, such as
`/admin#providers`, `/creator#services`, and `/creator#receipts`; these are not
separate route files. Settlement review is a nested route because it has its
own API access, loading, empty, error, and populated states.

The public landing page, informational pages, and sign-in page do not use
the dashboard shell. The landing page at `/` explains the product and links to
the dashboard workspaces. `How it works`, `For teams`, and `For providers` have
separate public routes. `/sign-in` starts the configured company OIDC flow;
protected deployments fail startup if OIDC configuration is missing.
`components/marketing-chrome.tsx` supplies the
sticky header and footer for public pages. `components/reveal.tsx` uses Motion
for small scroll-triggered reveals and respects reduced-motion preferences.

## Navigation and workspace selection

`components/app-shell.tsx` reads the current pathname and selects one of three
navigation sets:

| Path prefix | Shell navigation |
| --- | --- |
| `/admin` | Project providers, services, requests, approvals, settlement review, and project settings |
| `/creator` | Provider project overview, services, requests, receipts, and project settings |
| Other dashboard routes | PaxRelay operate, configure, network, evidence, and workspace settings |

On desktop, the fixed navigation rail includes a workspace switcher for
`/dashboard`, `/admin`, and `/creator`. On small screens, the rail is replaced
with a floating four-item pill. The fourth item opens the `More` sheet. The
sheet contains quick links for the current workspace and links for switching
dashboards. Its open state, Escape handling, focus, background scroll lock, and
close actions are owned by `app-shell.tsx`.

The admin and creator overview section links remain same-page fragments. The
settlement review link uses its own route. The mobile navigation is styled in
`app/globals.css`, including device safe-area spacing and the backdrop and
bottom sheet.

## Icon usage

The dashboard shell and the new overview pages use Hugeicons through the direct
dependencies `@hugeicons/react` and `@hugeicons/core-free-icons` in
`package.json`. Import only the named icons required by each component so the
bundler can omit unused icons. The prior `components/icons.tsx` remains for
existing PaxRelay resource screens that still import its inline SVG icons.
See the [Hugeicons React quick start](https://hugeicons.com/docs/integrations/react/quick-start)
for the upstream component and icon package usage.

Public-page reveals use the `motion` dependency and its `motion/react` entry
point. Motion is only used for decorative entrances; page content remains
visible without animation and reduced-motion preferences disable movement.

Decorative icons use `aria-hidden="true"`. Icon-only controls need an
accessible name. Navigation links retain visible text labels so meaning does
not depend on the icon.

## Code ownership and data flow

### `app/`: route and page composition

Route files compose one page for one URL. Keep role-specific overview content in
`app/admin/page.tsx` and `app/creator/page.tsx` until a workflow grows into
multiple routes or reusable domain components. Keep common navigation, status
labels, and controls under `components/`.

### `components/`: shared interface pieces

`app-shell.tsx` owns the role-specific sidebar, dashboard switcher, top bar,
mobile navigation, and quick-action sheet. Use feature components for live
resource pages; Settings uses `components/api-key-inventory.tsx`. Keep shared
behavior in reusable components and use [`DESIGN.md`](DESIGN.md) for visual
rules.

### `hooks/` and `lib/`: API boundary

`lib/api-client.ts` is the browser's typed HTTP boundary. In staging and
production it sends requests to the same-origin web proxy, which forwards a
short-lived signed assertion and selected project ID to FastAPI. In development
it can accept a scoped API key held only in page memory. Hooks such as
`hooks/use-analytics.ts`, `hooks/use-transactions.ts`, and
`hooks/use-settlement-reconciliation.ts` own request state and API response
types. Dashboard sessions load project memberships from `/v1/auth/projects`, and the API rechecks the selected membership role on every request. Query data is cleared when the user or project changes. The workspace, admin, and creator overviews use `hooks/use-live-dashboard.ts` and load live resources independently. Admin and creator overviews remain project-scoped because the API does not yet provide platform-wide or per-creator identity filtering. The network adapter paths and response contracts still require operator confirmation before the data can be treated as production settlement evidence.

```text
Route page
   │
   ├── shared component for display and interaction
   │
   └── feature hook (when connected)
          │
          └── lib/api-client.ts
                 │  HTTP + bearer token
                 ▼
              apps/api (/v1/...)
```

The web application must not connect directly to PostgreSQL. Production and
staging dashboard requests pass through the server-side proxy so the browser
does not receive a machine API key or internal assertion secret. Only explicitly
public configuration, such as the expected app environment, may use a
`NEXT_PUBLIC_` environment variable.

### `public/`: brand assets

- Use `/PaxRelay-logo.png` for the full wordmark on a light surface.
- Use `/PaxRelay-ico.png` for compact brand placement and the browser icon.
- Keep filenames' capitalization unchanged; paths are case-sensitive on Linux.

Existing SVG marks remain available for compatibility.

## Local development

Install workspace dependencies from the repository root. Start the web server
from its app directory:

```powershell
cd apps/web
pnpm dev
```

The web server listens on `http://localhost:3000`. To start the API separately:

```powershell
cd apps/api
uv run uvicorn app.main:app --reload
```

Starting the web server does not start FastAPI or PostgreSQL. Check
[`../../docs/deployment.md`](../../docs/deployment.md) and
[`../../docs/api-reference.md`](../../docs/api-reference.md) for API settings
and database requirements.

## Rules for future changes

1. Put one URL's page composition in its route file and reusable interface
   pieces in `components/`.
2. Keep internal platform administration, organisation operations, and
   provider-owned workflows separate in both navigation and API permissions.
3. Keep browser data access behind `lib/api-client.ts` and typed hooks.
4. Add loading, empty, error, and populated states before treating a live data
   page as complete.
5. Use PaxRelay domain terms: agents, providers, services, policies,
   transactions, payments, executions, and receipts.
6. Update this map when routes, dashboard boundaries, or major data paths
   change.
