#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""Main entry point for the integration test server."""

import logging

import typer
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

app = typer.Typer()


def create_cli_from_config():
    """Create CLI arguments dynamically from ServerConfig model."""

    def cli_wrapper(**kwargs):
        """Wrapper function that creates ServerConfig from CLI args."""

        # Extract log_level separately since it's not part of ServerConfig
        log_level = kwargs.pop("log_level", ConfigDefaults.LOG_LEVEL)

        # Map CLI parameter names to ServerConfig field names
        ttft = kwargs.pop("ttft", ConfigDefaults.TTFT_MS)
        itl = kwargs.pop("itl", ConfigDefaults.ITL_MS)

        # Set logging level
        logging.root.setLevel(getattr(logging, log_level))

        # Create server configuration from CLI arguments and environment variables
        config = ServerConfig(TTFT_MS=ttft, ITL_MS=itl, **kwargs)

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

    return cli_wrapper


@app.command()
def main(
    port: int = typer.Option(
        ConfigDefaults.PORT, help="Port to run the server on (env: SERVER_PORT)"
    ),
    host: str = typer.Option(
        ConfigDefaults.HOST, help="Host to bind the server to (env: SERVER_HOST)"
    ),
    ttft: float = typer.Option(
        ConfigDefaults.TTFT_MS,
        "--ttft",
        "--time-to-first-token-ms",
        help="Time to first token latency in milliseconds (env: TTFT_MS)",
    ),
    itl: float = typer.Option(
        ConfigDefaults.ITL_MS,
        "--itl",
        "--inter-token-latency-ms",
        help="Inter-token latency in milliseconds (env: ITL_MS)",
    ),
    workers: int = typer.Option(
        ConfigDefaults.WORKERS, help="Number of worker processes (env: SERVER_WORKERS)"
    ),
    log_level: str = typer.Option(
        ConfigDefaults.LOG_LEVEL, help="Set the logging level"
    ),
):
    """Start the AI Performance Integration Test Server."""
    create_cli_from_config()(
        port=port,
        host=host,
        ttft=ttft,
        itl=itl,
        workers=workers,
        log_level=log_level,
    )


if __name__ == "__main__":
    app()
