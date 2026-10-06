"""Provision and run one clearly simulated paid-request flow on localhost.

The API key must come from local development bootstrap and the gateway must
use USE_MOCK_ADAPTER=true. The script constructs a mock proof; it never touches
a wallet, submits a LayerX activity, or contacts a public provider.
"""

from __future__ import annotations

import json
import os
import sys
import time
import uuid
from ipaddress import ip_address
from typing import BinaryIO
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
PRICE_ATOMIC = 1_000


class DemoFailure(RuntimeError):
    """A safe local-demo failure message."""


def main() -> int:
    api_key = os.environ.get("PAXRELAY_API_KEY", "")
    if not api_key:
        return _fail("set PAXRELAY_API_KEY to a local development bootstrap key")
    try:
        api = _local_origin(
            os.environ.get("PAXRELAY_API_URL", "http://127.0.0.1:8000")
        )
        gateway = _local_origin(
            os.environ.get("PAXRELAY_GATEWAY_URL", "http://127.0.0.1:8001")
        )
        simulator = _local_origin(
            os.environ.get("PAXRELAY_SIMULATOR_URL", "http://127.0.0.1:8100")
        )
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        suffix = uuid.uuid4().hex[:10]
        agent = _api_json(
            "POST",
            api,
            "/v1/agents",
            headers,
            {
                "name": "Local paid-request demo",
                "slug": f"local-paid-demo-{suffix}",
                "description": "Development-only simulated 402LXP request.",
            },
        )
        provider = _api_json(
            "POST",
            api,
            "/v1/providers",
            headers,
            {
                "name": "PaxRelay local demo provider",
                "slug": f"local-demo-provider-{suffix}",
                "description": "A deterministic local provider; no internet access.",
            },
        )
        service = _api_json(
            "POST",
            api,
            f"/v1/services/providers/{provider['id']}",
            headers,
            {
                "name": "Local demo search",
                "slug": f"local-demo-search-{suffix}",
                "capability": "research.web-search",
                "protocols": ["http"],
                "price_per_call": {
                    "amount_atomic": PRICE_ATOMIC,
                    "currency": "USDX",
                    "decimals": 6,
                },
                "base_url": simulator,
                "endpoint_url": f"{simulator}/demo-provider/search",
                "health": {
                    "endpoint": "/health",
                    "interval_seconds": 5,
                    "timeout_seconds": 3,
                    "failure_threshold": 3,
                },
                "version": "1.0.0",
                "description": "A deterministic local provider for the demo.",
            },
        )
        policy = _api_json(
            "POST",
            api,
            "/v1/policies",
            headers,
            {
                "name": f"Local demo policy {suffix}",
                "description": "Allows the single low-cost local demo capability.",
                "mode": "enforce",
                "maximum_per_call": _money(PRICE_ATOMIC),
                "daily_budget": _money(100_000),
                "allowed_capabilities": ["research.web-search"],
            },
        )
        _api_json(
            "POST",
            api,
            f"/v1/policies/{policy['id']}/assign",
            headers,
            {"agent_id": agent["id"]},
        )

        _wait_for_healthy_service(api, headers, service["id"])
        gateway_headers = {
            **headers,
            "X-Agent-Id": agent["id"],
        }
        idempotency_key = f"local-demo-{uuid.uuid4().hex}"
        status, challenge_bytes = _request(
            "POST",
            f"{gateway}/v1/invoke",
            gateway_headers,
            {
                "capability": "research.web-search",
                "idempotency_key": idempotency_key,
                "arguments": {"query": "PaxRelay local paid-request demo"},
            },
        )
        if status != 402:
            raise DemoFailure(f"expected_http_402_received_{status}")
        challenge = _decode_object(challenge_bytes)
        requirement = challenge.get("payment_requirement")
        tool_call_id = challenge.get("tool_call_id")
        if not isinstance(requirement, dict) or not isinstance(tool_call_id, str):
            raise DemoFailure("gateway_returned_invalid_local_demo_challenge")

        # These claims only satisfy the mock adapter's local shape checks.
        # They are not LayerX signatures, receipts, or payment evidence.
        proof = {
            "quote_id": requirement["quote_id"],
            "request_hash": requirement["request_hash"],
            "amount_atomic": requirement["amount_atomic"],
            "recipient": requirement["recipient"],
            "nonce": requirement["nonce"],
            "chain_id": requirement["chain_id"],
            "payment_scheme": requirement["payment_scheme"],
        }
        complete_status, result_bytes = _request(
            "POST",
            f"{gateway}/v1/invoke/{tool_call_id}",
            gateway_headers,
            {"proof": json.dumps(proof, separators=(",", ":"))},
        )
        if not 200 <= complete_status < 300:
            raise DemoFailure(f"completion_failed_http_{complete_status}")
        result = _decode_object(result_bytes)
        print(
            json.dumps(
                {
                    "mode": "SIMULATED_ONLY",
                    "payment_submitted": False,
                    "agent_id": agent["id"],
                    "provider_id": provider["id"],
                    "service_id": service["id"],
                    "policy_id": policy["id"],
                    "provider_result_and_receipt": result,
                },
                indent=2,
            )
        )
        return 0
    except DemoFailure as exc:
        return _fail(str(exc))
    except (KeyError, TypeError, ValueError):
        return _fail("service_response_was_not_a_valid_demo_payload")
    except OSError:
        return _fail("a_local_service_request_failed; check its health and logs")


def _local_origin(value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or not _is_loopback(parsed.hostname or "")
    ):
        raise DemoFailure("api_gateway_and_simulator_urls_must_be_loopback_http")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def _api_json(
    method: str,
    origin: str,
    path: str,
    headers: dict[str, str],
    body: dict[str, object] | None,
) -> dict[str, object]:
    status, response_bytes = _request(
        method,
        f"{origin}{path}",
        headers,
        body,
    )
    if not 200 <= status < 300:
        raise DemoFailure(f"control_plane_{path.replace('/', '_')}_http_{status}")
    return _decode_object(response_bytes)


def _wait_for_healthy_service(
    api: str,
    headers: dict[str, str],
    service_id: str,
) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        service = _api_json(
            "GET", api, f"/v1/services/{service_id}", headers, None
        )
        health = service.get("health")
        if isinstance(health, dict) and health.get("last_check_passing") is True:
            return
        if isinstance(health, dict) and health.get("last_check_passing") is False:
            time.sleep(2)
            continue
        time.sleep(2)
    raise DemoFailure("provider_health_probe_did_not_pass; is the worker running?")


def _request(
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, object] | None,
) -> tuple[int, bytes]:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8") if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.status, _bounded_read(response)
    except HTTPError as response:
        return response.code, _bounded_read(response)


def _bounded_read(response: BinaryIO) -> bytes:
    body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise DemoFailure("local_service_response_exceeded_2_mib")
    return body


def _decode_object(body: bytes) -> dict[str, object]:
    decoded = json.loads(body)
    if not isinstance(decoded, dict):
        raise DemoFailure("local_service_response_was_not_an_object")
    return decoded


def _money(amount_atomic: int) -> dict[str, object]:
    return {"amount_atomic": amount_atomic, "currency": "USDX", "decimals": 6}


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _fail(message: str) -> int:
    print(json.dumps({"mode": "SIMULATED_ONLY", "error": message}), file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
