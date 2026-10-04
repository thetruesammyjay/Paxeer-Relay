# PaxRelay Python SDK

The Python SDK provides an async client for the control-plane API. It can
register and inspect agents and providers, publish and manage service routing,
configure spend policies, review approvals, read receipt and transaction
history, and verify signed execution receipts.

## Install

From the repository root, sync the workspace:

```powershell
uv sync --all-packages
```

When using the SDK from another project, install the built `paxrelay` package
from the package registry used by your team.

## Connect to the API

Create an API key with the required scopes. Agent creation needs
`agents:write`; agent lookup needs `agents:read`. Provider and service
operations similarly need `providers:read` or `providers:write`, and
`services:read` or `services:write`. Policy creation and assignment need
`policies:write`; listing and lookup need `policies:read`.

```python
import asyncio
import os

from paxrelay import AsyncPaxRelayClient


async def main() -> None:
    async with AsyncPaxRelayClient(
        base_url="http://localhost:8000",
        api_key=os.environ["PAXRELAY_API_KEY"],
    ) as client:
        agent = await client.agents.create(
            name="Research Runner",
            slug="research-runner",
        )
        print(agent.id, agent.status)

        agents = await client.agents.list(status="active", limit=25)
        print(f"Found {len(agents)} agents")


asyncio.run(main())
```

The `base_url` can be the API origin or an API URL that already ends in `/v1`.
The SDK sends the API key as a bearer token and does not log or retry it.
Use HTTPS for remote APIs. The client closes its HTTP connection pool when
the `async with` block ends.

## Register a provider and publish a service

```python
from paxrelay import ServiceHealth


async def publish_example(client):
    provider = await client.providers.create(
        name="Example Research",
        slug="example-research",
        website_url="https://provider.example",
    )

    service = await client.services.publish(
        provider.id,
        name="Market Snapshot",
        slug="market-snapshot",
        capability="research.market-snapshot",
        price_amount_atomic=24_000,
        base_url="https://provider.example",
        endpoint_url="https://provider.example/api/snapshot",
        protocols=("http",),
        version="1.0.0",
        health=ServiceHealth(
            endpoint="/health",
            interval_seconds=30,
            timeout_seconds=3,
            failure_threshold=3,
        ),
    )
    print(service.id, service.price_per_call)
```

The API verifies that the provider belongs to the current tenant. In a
production tenant, the provider must have a wallet address and the service
URLs must meet the API's production HTTPS rules.

Pause or resume a service with a `services:write` key:

```python
paused = await client.services.pause(service.id)
resumed = await client.services.resume(paused.id)
```

Pausing prevents new routes. An already-issued, unexpired quote may still
complete while the provider remains active and its health check passes.
PaxRelay cannot reverse a payment already sent through an external network.

## Set a spending policy

```python
async def configure_agent_policy(client, agent, provider_id):
    policy = await client.policies.create(
        name="Research limits",
        mode="enforce",
        maximum_per_call_atomic=250_000,
        daily_budget_atomic=1_000_000,
        approval_threshold_atomic=100_000,
        allowed_capabilities=["research.*"],
        blocked_providers=[str(provider_id)],
        minimum_provider_reputation=0.7,
        minimum_provider_success_rate=0.9,
        maximum_accepted_latency_ms=2_000,
        maximum_consecutive_failures=3,
    )
    assignment = await client.policies.assign(policy.id, agent_id=agent.id)
    detail = await client.policies.get(policy.id)
    return policy, assignment, detail
```

Amounts use USDX atomic units with six decimal places. For example,
`250_000` means `0.25 USDX`. Provider reputation and success thresholds use a
0 to 1 scale; maximum latency is in milliseconds and is compared with the
selected service's indexed average. The failure limit counts completed
provider attempts since the agent's last successful attempt. Once the limit is
reached, assign a policy without the limit to restore calls. `create()` and
`list()` return policy metadata; `get()` returns a `PolicyDetail` with all
configured rules and agent assignments. Provider allow/block lists contain
provider UUIDs.

## Review approval requests

List pending requests and record an approval or rejection. Reading requests
needs `approvals:read`; decisions need `approvals:write`.

```python
async def review_pending(client):
    requests = await client.approvals.list(status="pending", limit=25)
    if not requests:
        return None

    request = requests[0]
    return await client.approvals.approve(
        request.id,
        reason="The requested service and amount match the review policy.",
    )
```

Use `client.approvals.reject(...)` to reject a request, or
`client.approvals.decide(...)` when the decision is selected dynamically. The
decision API accepts an optional reason of up to 512 characters. Repeating the
same decision is safe; a different decision for an already decided request
raises `ConflictError`. The API records the decision against the API key, so
this SDK operation does not identify an individual dashboard user.

