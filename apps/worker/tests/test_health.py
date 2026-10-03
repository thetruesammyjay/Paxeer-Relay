from __future__ import annotations

from datetime import UTC, datetime

import pytest

from paxrelay_worker.config import WorkerSettings
from paxrelay_worker.jobs.health import (
    _bounded_int,
    _health_url,
    _normalise_hostname,
    _parse_timestamp,
)


@pytest.mark.parametrize(
    ("base_url", "endpoint", "expected"),
    [
        (
            "https://provider.example/api",
            "/health",
            "https://provider.example/health",
        ),
        ("http://localhost:8080", "/ready", "http://localhost:8080/ready"),
    ],
)
def test_health_url_stays_on_service_host(
    base_url: str, endpoint: str, expected: str
) -> None:
    assert _health_url(base_url, endpoint) == expected


@pytest.mark.parametrize(
    ("base_url", "endpoint"),
    [
        ("https://provider.example", "//attacker.example/health"),
        ("https://provider.example", "https://attacker.example/health"),
        ("https://user:secret@provider.example", "/health"),
        ("https://provider.example?target=elsewhere", "/health"),
        ("https://provider.example", "/../admin"),
        ("https://provider.example", "/health?token=secret"),
    ],
)
def test_health_url_rejects_unsafe_targets(base_url: str, endpoint: str) -> None:
    with pytest.raises(ValueError):
        _health_url(base_url, endpoint)


def test_health_values_are_bounded_and_timestamps_normalized() -> None:
    assert _bounded_int("60", default=30, minimum=5, maximum=45) == 45
    assert _bounded_int("not-an-int", default=30, minimum=5, maximum=45) == 30
    assert _parse_timestamp("2026-10-02T12:00:00Z") == datetime(
        2026, 10, 2, 12, tzinfo=UTC
    ).replace(tzinfo=None)
    assert _parse_timestamp(None) is None


def test_hostname_normalization_uses_lowercase_idna() -> None:
    assert _normalise_hostname("B\u00fccher.example.") == "xn--bcher-kva.example"


def test_staging_requires_an_explicit_host_allowlist_and_non_mock_adapter() -> None:
    with pytest.raises(ValueError, match="PROVIDER_ENDPOINT_HOST_ALLOWLIST"):
        WorkerSettings(app_env="staging", use_mock_adapter=True)

    with pytest.raises(ValueError, match="USE_MOCK_ADAPTER"):
        WorkerSettings(
            app_env="staging",
            use_mock_adapter=True,
            paxeer_network_environment="staging",
            provider_endpoint_host_allowlist="provider.staging.example",
        )

    with pytest.raises(ValueError, match="PAXEER_NETWORK_ENVIRONMENT"):
        WorkerSettings(
            app_env="staging",
            use_mock_adapter=False,
            paxeer_network_environment="mainnet",
            provider_endpoint_host_allowlist="provider.staging.example",
            layerx_api_url="https://layerx.staging.example",
            paxeer_settlement_api_url="https://settlement.staging.example",
        )

    settings = WorkerSettings(
        app_env="staging",
        use_mock_adapter=False,
        paxeer_network_environment="staging",
        paxeer_rpc_url="https://rpc.staging.example",
        provider_endpoint_host_allowlist="PROVIDER.staging.example.",
        layerx_api_url="https://layerx.staging.example",
        paxeer_settlement_api_url="https://settlement.staging.example",
        paxeer_l1_settlement_contract_address="0x" + "1" * 40,
        paxeer_l1_commitment_event_topic="0x" + "a" * 64,
        paxeer_l1_confirmation_blocks=2,
    )
    assert settings.provider_endpoint_hosts == frozenset(
        {"provider.staging.example"}
    )
