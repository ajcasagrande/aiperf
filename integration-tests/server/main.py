#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Main entry point for the integration test server."""

import logging

import click
import uvicorn
from dotenv import load_dotenv

from .app import set_server_config
from .config import ConfigDefaults, ServerConfig

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
    help=f"Port to run the server on (default: {ConfigDefaults.PORT}, env: SERVER_PORT)",
)
@click.option(
    "--host",
    type=str,
    default=None,
    help=f"Host to bind the server to (default: {ConfigDefaults.HOST}, env: SERVER_HOST)",
)
@click.option(
    "--ttft",
    "--time-to-first-token-ms",
    type=float,
    default=None,
    help=f"Time to first token latency in milliseconds (default: {ConfigDefaults.TTFT_MS}, env: TTFT_MS)",
)
@click.option(
    "--itl",
    "--inter-token-latency-ms",
    type=float,
    default=None,
    help=f"Inter-token latency in milliseconds (default: {ConfigDefaults.ITL_MS}, env: ITL_MS)",
)
@click.option(
    "--workers",
    type=int,
    default=None,
    help=f"Number of worker processes (default: {ConfigDefaults.WORKERS}, env: SERVER_WORKERS)",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
    default=ConfigDefaults.LOG_LEVEL,
    help="Set the logging level",
)
def main(
    port: int | None,
    host: str | None,
    TTFT_MS: float | None,
    ITL_MS: float | None,
    workers: int | None,
    log_level: str,
):
    """Start the AI Performance Integration Test Server."""

    # Set logging level
    logging.root.setLevel(getattr(logging, log_level))

    # Create server configuration from environment variables and CLI arguments
    config = ServerConfig.from_cli_args(
        port=port,
        host=host,
        TTFT_MS=TTFT_MS,
        ITL_MS=ITL_MS,
        workers=workers,
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
        workers=config.workers,
    )


if __name__ == "__main__":
    main()
