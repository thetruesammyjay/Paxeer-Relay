"""Provider request forwarding.

Forwards an authorised request to the selected service version's endpoint,
bounded by the service's delivery timeout. Classifies the outcome into a
domain ``ExecutionState`` and captures timing for the receipt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from paxrelay_domain import ExecutionState


@dataclass
class ForwardResult:
    """Outcome of a single forward attempt to a provider."""

    execution_state: ExecutionState
    http_status_code: int | None
    response_body: dict[str, Any] | None
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
    client: httpx.AsyncClient | None = None,
) -> ForwardResult:
    """POST the tool-call arguments to the provider endpoint.

    A caller-supplied ``client`` (e.g. one wired with httpx.MockTransport in
    tests) is used when provided; otherwise a fresh client is created.
    """
    started = datetime.utcnow()
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=timeout_seconds)

    try:
        resp = await client.post(endpoint_url, json=arguments)
        completed = datetime.utcnow()
        latency_ms = int((completed - started).total_seconds() * 1000)
        body: dict[str, Any] | None
        try:
            body = resp.json()
        except Exception:
            body = None

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
            response_bytes=resp.content,
            started_at=started,
            completed_at=completed,
            latency_ms=latency_ms,
            error_code=error_code,
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
        if owns_client:
            await client.aclose()
