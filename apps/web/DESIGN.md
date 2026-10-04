# PaxRelay Visual Direction

> Forge fire on warm limestone.

PaxRelay is an operations desk for teams that let software spend money. The interface should feel like a clear instrument: bold enough to be memorable, calm enough to support careful decisions, and direct about what an agent is allowed to do.

This direction uses the Caldera reference's warm paper surfaces, industrial display type, flat construction, ember actions, and halftone artwork. The dashboard keeps its operational hierarchy and readable data density.

## Design principles

1. **Let type carry the character.** Use condensed, heavy display headings. Keep supporting copy plain and medium weight.
2. **Use orange with purpose.** Ember marks the main action, an active step, or a decision that needs attention.
3. **Build depth with paper and color.** Separate the pumice canvas, limestone surfaces, and rare feature panels. Do not use shadows.
4. **Keep decisions legible.** Name the agent, service, price, policy, and result in plain language. State labels and icons must work without color.
5. **Use one signature image.** The orange halftone over violet is for a hero or lifecycle illustration. Keep the rest of the interface quiet.
6. **Preserve evidence.** Keep the payment, provider response, policy result, and receipt close together in the request story.

## Color tokens

| Name | Value | Use |
| --- | --- | --- |
| Pumice | #e2e2df | Main page canvas |
| Limestone | #f7f6f2 | Cards, content panels, and quiet controls |
| Obsidian | #070607 | Main text, headings, borders, and dark panels |
| Chalk | #ffffff | Text on dark surfaces |
| Ember | #fc5000 | Primary action, active relay step, and key emphasis |
| Plasma violet | #524ae9 | Hero halftone and one featured visual surface only |
| Sulfur | #f5f28e | Category tags and small explanatory badges |

Keep the palette constrained. Do not use violet for buttons or routine status. Do not add color for decoration. Use words and simple icons first for states such as settled, pending, denied, and routing. Any state color must communicate a real outcome and pass contrast checks.

## Typography

- **Display:** PP Neue Corp Compact when a licensed font file is available. Use Bebas Neue, Anton, or Impact as a substitute. Apply it to page titles, hero statements, and large metrics.
- **Interface:** DM Sans Medium (500). Use Inter Medium or a system sans-serif fallback if DM Sans is unavailable. Use it for body copy, navigation, controls, tables, and supporting headings.
- **Captions:** System sans-serif at 12px for dates and secondary metadata only.

Use positive tracking around 0.02em for the condensed display face. Do not squeeze its letters together. Use 26px and above for structural headings. Keep ordinary page titles around 48-64px, supporting headings around 26-32px, and body copy at 14-18px with comfortable line height. Reserve 80-189px type for entry pages and poster-like feature moments, not routine data screens.

## Layout and shape

- Maximum content width: 1280px.
- Give marketing and entry pages generous section gaps, around 80px.
- Use a 4px spacing base, with 16px for common control gaps and 40px for card padding.
- Cards and major content panels use a 40px radius.
- Buttons, tags, navigation containers, and compact controls use a full pill shape.
- Inputs use a full pill shape. On dark panels, use a 1.5px Chalk outline and Chalk text.
- Keep surfaces flat. Use no drop shadows. Use solid, dotted, or color boundaries only when they explain grouping or sequence.

## Components

### Navigation

Use a Limestone pill container for top-level navigation on entry and marketing pages. Keep links in Obsidian, with a small Ember marker for the active destination. In the operator console, a persistent navigation rail may remain for fast access; make it a quiet Limestone surface with the same pill-shaped links.

Keep the public navigation sticky near the top edge on desktop and mobile. Use
a translucent Limestone pill with a blurred canvas behind it. On small screens,
keep the page links available in a compact, horizontally scrollable row below
the brand and primary actions. Respect the device safe-area inset.

### Public landing page and sign-in

Use `/` for the public product landing page. Explain what PaxRelay does, show
the request lifecycle, identify the people it serves, and link visitors to the
dashboard previews. Keep dedicated pages at `/how-it-works`, `/for-teams`, and
`/for-providers` for the request flow and each primary audience. Keep marketing
sections spacious and use the Ember-to-violet halftone treatment for one
request illustration. Label dashboard content as sample data while the product
remains a preview.

