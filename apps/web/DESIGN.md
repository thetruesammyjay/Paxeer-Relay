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

Write from the operator's point of view. Use short, active labels such as Add agent, Review request, Verify receipt, and Save changes. Say what happened and what the person can do next. Explain a technical term when it first appears.

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