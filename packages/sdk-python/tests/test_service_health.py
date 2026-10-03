from __future__ import annotations

import pytest
from pydantic import ValidationError

from paxrelay.models import ServiceHealth


def test_service_health_config_accepts_bounded_probe_settings() -> None:
    health = ServiceHealth(
        endpoint="/readyz",
        interval_seconds=60,
        timeout_seconds=2,
        failure_threshold=4,
    )
    assert health.endpoint == "/readyz"
    assert health.timeout_seconds == 2


@pytest.mark.parametrize(
    "endpoint",
    ["https://other.example/health", "//other.example/health", "/../admin"],
)
def test_service_health_config_rejects_remote_or_traversing_paths(
    endpoint: str,
) -> None:
    with pytest.raises(ValidationError):
        ServiceHealth(endpoint=endpoint)
