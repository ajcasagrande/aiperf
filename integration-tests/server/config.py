#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Configuration management for the integration test server."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigDefaults:
    """Centralized configuration defaults for the integration test server."""

    # Server settings
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    WORKERS: int = 1

    # Timing settings
    TTFT_MS: float = 20.0
    ITL_MS: float = 5.0

    # Logging settings
    LOG_LEVEL: str = "INFO"


class ServerConfig(BaseSettings):
    """Server configuration with automatic environment variable support."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    port: int = Field(
        default=ConfigDefaults.PORT,
        description="Port to run the server on",
        validation_alias="SERVER_PORT",
    )

    TTFT_MS: float = Field(
        default=ConfigDefaults.TTFT_MS,
        description="Time to first token latency in milliseconds",
    )

    ITL_MS: float = Field(
        default=ConfigDefaults.ITL_MS, description="Inter-token latency in milliseconds"
    )

    host: str = Field(
        default=ConfigDefaults.HOST,
        description="Host to bind the server to",
        validation_alias="SERVER_HOST",
    )

    workers: int = Field(
        default=ConfigDefaults.WORKERS,
        description="Number of worker processes",
        validation_alias="SERVER_WORKERS",
    )

    @classmethod
    def from_cli_args(cls, **cli_args) -> "ServerConfig":
        """Create config from CLI arguments, with automatic environment variable fallback.

        CLI arguments override environment variables which override defaults.
        """
        # Filter out None values from CLI args and create the config
        # BaseSettings will automatically handle environment variables
        filtered_args = {k: v for k, v in cli_args.items() if v is not None}
        return cls(**filtered_args)
