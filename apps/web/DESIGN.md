# Paxeer Relay — Design Direction

> A calm operations desk for software that spends money.

Paxeer Relay is a payment gateway, service router, and AgentOps control plane for teams running autonomous agents on Paxeer Network. Its primary audience is the operator accountable for cost, permissions, and reliability. Every screen has one job: make it obvious what an agent is doing, what it may do, what needs a person, and what can be proven afterward.

## Design thesis

The interface should feel like an instrument, not a casino, wallet, or generic admin template. It borrows AiKi’s task-first information hierarchy, compact shell, plain-language state labels, and restrained warm accent. It borrows Refero’s strongest SaaS lessons: hairlines instead of ornamental shadows, precise density, few radii, one committed action color, and product evidence as the visual texture.

The signature gesture is the **relay trace**: request → policy → settlement → receipt. It is the product’s real value chain and should appear anywhere the lifecycle matters. Amber-orange is the moving signal in that trace and the color of authority requiring attention.

## Principles

1. **Lead with current state.** Put live work, blocked work, and decisions above retrospective charts.
2. **Authority is explicit.** Approval copy names the agent, provider, amount, rule, and expiry. Never make approval a vague confirmation.
3. **Evidence stays attached.** A payment, provider response, policy decision, and receipt are parts of one trace.
4. **Color has a job.** Orange is action and human attention. Green is verified or safely complete. Blue is routing or informational. Red is denied or failed. Neutrals do everything else.
5. **Numbers need context.** Pair every metric with a period, denominator, delta, or operational meaning.
6. **Compact, never cramped.** Dense tables use 53px rows, clear grouping, and generous page gutters. Reading copy remains at a comfortable line height.
7. **Fail closed in the interface.** Uncertain payment, policy, or signature states must not look successful.

## Color tokens

| Token         |     Value | Role                                                           |
| ------------- | --------: | -------------------------------------------------------------- |
| Canvas        | `#F3F4F1` | App background; cool enough to avoid a generic cream aesthetic |
| Paper         | `#FFFFFF` | Tables, cards, controls                                        |
| Soft paper    | `#F8F9F6` | Sidebar, table heads, nested states                            |
| Ink           | `#171917` | Primary text and committed neutral actions                     |
| Secondary ink | `#454944` | Body and inactive navigation                                   |
| Muted         | `#737972` | Labels, metadata, helper copy                                  |
| Hairline      | `#DDE0DA` | Primary structural border                                      |
| Relay orange  | `#F36B21` | Authority, live relay position, focused action                 |
| Relay soft    | `#FFF0E6` | Orange avatar and attention wash                               |
| Verified      | `#147A58` | Healthy, settled, verified                                     |
| Pending       | `#9A6700` | Waiting for a person or external state                         |
| Denied        | `#B33434` | Failure, refusal, suspended authority                          |
| Routing       | `#23658C` | In-flight routing and informational state                      |

Do not use decorative gradients, multicolor glows, or purple UI chrome. A dark surface is reserved for the live relay trace and sign-in narrative, where it creates focus rather than acting as a theme toggle.

## Typography

- **Display:** Trebuchet MS, falling back to Segoe UI. Use only for the brand, page titles, live narrative, and large metrics. Its humanist shapes keep the product from feeling like a generic developer dashboard.
- **Interface:** Segoe UI, falling back to Helvetica Neue and Arial. Use 10–14px in the application, with 550–700 weights for controls and labels.
- **Evidence:** Cascadia Code, falling back to Consolas and monospace. Use for transaction IDs, hashes, network labels, time, policy versions, and compact metadata only.

Page titles use tight tracking around `-0.045em`; numeric metrics use `-0.04em`. Body copy never adopts display tracking.

## Layout and rhythm

- Desktop shell: 232px fixed sidebar, 58px sticky context bar, fluid content up to 1480px.
- Page gutter: 32px desktop, 15px mobile.
- Base spacing: 4px. Common gaps: 8, 12, 14, 18, 24, 32px.
- Card radius: 11px. Control radius: 8px. Status pills are fully rounded.
- Default separation: 1px hairline. Shadows are reserved for floating mobile navigation and true overlays.
- Mobile: navigation becomes a four-action floating dock. Tables scroll horizontally. Approval actions and page actions remain thumb-sized.

## Core components

### Relay trace

A dark operational panel with a faint engineering grid. Four connected nodes describe the actual lifecycle. Complete nodes use quiet green; the single active node uses relay orange; future nodes remain neutral. Motion is limited to the live health pulse and is disabled for reduced-motion users.

### Page header

An evidence-oriented eyebrow, direct title, one-sentence purpose, one secondary action, and one primary action. Avoid more than two actions at this level.

### Metrics

Flat cards with a short colored edge at the top-right. Never use oversized icon tiles. Every metric includes comparison or scope beneath the value.

### Data tables

The dominant resource view. Use uppercase monospace headers, quiet row separators, a strong first column, compact identity avatars, and plain-language status pills. IDs are shortened visually but remain recognizable by prefix.

### Approval request

Warm, contained, and specific. It shows current limit, requested amount, and expiry before presenting the decision. Orange means review; denial remains a quiet secondary action unless the request is actively dangerous.

### Status language

Prefer outcomes people understand: `Settled`, `Verified`, `Routing`, `Review`, `Denied`, `Paused`. Avoid protocol-state names when a plain-language label exists. A dot always accompanies color so state does not depend on color alone.

## Voice

Write from the operator’s side of the screen. Use active, precise verbs: `Add agent`, `Create policy`, `Review request`, `Verify receipt`, `Save changes`. Describe what did or did not happen. Never say only that something went wrong.

Good: “Research Runner needs a one-time exception above its per-call limit.”

Avoid: “Approval required for transaction.”

## Accessibility and motion

- Minimum 2px orange keyboard focus ring with offset.
- Status is communicated by label and dot as well as color.
- Respect `prefers-reduced-motion`; no essential information depends on animation.
- Maintain at least 4.5:1 text contrast for body copy.
- Mobile controls remain at least 36px high, with primary navigation at 52px.
- Horizontal table overflow must not create page-level overflow.

## Do / do not

**Do:** show live work before analytics; keep receipt and policy context close to a transaction; use one strong action per surface; use product data as the visual interest; let whitespace separate jobs.

**Do not:** decorate with crypto motifs; use green as a generic action color; turn every state into a card; rely on large shadows; put more than one orange filled action in a local decision area; imply that connecting a wallet grants authority.
