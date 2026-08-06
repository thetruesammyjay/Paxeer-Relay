"""Simulator configuration via pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class SimulatorSettings(BaseSettings):
    """Environment-driven settings for the local simulator."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_env: str = "development"
    log_level: str = "DEBUG"
    simulator_base_url: str = "http://localhost:8100"

    # Simulated LayerX node
    layerx_chain_id: int = 125
    layerx_block_time_ms: int = 500
    layerx_finality_blocks: int = 1  # instant finality in dev

    # Simulated Paxeer L1
    l1_block_time_ms: int = 2_000
    l1_finality_blocks: int = 3

    # Payment simulation
    payment_verify_delay_ms: int = 200
    settlement_delay_ms: int = 1_000
    failure_rate: float = 0.0  # 0.0–1.0, fraction of payments that fail in simulation


def get_settings() -> SimulatorSettings:
    """Return a fresh settings instance from the environment."""
    return SimulatorSettings()
