# PaxRelay Python SDK

The Python SDK provides an async client for the control-plane API. It can
register and inspect agents and providers, publish services, configure spend
policies, review approvals, and verify signed execution receipts.

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
    )
    print(service.id, service.price_per_call)
```

The API verifies that the provider belongs to the current tenant. In a
production tenant, the provider must have a wallet address and the service
URLs must meet the API's production HTTPS rules.

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
    )
    assignment = await client.policies.assign(policy.id, agent_id=agent.id)
    return policy, assignment
```

Amounts use USDX atomic units with six decimal places. For example,
`250_000` means `0.25 USDX`. The API returns policy metadata and assignment
details, but the current policy read routes do not return the stored rule
configuration. Provider allow/block lists contain provider UUIDs.

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

## Receipt verification

The SDK also exposes `fetch_receipt_keyring(url)` and `verify_receipt(receipt,
keyring)`. See [the receipt guide](../../docs/execution-receipts.md) for the
manifest format and verification limits.

## Current scope

The client covers tenant-scoped agent, provider, service, policy, and approval
operations. It does not yet implement transaction, gateway invocation, or
payment methods. Create and use keys through the API's documented bootstrap
and key-management processes.