Keep sign-in at `/sign-in`, separate from the public homepage. Public marketing
routes render without the workspace dashboard shell. The current sign-in
providers are visual placeholders, so say that clearly and do not imply that
authentication is connected. Use subtle Motion in-view reveals for sections
and cards; keep content visible if animation is unavailable and honor reduced
motion preferences.

### Page headings

Use one clear title, a short explanation, and no more than two actions. The main action is an Ember pill with Obsidian text. Secondary actions are outlined or quiet pill links.

### Relay flow

Show the request as a sequence: agent request, policy and price check, payment, provider response, receipt. Use connected steps only when the order matters. The current step may use Ember. Use the violet halftone treatment once as a visual anchor; keep labels outside dense dot fields.

### Data surfaces

Use Limestone panels with 40px corners and no shadows. Keep tables calm and readable, with strong first-column text, clear row separators, and enough spacing for quick scanning. Keep transaction IDs, hashes, and network details in small evidence text rather than headlines.

### Metrics

Use flat, clear numbers with a time period or comparison. Ember can fill one featured metric panel. Keep the remaining metrics on Limestone; do not turn every card into a colored tile.

### Approval requests

Show the agent, requested service, amount, rule, current limit, and expiry before the decision. Use Sulfur for a review tag. Name both actions clearly. A user should understand what approval changes before acting.

### Inputs

Keep search and form fields as wide pills with clear labels. Use the Chalk outline treatment on Obsidian surfaces. On light pages, use Limestone fills and a 1.5px Obsidian outline.

## Graphics and imagery

Use graphic artwork rather than stock photography, 3D renders, or crypto decoration. The signature treatment is a high-density halftone that moves from Plasma violet toward Ember. Use it in a large, rounded hero or in the request-flow image. Keep icons small, monochrome, and simple.

## Accessibility and responsive behavior

- Keep text and controls high contrast. Ember actions use Obsidian text.
- Pair every status color with a written label and a distinct icon or shape.
- Keep keyboard focus visible with a 2px Ember outline and offset.
- Respect reduced-motion preferences. Motion must never carry essential status information.
- Let tables scroll inside their own surface on small screens; do not create page-wide horizontal overflow.
- Keep primary controls at least 44px high on touch screens.

## Voice

Write from the operator's point of view. Use short, active labels such as Add agent, Review request, Review receipt, and Save changes. Say what happened and what the person can do next. Explain a technical term when it first appears.

## Dashboard workspaces

PaxRelay has three separate dashboard experiences. Keep their navigation,
language, and data scopes distinct while sharing Caldera colors, type,
surfaces, controls, and status patterns.

| Workspace | Route | Intended user | Main responsibility |
| --- | --- | --- | --- |
| PaxRelay workspace | `/dashboard` | An organisation using PaxRelay | Monitor agents, policies, providers, payments, and receipts for that organisation |
| Admin dashboard | `/admin` | PaxRelay's internal operations team | Review platform workspaces and creators, monitor platform health, and inspect platform activity |
| Creator dashboard | `/creator` | A provider publishing paid services | Manage provider services and follow requests and payment evidence for that provider |

In this product, a **creator** is a service provider. It does not mean a video
or media creator. The admin dashboard is for PaxRelay's internal team; the
PaxRelay workspace remains the customer-facing operator console.

### Shared workspace frame

```text
Desktop
brand + dashboard switcher | role-specific navigation | context + account
                                                       page title + actions
                                                       summary + work queue
                                                       evidence and activity

Mobile
content with safe-area spacing
floating limestone pill: Home | role shortcut | Activity/Requests | More
More opens a blurred scrim and a scrollable quick-action sheet
```

- Keep a persistent role-specific navigation rail on desktop. The workspace
  switcher links to the PaxRelay, Admin, and Creator dashboards.
- Show the active organisation, platform, or provider context in the shell.
  Replace demo names with the authenticated account's actual context.
