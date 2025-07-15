# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Main CLI entry point for the AIPerf system."""

import sys

import cyclopts

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.config import CLIConfig, ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.logging import setup_rich_logging
from aiperf.services import SystemController

logger = AIPerfLogger(__name__)

app = cyclopts.App(name="aiperf", help="NVIDIA AIPerf")


@app.command(name="profile")
def profile(
    user_config: UserConfig,
    service_config: ServiceConfig | None = None,
    cli_config: CLIConfig | None = None,
) -> None:
    """Run the Profile subcommand.

    Args:
        user_config: User configuration for the benchmark
        service_config: Service configuration options
        cli_config: CLI configuration options
    """
    service_config = _prepare_service_config_from_cli(cli_config, service_config)
    _run_system_controller(user_config, service_config)


@app.command(name="analyze")
def analyze(
    user_config: UserConfig,
    service_config: ServiceConfig | None = None,
    cli_config: CLIConfig | None = None,
) -> None:
    """Sweep through one or more parameters."""
    # TODO: Implement this
    service_config = _prepare_service_config_from_cli(cli_config, service_config)
    setup_rich_logging(user_config or UserConfig(model_names=["gpt2"]), service_config)
    logger.error("Analyze subcommand not implemented")
    raise NotImplementedError("Analyze not implemented")


@app.command(name="create-template", help="Create a template configuration file")
def create_template(
    user_config: UserConfig | None = None,
    service_config: ServiceConfig | None = None,
    cli_config: CLIConfig | None = None,
) -> None:
    """Create a template configuration file."""
    # TODO: Implement this
    service_config = _prepare_service_config_from_cli(cli_config, service_config)
    setup_rich_logging(user_config or UserConfig(model_names=["gpt2"]), service_config)
    logger.error("Create template subcommand not implemented")
    raise NotImplementedError("Create template not implemented")


@app.command(name="validate", help="Validate the configuration file")
def validate(
    user_config: UserConfig | None = None,
    service_config: ServiceConfig | None = None,
    cli_config: CLIConfig | None = None,
) -> None:
    """Validate the configuration file."""
    # TODO: Implement this
    service_config = _prepare_service_config_from_cli(cli_config, service_config)
    setup_rich_logging(user_config or UserConfig(model_names=["gpt2"]), service_config)
    logger.error("Validate subcommand not implemented")
    raise NotImplementedError("Validate not implemented")


def _prepare_service_config_from_cli(
    cli_config: CLIConfig | None = None,
    service_config: ServiceConfig | None = None,
) -> ServiceConfig:
    """Prepare service config and apply verbose overrides."""
    cli_config = cli_config or CLIConfig()
    service_config = service_config or ServiceConfig()

    # Override log level based on verbose flags
    # TODO: Warn the user that the log level is being overridden if they manually set it with --log-level
    if cli_config.extra_verbose:
        service_config.log_level = "TRACE"
    elif cli_config.verbose:
        service_config.log_level = "DEBUG"

    return service_config


def _run_system_controller(
    user_config: UserConfig, service_config: ServiceConfig
) -> None:
    """Run the system controller with the given configuration."""
    log_queue = None
    if service_config.disable_ui:
        setup_rich_logging(user_config, service_config)
    else:
        from aiperf.common.logging import get_global_log_queue

        log_queue = get_global_log_queue()

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
