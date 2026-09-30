"""Provider request forwarding.

Forwards an authorised request to the selected service version's endpoint,
bounded by the service's delivery timeout. Classifies the outcome into a
domain ``ExecutionState`` and captures timing for the receipt.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from paxrelay_domain import ExecutionState
from paxrelay_gateway.proxy.endpoint_security import (
    PinnedAddressBackend,
    ProviderEndpointResolutionTimeout,
    ResolvedProviderEndpoint,
    UnsafeProviderEndpoint,
    resolve_provider_endpoint,
)


@dataclass
class ForwardResult:
    """Outcome of a single forward attempt to a provider."""

    execution_state: ExecutionState
    http_status_code: int | None
    response_body: Any | None
    response_bytes: bytes
    started_at: datetime
    completed_at: datetime
    latency_ms: int
    error_code: str | None = None


async def forward_request(
    *,
    endpoint_url: str,
    arguments: dict[str, Any],
    timeout_seconds: int = 30,
    connect_timeout_seconds: int = 5,
    max_response_bytes: int = 10_485_760,
    allow_private_endpoints: bool = False,
    allowed_provider_hosts: frozenset[str] | None = None,
    client: httpx.AsyncClient | None = None,
) -> ForwardResult:
    """POST the tool-call arguments to the provider endpoint.

    A caller-supplied ``client`` is a trusted transport hook for tests. Normal
    gateway requests resolve and pin the provider address for this connection.
    """
    started = datetime.utcnow()
    owns_client = client is None

    try:
        if client is None:
            endpoint = await resolve_provider_endpoint(
                endpoint_url,
                allow_private=allow_private_endpoints,
                timeout_seconds=min(connect_timeout_seconds, timeout_seconds),
                allowed_hosts=allowed_provider_hosts,
            )
            transport = _pinned_transport(endpoint)
            client = httpx.AsyncClient(
                timeout=timeout_seconds,
                follow_redirects=False,
                trust_env=False,
                transport=transport,
            )

        async with client.stream(
            "POST",
            endpoint_url,
            json=arguments,
            follow_redirects=False,
            timeout=httpx.Timeout(
                timeout_seconds,
                connect=min(connect_timeout_seconds, timeout_seconds),
            ),
        ) as resp:
            chunks: list[bytes] = []
            response_size = 0
            async for chunk in resp.aiter_bytes():
                response_size += len(chunk)
                if response_size > max_response_bytes:
                    completed = datetime.utcnow()
                    return ForwardResult(
                        execution_state=ExecutionState.UNKNOWN,
                        http_status_code=resp.status_code,
                        response_body=None,
                        response_bytes=b"",
                        started_at=started,
                        completed_at=completed,
                        latency_ms=int((completed - started).total_seconds() * 1000),
                        error_code="response_too_large",
                    )
                chunks.append(chunk)

            response_bytes = b"".join(chunks)
            try:
                body: Any = json.loads(response_bytes)
            except (json.JSONDecodeError, UnicodeDecodeError):
                body = None

            completed = datetime.utcnow()
            latency_ms = int((completed - started).total_seconds() * 1000)
            if 200 <= resp.status_code < 300:
                state = ExecutionState.SUCCEEDED
                error_code = None
            else:
                state = ExecutionState.PROVIDER_ERROR
                error_code = f"http_{resp.status_code}"

            return ForwardResult(
                execution_state=state,
                http_status_code=resp.status_code,
                response_body=body,
                response_bytes=response_bytes,
                started_at=started,
                completed_at=completed,
                latency_ms=latency_ms,
                error_code=error_code,
            )
    except ProviderEndpointResolutionTimeout:
        completed = datetime.utcnow()
        return ForwardResult(
            execution_state=ExecutionState.TIMEOUT,
            http_status_code=None,
            response_body=None,
            response_bytes=b"",
            started_at=started,
            completed_at=completed,
            latency_ms=int((completed - started).total_seconds() * 1000),
            error_code="dns_timeout",
        )
    except UnsafeProviderEndpoint:
        completed = datetime.utcnow()
        return ForwardResult(
            execution_state=ExecutionState.PROVIDER_ERROR,
            http_status_code=None,
            response_body=None,
            response_bytes=b"",
            started_at=started,
            completed_at=completed,
            latency_ms=int((completed - started).total_seconds() * 1000),
            error_code="unsafe_provider_endpoint",
        )
    except httpx.TimeoutException:
        completed = datetime.utcnow()
        return ForwardResult(
            execution_state=ExecutionState.TIMEOUT,
            http_status_code=None,
            response_body=None,
            response_bytes=b"",
            started_at=started,
            completed_at=completed,
            latency_ms=int((completed - started).total_seconds() * 1000),
            error_code="timeout",
        )
    except httpx.HTTPError:
        completed = datetime.utcnow()
        return ForwardResult(
            execution_state=ExecutionState.UNKNOWN,
            http_status_code=None,
            response_body=None,
            response_bytes=b"",
            started_at=started,
            completed_at=completed,
            latency_ms=int((completed - started).total_seconds() * 1000),
            error_code="connection_error",
        )
    finally:
        if owns_client and client is not None:
            await client.aclose()


def _pinned_transport(endpoint: ResolvedProviderEndpoint) -> httpx.AsyncHTTPTransport:
    """Build an HTTPX transport whose sockets use only prevalidated IPs."""
    transport = httpx.AsyncHTTPTransport(trust_env=False, retries=0)
    # HTTPX does not expose httpcore's network backend in its public transport
    # constructor. Keep this compatibility check fail-closed if that changes.
    pool = getattr(transport, "_pool", None)
    if pool is None or not hasattr(pool, "_network_backend"):
        raise RuntimeError("HTTPX transport cannot enforce pinned provider addresses")
    pool._network_backend = PinnedAddressBackend(endpoint)
    return transport