- Give each page one clear heading, a short explanation, and no more than two
  actions. Put filters beside the data they affect.
- Keep payment, policy, provider, execution, and receipt evidence together in
  detail views so an operator can follow one request without changing context.
- Scope PaxRelay workspace records to the signed-in organisation and project.
  Scope creator records to the signed-in provider. Give platform admins only
  the platform controls their role permits.

### Mobile navigation and quick actions

Use the mobile navigation at viewport widths up to 760px. It is a fixed,
floating Limestone pill with four equal, touch-sized destinations. Use a small
Ember treatment and Obsidian text for the active destination. Leave enough page
padding for the bar and the device safe area.

The fourth item is `More`. It opens a bottom sheet with:

1. A clear `Quick actions` heading and a close button.
2. A four-column grid of the current workspace's remaining destinations.
3. A `Switch dashboard` area for the PaxRelay, Admin, and Creator workspaces.
4. A dimmed, softly blurred page behind the sheet.

Close the sheet from its close button, the backdrop, or the Escape key. Lock
background scrolling while it is open, move focus into it, and return focus to
the More button when it closes. Keep the sheet within the viewport, scroll its
contents when needed, and include the device safe-area inset below its content.

Use Hugeicons' React package for dashboard navigation and dashboard content
icons. Import only the named icons used by the page. Keep icons monochrome and
around 20-24px in the mobile bar. Give icon-only controls accessible labels;
hide decorative icons from assistive technology when adjacent text already
names the action. Icons must support, not replace, a written destination label.

### PaxRelay workspace dashboard

The current `/dashboard` is the organisation operator's overview. Preserve its
existing routes and navigation groups:

| Group | Destinations | Operator task |
| --- | --- | --- |
| Operate | Overview, Transactions, Approvals | Monitor requests and decide exceptions |
| Configure | Agents, Policies | Control who can spend and under which limits |
| Network | Providers, Services | Manage available service destinations |
| Evidence | Receipts, Analytics | Inspect outcomes and spending records |
| Workspace | Settings | Review workspace configuration |

The current Receipts page reads up to 100 tenant-scoped summaries with a
`receipts:read` key. Keep payment amounts in exact atomic units and show hashes
and signature metadata as returned by the API. The page does not verify the
signature, so avoid verified or trusted labels unless verification is added.

Keep the page order: title and workspace context; relay, settlement, success,
and attention metrics; a request lifecycle; recent transactions; approval
requests; then spend trend and operational activity. Every metric includes its
period or scope. Show the agent, requested service, amount, governing rule,
current limit, and expiry before an approval decision.

Approval actions must be explicit (`Approve once`, `Deny`, or the equivalent
supported action). The current API provides a tenant-scoped approval queue and
a decision endpoint. Show a decision as persisted only after that endpoint
confirms it. The API attributes a decision to the API key, not to an individual
dashboard user, so do not show a named reviewer unless user identity is added.

### Admin dashboard

The `/admin` dashboard is the internal platform overview. It is a separate
experience from the organisation's PaxRelay workspace. Keep these regions in
this order:

Admin navigation includes `Overview`, `Creators`, `Activity`, `Settlement
review`, `Workspaces`, `Platform health`, and `Settings`.

1. Platform context, a plain-language heading, and links to creator review or
   platform activity.
2. Summary measures for active workspaces, creator accounts, request volume,
   and relay health. Mark every sample figure and identify its time period.
3. Creator onboarding and review queue, with account, category, submission
   time, and review state.
4. Platform health for request routing, policy checks, payment connections,
   and receipt records. Clearly distinguish demo connections from live ones.
5. Workspace directory and recent platform activity.
6. A reserved place for platform-wide controls and role settings.

Do not place a customer's private transaction or policy settings in the
platform overview unless the admin's role explicitly grants that access. The
current page is a sample-data preview; it does not approve creators or change
platform configuration.

### Settlement review

The `/admin/settlements` route is a read-only queue backed by
`GET /v1/settlements/reconciliation`. It is tenant-scoped by the API key, so
label the project and environment scope instead of implying a cross-tenant
platform view. Keep `Needs review`, `Waiting for evidence`, `LayerX confirmed`,
and `Reconciled` filters beside the queue. Do not invent totals: the endpoint
returns one cursor-paginated page at a time and does not return aggregate
counts.

