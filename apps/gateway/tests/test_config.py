from __future__ import annotations

import pytest

from paxrelay_gateway.config import GatewaySettings


def test_staging_rejects_mock_adapter() -> None:
    with pytest.raises(ValueError, match="USE_MOCK_ADAPTER"):
        GatewaySettings(
            app_env="staging",
            use_mock_adapter=True,
            paxeer_network_environment="staging",
            provider_endpoint_host_allowlist="provider.staging.example",
        )


def test_staging_requires_provider_host_allowlist() -> None:
    with pytest.raises(ValueError, match="PROVIDER_ENDPOINT_HOST_ALLOWLIST"):
        GatewaySettings(
            app_env="staging",
            use_mock_adapter=True,
            paxeer_network_environment="staging",
        )


def test_staging_rejects_mainnet_network_label() -> None:
    with pytest.raises(ValueError, match="PAXEER_NETWORK_ENVIRONMENT"):
        GatewaySettings(
            app_env="staging",
            use_mock_adapter=False,
            paxeer_network_environment="mainnet",
            provider_endpoint_host_allowlist="provider.staging.example",
        )


def test_staging_requires_staging_endpoint_configuration() -> None:
    with pytest.raises(ValueError, match="LAYERX_API_URL"):
        GatewaySettings(
            app_env="staging",
            use_mock_adapter=False,
            paxeer_network_environment="staging",
            provider_endpoint_host_allowlist="provider.staging.example",
            paxeer_rpc_url="https://rpc.staging.example",
        )

    with pytest.raises(ValueError, match="PAXEER_RPC_URL"):
        GatewaySettings(
            app_env="staging",
            use_mock_adapter=False,
            paxeer_network_environment="staging",
            provider_endpoint_host_allowlist="provider.staging.example",
            layerx_api_url="https://layerx.staging.example",
        )

    GatewaySettings(
        app_env="staging",
        use_mock_adapter=False,
        paxeer_network_environment="staging",
        provider_endpoint_host_allowlist="provider.staging.example",
        layerx_api_url="https://layerx.staging.example",
        paxeer_rpc_url="https://rpc.staging.example",
    )
