# PaxRelay web dashboard file structure

This guide maps the Next.js application in `apps/web`: URL routes, the three
dashboard workspaces, shared interface code, icon packages, and the browser-to-
API boundary.

In this document, **Current** means the file or route exists in the checkout.
**Preview** means the page is implemented with sample content but is not backed
by the corresponding live API workflow. **Planned** means the route or workflow
does not exist yet.

## Dashboard workspaces

The app contains three distinct workspaces. The route shell chooses its
navigation from the current URL.

| Workspace | Route | Purpose | Data scope |
| --- | --- | --- | --- |
| PaxRelay workspace | `/dashboard` | An organisation's agent, policy, provider, transaction, and receipt operations | Intended to be the signed-in organisation and project |
| Admin dashboard | `/admin` | PaxRelay internal platform overview, creator review, workspace directory, and platform health | Intended for internal admin roles |
| Creator dashboard | `/creator` | Provider services, incoming requests, payment records, and profile | Intended to be the signed-in provider |

`/admin` and `/creator` are preview pages and use sample data. Their navigation
links to sections on the overview page with URL fragments, for example
`/admin#creators` and `/creator#requests`. `/admin/settlements` is a live,
read-only review screen backed by the tenant-scoped API. Sign-in remains a
preview; the review screen accepts a `settlements:read` API key in page memory.
The PaxRelay workspace keeps its existing resource routes, such as `/agents`,
`/policies`, and `/transactions`.

## Current application tree

```text
apps/web/
├── app/
│   ├── (auth)/
│   │   ├── layout.tsx                 # Public sign-in route-group layout
│   │   └── sign-in/page.tsx           # Sign-in preview; buttons are presentation only
│   ├── admin/
│   │   ├── page.tsx                   # Platform admin dashboard preview
│   │   └── settlements/page.tsx       # Read-only settlement review route
│   ├── agents/page.tsx                # Live tenant agent directory
│   ├── analytics/page.tsx             # Spend and capability analytics
│   ├── api/
│   │   └── health/route.ts            # Next.js process health response
│   ├── approvals/page.tsx             # Live approval queue and decisions
│   ├── creator/
│   │   └── page.tsx                   # Provider dashboard preview
│   ├── dashboard/page.tsx             # PaxRelay organisation overview
│   ├── for-providers/page.tsx         # Public service-provider introduction
│   ├── for-teams/page.tsx             # Public agent-operator introduction
│   ├── how-it-works/page.tsx          # Public request lifecycle explanation
│   ├── page.tsx                       # Public product landing page
│   ├── policies/page.tsx              # Live tenant policy summary directory
│   ├── providers/page.tsx             # Live tenant provider directory
│   ├── receipts/page.tsx              # Live tenant receipt summaries
│   ├── services/page.tsx              # Live tenant service directory
│   ├── settings/page.tsx              # PaxRelay workspace settings
│   ├── transactions/page.tsx          # Request and payment activity
│   ├── globals.css                    # Tokens, shared components, dashboard and mobile styles
│   └── layout.tsx                     # Root metadata and AppShell
├── components/
│   ├── app-shell.tsx                  # Role-aware desktop shell, workspace switcher, mobile nav and More sheet
│   ├── agent-directory.tsx            # Scoped live agent list, filters, and empty/error states
│   ├── analytics-dashboard.tsx        # Scoped live spend and capability analytics
│   ├── approval-queue.tsx             # Scoped approval review and confirmed decisions
│   ├── icons.tsx                      # Existing small inline icons used by older PaxRelay screens
│   ├── marketing-chrome.tsx           # Shared sticky public header and footer
│   ├── policy-directory.tsx            # Scoped live policy summaries and filters
│   ├── provider-directory.tsx          # Scoped live provider records and filters
│   ├── receipt-directory.tsx           # Scoped receipt summaries and signature evidence
│   ├── service-directory.tsx           # Scoped live services, prices, protocols, and probe settings
│   ├── reveal.tsx                     # Reduced-motion-aware scroll reveals
│   ├── resource-page.tsx              # Shared presentation for resource screens
│   ├── scoped-api-key-access.tsx       # In-memory scoped API key entry
│   ├── settlement-review.tsx          # Reconciliation queue and evidence details
│   ├── status-badge.tsx               # Shared status label
│   └── transaction-activity.tsx       # Scoped live request and payment activity
├── hooks/
│   ├── use-agents.ts                  # Session-scoped React Query hook for agents
│   ├── use-analytics.ts                # Session-scoped analytics API queries
│   ├── use-approvals.ts               # Session-scoped queue and decision mutation
│   ├── use-policies.ts                # Session-scoped policy list query
│   ├── use-providers.ts               # Session-scoped provider list query
│   ├── use-receipts.ts                # Session-scoped receipt list query
│   ├── use-services.ts                # Session-scoped service list query
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
`hooks/use-agents.ts` to list agents visible to the supplied `agents:read` key.
The key remains in page memory, results use a unique connection cache key, and
disconnecting or leaving the page clears those cached results.
`app/policies/page.tsx` composes `components/policy-directory.tsx`, which uses
`hooks/use-policies.ts` to read policy summaries with a `policies:read` key.
The API returns policy name, description, mode, version, and active state, but
does not include rule details or agent assignments in this list response.
`app/approvals/page.tsx` composes `components/approval-queue.tsx` and
`hooks/use-approvals.ts`. It reads the tenant queue with `approvals:read` and
submits explicit approve or reject decisions with `approvals:write`. The UI
requires a second confirmation and can attach an audit note; approval allows
the request to continue to payment checks but does not submit payment.
`app/providers/page.tsx` composes `components/provider-directory.tsx`, which
uses `hooks/use-providers.ts` to list records visible to a `providers:read` key.
Search and lifecycle state are API-backed; verification filtering uses the
latest returned records. Provider health and performance are not in this API
response.
`app/services/page.tsx` composes `components/service-directory.tsx`, which
uses `hooks/use-services.ts` to list up to 100 recent services visible to a
`services:read` key. Search, status, and protocol filters use that returned
list. Prices retain their exact atomic-unit values, and the displayed health
probe fields are configured settings rather than live probe results.
`app/receipts/page.tsx` composes `components/receipt-directory.tsx`, which
uses `hooks/use-receipts.ts` to read up to 100 tenant-scoped summaries with a
`receipts:read` key. It preserves `payment_amount` as an exact integer and
shows the returned hashes and signature metadata. The page does not verify
signatures because this endpoint returns a summary rather than the complete
canonical receipt.

## Route map

| URL | File | Purpose and status |
| --- | --- | --- |
| `/` | `app/page.tsx` | Public product landing page with product overview and links to the dashboard previews. |
| `/sign-in` | `app/(auth)/sign-in/page.tsx` | Sign-in preview. Authentication buttons do not sign in yet. |
| `/how-it-works` | `app/how-it-works/page.tsx` | Public explanation of the request, policy, payment, provider response, and receipt flow. |
| `/for-teams` | `app/for-teams/page.tsx` | Public introduction for teams that operate AI agents. |
| `/for-providers` | `app/for-providers/page.tsx` | Public introduction for online service providers. |
| `/dashboard` | `app/dashboard/page.tsx` | PaxRelay organisation operations overview; metrics and events are sample data. |
| `/admin` | `app/admin/page.tsx` | Internal platform admin overview; creator reviews, workspace list, health, and activity are sample data. |
| `/admin/settlements` | `app/admin/settlements/page.tsx` | Tenant-scoped reconciliation review; reads API data with a `settlements:read` key. |
| `/creator` | `app/creator/page.tsx` | Service-provider overview; services, requests, payment records, and profile are sample data. |
| `/agents` | `app/agents/page.tsx` | Reads up to 100 agents visible to the supplied project/environment using an `agents:read` key; supports local search and status filtering. |
| `/policies` | `app/policies/page.tsx` | Reads up to 100 policy summaries using a `policies:read` key; supports API-backed name, mode, and active-state filters. Rule details and assignments are not included by this endpoint. |
| `/approvals` | `app/approvals/page.tsx` | Reads up to 100 recent requests with `approvals:read`; approve/reject requires `approvals:write`, a confirmation step, and supports an optional audit note. |
| `/transactions` | `app/transactions/page.tsx` | Reads up to 100 recent request records with request/payment state filters and a `transactions:read` key. |
| `/providers` | `app/providers/page.tsx` | Reads up to 100 provider records with `providers:read`; supports API-backed name/slug and lifecycle filters, plus local verification filtering. Health and performance metrics are not returned by this endpoint. |
| `/services` | `app/services/page.tsx` | Reads up to 100 recent service records with a `services:read` key; supports search, status, and protocol filters. Displays configured probe settings, not live health results. |
| `/receipts` | `app/receipts/page.tsx` | Reads up to 100 tenant-scoped receipt summaries with a `receipts:read` key; supports local search and execution-state filtering. Shows signature metadata but does not verify signatures. |
| `/analytics` | `app/analytics/page.tsx` | Reads the last 30 days of spend and capability totals from the API with an `analytics:read` key. |
| `/settings` | `app/settings/page.tsx` | PaxRelay workspace settings presentation. |
| `/api/health` | `app/api/health/route.ts` | Next.js process health. It does not check FastAPI or the database. |

The admin and creator pages have overview sections for their mobile and desktop
navigation. Current section destinations use URL fragments, such as
`/admin#creators`, `/creator#services`, and `/creator#receipts`; these are not
separate route files. Settlement review is a nested route because it has its
own API access, loading, empty, error, and populated states.

