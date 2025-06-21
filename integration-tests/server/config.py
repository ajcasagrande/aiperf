#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Configuration management for the integration test server."""

import os

from pydantic import BaseModel, Field


class ServerConfig(BaseModel):
    """Server configuration with environment variable and CLI argument support."""

    port: int = Field(default=8000, description="Port to run the server on")

    time_to_first_token_ms: float = Field(
        default=20.0, description="Time to first token latency in milliseconds"
    )

    inter_token_latency_ms: float = Field(
        default=5.0, description="Inter-token latency in milliseconds"
    )

    host: str = Field(default="0.0.0.0", description="Host to bind the server to")

    workers: int = Field(default=1, description="Number of worker processes")

    @classmethod
    def from_env_and_args(
        cls,
        port: int | None = None,
        time_to_first_token_ms: float | None = None,
        inter_token_latency_ms: float | None = None,
        host: str | None = None,
        workers: int | None = None,
    ) -> "ServerConfig":
        """Create config from environment variables and command line arguments.

        Command line arguments take precedence over environment variables.
        """
        # Get values from environment variables first
        env_port = os.getenv("SERVER_PORT")
        env_ttft = os.getenv("TIME_TO_FIRST_TOKEN_MS")
        env_itl = os.getenv("INTER_TOKEN_LATENCY_MS")
        env_host = os.getenv("SERVER_HOST")
        env_workers = os.getenv("SERVER_WORKERS")

        # Command line arguments override environment variables
        final_port = port if port is not None else (int(env_port) if env_port else 8000)
        final_ttft = (
            time_to_first_token_ms
            if time_to_first_token_ms is not None
            else (float(env_ttft) if env_ttft else 20.0)
        )
        final_itl = (
            inter_token_latency_ms
            if inter_token_latency_ms is not None
            else (float(env_itl) if env_itl else 5.0)
        )
        final_host = host if host is not None else (env_host if env_host else "0.0.0.0")
        final_workers = (
            workers if workers is not None else (int(env_workers) if env_workers else 1)
        )

        return cls(
            port=final_port,
            time_to_first_token_ms=final_ttft,
            inter_token_latency_ms=final_itl,
            host=final_host,
            workers=final_workers,
        )