## Read transaction history

Use the `transactions:read` scope to list transaction summaries. The API
supports filtering by agent, request state, payment state, and creation time.

```python
from datetime import UTC, datetime, timedelta

async def recent_agent_transactions(client, agent_id):
    return await client.transactions.list(
        agent_id=agent_id,
        created_after=datetime.now(UTC) - timedelta(days=7),
        limit=25,
    )
```

The route returns request, payment, and execution states with timestamps. The
control-plane client does not create transactions; paid invocation and proof
submission use the separate gateway client described below.

## Invoke a paid service through the gateway

The gateway client starts an invocation and returns the 402LXP payment
requirement. Your application or wallet integration handles the payment and
passes the resulting proof back to PaxRelay. The SDK does not hold wallet keys,
sign transfers, or initiate payments. Use a key with the `gateway:invoke`
scope and an agent ID that belongs to the key's tenant.

```python
from paxrelay import (
    AsyncPaxRelayGatewayClient,
    GatewayCallResult,
    PaymentChallenge,
)

async def call_paid_service(api_key, agent_id, wallet):
    async with AsyncPaxRelayGatewayClient(
        base_url="http://localhost:8080",
        api_key=api_key,
        agent_id=agent_id,
    ) as gateway:
        started = await gateway.invoke(
            capability="research.web-search",
            idempotency_key="search-2026-10-03-001",
            arguments={"query": "Paxeer Network"},
        )

        if isinstance(started, PaymentChallenge):
            proof = await wallet.create_payment_proof(started.payment_requirement)
            return await gateway.submit_proof(started.tool_call_id, proof=proof)
        if isinstance(started, GatewayCallResult):
            return started  # An idempotent replay of a completed call.
        return started  # Policy requires human approval.
```

`invoke()` can return a `PaymentChallenge`, a completed `GatewayCallResult` for
an idempotent replay, or `ApprovalPending`. `submit_proof()` returns the
provider result and signed receipt. Verification failures, expired quotes,
policy denials, and gateway errors raise the corresponding SDK API exception.
The client does not automatically retry requests or submit payment proofs.

## Read spend analytics

Use the `analytics:read` scope to read committed-spend totals or totals grouped
by service capability. Both methods accept optional `start_date` and
`end_date` values and default to the last 30 days when no range is provided.

```python
from datetime import UTC, datetime, timedelta

async def review_spend(client):
    start = datetime.now(UTC) - timedelta(days=30)
    total = await client.analytics.spend(
        period="monthly",
        start_date=start,
    )
    by_capability = await client.analytics.capabilities(
        start_date=start,
        limit=10,
    )
    return total, by_capability
```

`spend()` returns one aggregate for the date range, with a `daily` or `monthly`
period label. It does not return a time series. Amounts use the currency and
decimal count returned by the API (currently USDX with six decimals).

## Handle API errors

API errors include their HTTP status, machine-readable code, and request ID
when the API supplies one. Common failures have dedicated exception classes:

```python
from paxrelay import (
    AuthenticationError,
    PaxRelayAPIError,
    PaxRelayConnectionError,
    PermissionDeniedError,
    RateLimitError,
)

async def list_agents_safely(client):
    try:
        agents = await client.agents.list()
    except AuthenticationError:
        print("Check the API key")
    except PermissionDeniedError:
        print("The key needs agents:read")
    except RateLimitError as exc:
        print("Retry after", exc.retry_after_seconds, "seconds")
    except PaxRelayConnectionError:
        print("The API could not be reached")
    except PaxRelayAPIError as exc:
        print(exc.status_code, exc.code, exc.request_id)
```

## Read receipt history

Use the `receipts:read` scope to list execution receipt summaries. Results can
be filtered by agent or tool-call ID.

```python
async def receipts_for_agent(client, agent_id):
    return await client.receipts.list(agent_id=agent_id, limit=25)
```

This endpoint returns summary fields for review and pagination. It does not
return the full canonical receipt payload required by `verify_receipt`.

## Receipt verification

The SDK also exposes `fetch_receipt_keyring(url)` and `verify_receipt(receipt,
keyring)`. See [the receipt guide](../../docs/execution-receipts.md) for the
manifest format and verification limits.

## Current scope

The client covers tenant-scoped agent, provider, service, policy, approval,
receipt-history, transaction-history, and spend-analytics read operations. It
does not yet implement transaction mutations, gateway invocation, or payment
methods. Create and use keys through the API's documented bootstrap and
key-management processes.
