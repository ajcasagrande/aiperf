#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.config import CLIConfig, ServiceConfig, UserConfig


def prepare_service_config_from_cli(
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


def run_system_controller(
    user_config: UserConfig,
    service_config: ServiceConfig | None = None,
    cli_config: CLIConfig | None = None,
) -> None:
    """Run the system controller with the given configuration."""

    from aiperf.common.aiperf_logger import AIPerfLogger
    from aiperf.common.bootstrap import bootstrap_and_run_service
    from aiperf.services import SystemController

    service_config = prepare_service_config_from_cli(
        cli_config=cli_config, service_config=service_config
    )

    logger = AIPerfLogger(__name__)

    log_queue = None
    if service_config.disable_ui:
        from aiperf.common.logging import setup_rich_logging

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


def raise_subcommand_not_implemented(
    subcommand: str,
    user_config: UserConfig | None = None,
    service_config: ServiceConfig | None = None,
    cli_config: CLIConfig | None = None,
) -> None:
    """Raise a NotImplementedError with a message."""
    from aiperf.common.aiperf_logger import AIPerfLogger
    from aiperf.common.logging import setup_rich_logging

    service_config = prepare_service_config_from_cli(
        cli_config=cli_config, service_config=service_config
    )
    setup_rich_logging(user_config or UserConfig(model_names=["gpt2"]), service_config)
    logger = AIPerfLogger(__name__)

    logger.error(f"{subcommand} subcommand not implemented")
    raise NotImplementedError(f"{subcommand} not implemented")