The public landing page, informational pages, and sign-in preview do not use
the dashboard shell. The landing page at `/` explains the product and links to
the sample workspaces. `How it works`, `For teams`, and `For providers` have
separate public routes. `/sign-in` is a visual preview because identity
providers are not yet connected. `components/marketing-chrome.tsx` supplies the
sticky header and footer for public pages. `components/reveal.tsx` uses Motion
for small scroll-triggered reveals and respects reduced-motion preferences.

## Navigation and workspace selection

`components/app-shell.tsx` reads the current pathname and selects one of three
navigation sets:

| Path prefix | Shell navigation |
| --- | --- |
| `/admin` | Platform overview, creators, activity, settlement review, workspaces, platform health, and admin controls |
| `/creator` | Provider overview, services, requests, receipts, and profile settings |
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
mobile navigation, and quick-action sheet. `resource-page.tsx` composes the
existing PaxRelay resource views. Keep shared behavior here and use
[`DESIGN.md`](DESIGN.md) for visual rules.

### `hooks/` and `lib/`: API boundary

`lib/api-client.ts` is the browser's typed HTTP boundary. It accepts a bearer
token from its caller and unwraps the API error envelope. Hooks such as
`hooks/use-analytics.ts`, `hooks/use-transactions.ts`, and
`hooks/use-settlement-reconciliation.ts` own request state and API response
types. Analytics, transactions, and settlement review keep their keys in React
state, never browser storage. The API client is not connected to every screen:
the admin and creator overviews and most other dashboard pages still show
sample data. The network adapter paths and response contracts still require
operator confirmation before the data can be treated as production settlement
evidence.

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

The web application must not connect directly to PostgreSQL. API keys and
privileged credentials belong on the server. Only explicitly public
configuration may use a `NEXT_PUBLIC_` environment variable.

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
