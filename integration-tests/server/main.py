#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Main entry point for the integration test server."""

import logging
import os

import click
import uvicorn
from dotenv import load_dotenv

from .app import set_server_config
from .config import ServerConfig

# Load environment variables from .env file if it exists
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


@click.command()
@click.option(
    "--port",
    type=int,
    default=None,
    help="Port to run the server on (default: 8000, env: SERVER_PORT)",
)
@click.option(
    "--host",
    type=str,
    default=None,
    help="Host to bind the server to (default: 0.0.0.0, env: SERVER_HOST)",
)
@click.option(
    "--time-to-first-token-ms",
    type=float,
    default=None,
    help="Time to first token latency in milliseconds (default: 100.0, env: TIME_TO_FIRST_TOKEN_MS)",
)
@click.option(
    "--inter-token-latency-ms",
    type=float,
    default=None,
    help="Inter-token latency in milliseconds (default: 50.0, env: INTER_TOKEN_LATENCY_MS)",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default="INFO",
    help="Set the logging level",
)
def main(
    port: int | None,
    host: str | None,
    time_to_first_token_ms: float | None,
    inter_token_latency_ms: float | None,
    log_level: str,
):
    """Start the AI Performance Integration Test Server."""

    # Set logging level
    logging.getLogger().setLevel(getattr(logging, log_level))

    # Create server configuration from environment variables and CLI arguments
    config = ServerConfig.from_env_and_args(
        port=port,
        host=host,
        time_to_first_token_ms=time_to_first_token_ms,
        inter_token_latency_ms=inter_token_latency_ms,
    )

    # Set the global server configuration
    set_server_config(config)

    logger.info("Starting AI Performance Integration Test Server")
    logger.info(f"Server configuration: {config.model_dump()}")

    # Start the server
    uvicorn.run(
        "server.app:app",
        host=config.host,
        port=config.port,
        log_level=log_level.lower(),
        access_log=log_level.lower() == "debug",
        workers=100, #(os.cpu_count() or 11) - 1,
    )


if __name__ == "__main__":
    main()
