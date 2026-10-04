# Provider routing

`packages/provider-router` chooses a service version from candidates supplied by
the database repository. It is deterministic for a given candidate set,
constraints, metrics, strategy, and weights. It returns a route decision with
the selected provider/service/version, score breakdown, explanation, and
attempt number.

## Candidate filtering

Routing applies hard filters before scoring. A candidate must:

1. Have an active service status.
2. Belong to the active provider in the agent's environment.
3. Have a passing health flag from a real worker probe.
4. Stay at or below `maximum_price`, when one is supplied.
5. Not appear in `blocked_providers`.
6. Appear in `allowed_providers` when the allowlist is non-empty.
7. Meet `minimum_reputation` and `minimum_success_rate`, when set.
8. Stay at or below `maximum_latency_ms`, when set.
9. Support at least one required protocol, when the list is non-empty.

Capability matching happens when the repository loads eligible service
versions. If every candidate is filtered out, the router returns no decision.

## Score dimensions

Every eligible candidate receives normalised scores from 0 to 1:

| Dimension | Current calculation |
| --- | --- |
| Reputation | Provider metrics value as stored |
| Success rate | Provider metrics value as stored |
| Latency | Inverted linear score against a 5,000 ms reference; unknown/non-positive latency receives 0.5 |
| Price | Relative to `maximum_price`; an unknown price gets 0.5; without a positive maximum price the score is 1.0 |
| Availability | Provider metrics value as stored |

Balanced ranking uses weights `reputation 0.30`, `success_rate 0.25`, `latency
0.20`, `price 0.15`, and `availability 0.10`.

## Strategies

The router supports:

- `balanced` — default dimension weights above.
- `lowest_cost` — price weight 0.60, remaining weight divided across other
  dimensions.
- `lowest_latency` — latency weight 0.60.
- `highest_reputation` — reputation weight 0.70.
- `highest_availability` — availability weight 0.60.
- `sticky_session` — ranks a preferred provider first, then uses balanced
  ranking for the rest.
- `custom_weighted` — uses caller-supplied dimension weights.

The current gateway constructs `RouteRequest` without a strategy override, so
it uses `balanced`. Its `router_default_strategy` setting is not currently
passed into that request. The public invoke request supplies constraints but
does not expose the strategy or custom weights.

## Decision and explanation

The decision stores the provider ID, service ID, immutable service-version ID,
strategy, composite score, dimension breakdown, explanation, and attempt
number. Receipts copy the chosen strategy and score so operators can understand
why a provider was selected.

Publishing a service creates neutral, unmeasured routing metrics and sets its
health flag to false. It cannot receive new routes until the worker records a
successful health probe. The first availability score is the first measured
observation; later observations use the configured exponential moving
average. The service directory shows the latest health result and timestamp.
Existing rows without a recorded probe are also reset to fail closed by the
`0014_provider_health_fail_closed` migration.

An operator can set a service to `inactive` to remove it from new candidate
sets, then set it back to `active` to make it eligible again. Resuming does not
bypass the provider's active state or the passing-health requirement. Quotes
issued before a pause remain valid until their normal expiry, so those paid
requests may still complete; the pause does not revoke or refund an external
payment.

## Failover status and constraints

The router can return a ranked list internally, and the domain supports
multiple execution attempts. The gateway currently selects the first route,
creates one execution attempt, and does not try another provider after a
timeout or error. `router_max_provider_attempts` is configured but not used by
the current invoke flow.

Before enabling failover, define whether a second provider call is covered by
the same payment, how a partially completed first call is handled, and how the
receipt records multiple attempts. Never retry a paid operation without an
idempotency contract for the provider.

## Known scoring limits

- `lowest_cost` only distinguishes prices when a positive maximum-price
  constraint provides a normalisation reference. Without one, every known
  price receives a full price score.
- Custom weights are not normalised or fully validated by the router. Validate
  that supplied weights are finite, non-negative, and sum to the intended
  total before exposing them to clients.
- Routing metrics need a real measurement source and freshness rules before
  production decisions can rely on them.
