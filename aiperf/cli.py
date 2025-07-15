# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Main CLI entry point for the AIPerf system."""

import logging
import sys
from pathlib import Path

import cyclopts
from rich.console import Console
from rich.logging import RichHandler

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.config import CLIConfig, ServiceConfig
from aiperf.common.config.config_defaults import ServiceDefaults
from aiperf.common.config.user_config import UserConfig
from aiperf.services import SystemController

logger = AIPerfLogger(__name__)

app = cyclopts.App(name="aiperf", help="NVIDIA AIPerf")


def _setup_logging(service_config: ServiceConfig | None = None) -> None:
    """Set up rich logging with appropriate configuration."""
    # Set logging level for the root logger (affects all loggers)
    level = (
        service_config.log_level.upper()
        if service_config
        else ServiceDefaults.LOG_LEVEL.upper()
    )
    logging.root.setLevel(level)

    rich_handler = RichHandler(
        rich_tracebacks=True,
        show_path=True,
        console=Console(),
        tracebacks_show_locals=False,
        log_time_format="%H:%M:%S.%f",
        omit_repeated_times=False,
    )
    logging.root.addHandler(rich_handler)

    # Enable file logging for services
    # TODO: Use config to determine if file logging is enabled and the folder path.
    log_folder = Path("artifacts/logs")
    log_folder.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_folder / "aiperf.log")
    file_handler.setLevel(level)
    file_handler.formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.root.addHandler(file_handler)

    logger.debug(lambda: f"Logging initialized with level: {level}")


# @app.command("profile")
# def profile(
#     config: Path | None = None,
#     run_type: ServiceRunType = ServiceRunType.MULTIPROCESSING,
#     user_config: UserConfig | None = None,
# ) -> None:
#     """Profile the AIPerf system."""
#     pass


@app.default
def main(
    cli_config: CLIConfig,
    user_config: UserConfig,
    service_config: ServiceConfig | None = None,
) -> None:
    """Main entry point for the AIPerf system."""

    # Create service config if not provided
    if service_config is None:
        service_config = ServiceConfig()

    # Override log level to DEBUG if verbose is enabled
    if cli_config.verbose:
        service_config.log_level = "DEBUG"

    log_queue = None
    if service_config.disable_ui:
        _setup_logging(service_config)
    else:
        from aiperf.common.logging import get_global_log_queue

        log_queue = get_global_log_queue()

    # Load configuration
    if cli_config.template_filename:
        logger.debug(f"Loading configuration from {cli_config.template_filename}")
        # TODO: Implement this
        # service_config.load_from_file(cli_config.template_filename)

    # Create and start the system controller
    logger.info("Starting AIPerf System")

    try:
        bootstrap_and_run_service(
            SystemController,
            service_id="system_controller",
            service_config=service_config,
            user_config=user_config,
            log_queue=log_queue,
        )
    except Exception as e:
        logger.exception("Error starting AIPerf System")
        raise e
    finally:
        logger.info("AIPerf System exited")


if __name__ == "__main__":
    sys.exit(app())