Show the payment ID, payment state, reconciliation status, LayerX reference,
and last-check time in the queue. Selecting a record reveals issue codes,
expected and recorded values, available LayerX and L1 references, attempts,
and the next check time. Never show raw payment proofs. The page refreshes its
read-only list; it does not start another reconciliation or modify payments.

The sign-in preview is not connected yet. During preview, an operator may
paste a key with `settlements:read` scope. Keep it in page memory only, clear
it on disconnect or reload, and label this as a temporary preview access path.
Replace it with the authenticated admin session before production use; do not
persist operator API keys in browser storage.

### Creator dashboard

The `/creator` dashboard is the provider's home for publishing services and
following work. Keep these regions in this order:

1. Provider name, availability, and the primary `Manage services` action.
2. Summary measures for published services, incoming requests, recorded
   payments, and service availability. Include a period for each measure.
3. The provider's services with a short description, recent request count, and
   availability state.
4. Recent requests with the calling agent, service, amount, execution state,
   and time.
5. Payment and execution receipts near the requests they describe.
6. Provider profile and account settings.

Keep creator navigation short: `Overview`, `Services`, `Requests`, `Receipts`,
and `Profile & settings`. Do not show tenant-wide agent or policy controls in
this workspace. The current page is a sample-data preview; publishing,
provider-scoped authentication, and live creator data are not connected yet.

### Brand assets

- Use `apps/web/public/PaxRelay-logo.png` for the full wordmark on light
  surfaces. Preserve its natural aspect ratio and do not rebuild the wordmark
  with interface text.
- Use `apps/web/public/PaxRelay-ico.png` for compact navigation and the
  browser favicon.
- Keep the wordmark on limestone or another light surface so its dark ink and
  ember detail remain visible. Do not place the dark PNG directly on an
  obsidian panel without a light backing surface.

## Implementation map

| Area | Current location | Role |
| --- | --- | --- |
| Global tokens and responsive styling | `apps/web/app/globals.css` | Shared Caldera foundations |
| Workspace shell and navigation | `apps/web/components/app-shell.tsx` | PaxRelay, platform admin, and creator shells; responsive navigation and More sheet |
| Overview and operations pages | `apps/web/app/dashboard/`, `agents/`, `policies/`, `approvals/`, `transactions/` | Current operator experience |
| Network pages | `apps/web/app/providers/`, `services/` | Provider and service administration |
| Evidence pages | `apps/web/app/receipts/`, `analytics/` | Live tenant receipt summaries and analytics |
| Shared page and state components | `apps/web/components/` | Reusable presentation pieces |
| API boundary and query hooks | `apps/web/lib/`, `apps/web/hooks/` | Typed HTTP access; not yet wired to every screen |
| Admin and creator overview pages | `apps/web/app/admin/page.tsx`, `apps/web/app/creator/page.tsx` | Current visual previews using sample data |
| Settlement review | `apps/web/app/admin/settlements/`, `apps/web/components/settlement-review.tsx` | Tenant-scoped read-only queue, evidence details, and preview API-key entry |
| Dashboard icons | `@hugeicons/react`, `@hugeicons/core-free-icons` | Hugeicons React renderer and free icon pack |

The Next.js app must call the FastAPI API through `apps/web/lib/`. Browser
components must not connect directly to PostgreSQL or hold server secrets.

## Do

- Use warm neutral surfaces and Obsidian text.
- Use Ember for the main action and active relay position.
- Keep the violet halftone rare and recognizable.
- Use 40px surfaces and pill-shaped controls consistently.
- Keep evidence near the decision it supports.

## Do not

- Add shadows, gradients outside the signature artwork, or extra accent colors.
- Use violet for buttons, routine navigation states, or status decoration.
- Use large type in dense tables or small display headings below 26px.
- Make success depend on color alone.
- Imply that connecting a wallet gives PaxRelay custody or spending authority.
