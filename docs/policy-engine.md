# Policy engine

The policy engine is a deterministic Python package in
`packages/policy-engine`. It evaluates a payment request against an immutable
policy model and returns a decision, matched rule names, policy version, and a
human-readable explanation. The evaluator has no database or network side
effects.

## Evaluation input

The evaluator receives:

- agent ID and current agent status;
- requested capability and selected provider ID;
- requested amount and currency;
- current daily and monthly spend;
- provider reputation, success rate, and average latency;
- the agent's completed provider attempts since its last successful attempt;
- emergency-stop and session-validity flags.

Monetary values use integer atomic amounts, not floating point.

## Evaluation order

Rules run in this order:

1. Agent status must be active.
2. Emergency stop must be off.
3. Session must be valid.
4. Capability must match `allowed_capabilities` (glob patterns such as
   `research.*` are supported; an empty list allows all capabilities).
5. Provider must not be blocked and must match the allowlist when one exists.
6. Currency must match `allowed_currencies` when configured.
7. Amount must not exceed `maximum_per_call`.
8. Current daily spend plus this amount must not exceed `daily_budget`.
9. Current monthly spend plus this amount must not exceed `monthly_budget`.
10. Provider reputation, success rate, and latency must meet configured
    thresholds.
11. Consecutive failures must be below the configured limit.
12. Amounts at or above `approval_threshold` require approval.

In `enforce` mode the evaluator stops at the first blocking rule. In `observe`
and `warn`, a triggered rule is reported but the final decision is `allow`.
Use `enforce` for any action whose policy must block payment.

## Decisions

| Decision | Meaning | Gateway behavior today |
| --- | --- | --- |
| `allow` | Request passes the active policy. | Continues to quote creation. |
| `deny` | A rule blocks the request. | Returns HTTP 403 with decision and explanation. |
| `require_approval` | A rule requires review. | Persists a tenant-scoped approval request and returns HTTP 202 with its ID. A key with `approvals:write` can approve or reject; the agent must retry the same request after approval. Decisions are attributed to an API key, not an individual dashboard user. |
| `pause_agent` | Emergency or failure rule requests a pause. | Returned as a policy result; durable agent pausing is not performed by the evaluator. |

## Policy model versus API schema

The domain `PolicyRules` model includes per-call, daily, and monthly amounts;
capability/provider lists; allowed contracts; provider quality thresholds;
approval threshold; failure/drawdown fields; session expiry; and currency
restrictions.

The control-plane `PolicyCreate` request supports mode, per-call/daily/monthly
amounts, capability/provider allow/block lists, provider reputation and success
thresholds, maximum average latency, a maximum consecutive-failures threshold,
and an approval threshold. Provider thresholds are evaluated against the
selected service's indexed metrics. Failure limits use completed provider
attempts after the agent's latest successful attempt; they exclude requests
that failed before contacting a provider and attempts that are still running.
Once reached, the rule blocks subsequent requests. Since blocked requests do
not create a provider attempt, the operator must assign a policy without this
limit to restore calls.
`allowed_contracts`, `maximum_drawdown`, `session_expiry_seconds`, and currency
restrictions remain unavailable through policy creation; allowed contracts,
drawdown, and session expiry are also not evaluated by the current rule
sequence.

The gateway defaults to session-valid and emergency-stop-off when no account
session source is configured. It loads spend totals, provider metrics, and
recent completed provider failure history. Account session proof is not yet
connected to the request.

## Gateway integration

For each invocation, the gateway selects a service first, then evaluates the
assigned active policy against that service's actual price and metrics. This
ensures a policy sees the proposed amount and provider. No active policy means
the gateway returns HTTP 403.

The API stores the policy explanation and binds the approval to the route,
amount, recipient, and policy version. The operator console can create
policies, inspect their stored rules, and assign them to agents through the
scoped API-key flow. Individual dashboard-user authentication is not yet
implemented; a dashboard key identifies the project, not the person using it.

## Changes and validation

Keep evaluation order stable and documented. For each new rule:

1. Add a pure rule function and insert it explicitly into `RULE_SEQUENCE`.
2. Define behavior for `observe`, `warn`, and `enforce`.
3. Add a stable rule name and plain-language explanation.
4. Update request models, control-plane schemas, and API documentation if the
   rule is configurable.
5. Check that amount comparisons use matching currencies and decimal units.
