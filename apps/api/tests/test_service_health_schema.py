from __future__ import annotations

import pytest
from pydantic import ValidationError

from paxrelay_api.schemas import ServiceHealthConfig


def test_service_health_defaults_and_custom_safe_path() -> None:
    assert ServiceHealthConfig().model_dump() == {
        "endpoint": "/health",
        "interval_seconds": 30,
        "timeout_seconds": 5,
        "failure_threshold": 3,
    }
    assert (
        ServiceHealthConfig(endpoint="/readyz", timeout_seconds=2).endpoint
        == "/readyz"
    )


@pytest.mark.parametrize(
    "endpoint",
    [
        "https://other.example/health",
        "//other.example/health",
        "/health?token=value",
        "/health#fragment",
        "/../admin",
        "/health\r\nX-Header: value",
        r"\health",
    ],
)
def test_service_health_endpoint_must_be_a_local_path(endpoint: str) -> None:
    with pytest.raises(ValidationError):
        ServiceHealthConfig(endpoint=endpoint)
