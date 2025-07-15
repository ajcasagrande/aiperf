# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Main CLI entry point for the AIPerf system."""

################################################################################
# NOTE: Keep the imports here to a minimum. This file is read every time
# the CLI is run, including to generate the help text. Any imports here
# will cause a performance penalty during this process.
################################################################################

import sys

import cyclopts

from aiperf.common.config import CLIConfig, ServiceConfig, UserConfig

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
    from aiperf.cli_runner import (
        prepare_service_config_from_cli,
        run_system_controller,
    )

    service_config = prepare_service_config_from_cli(
        cli_config=cli_config, service_config=service_config
    )
    run_system_controller(user_config, service_config, cli_config)


@app.command(name="analyze")
def analyze(
    user_config: UserConfig,
    service_config: ServiceConfig | None = None,
    cli_config: CLIConfig | None = None,
) -> None:
    """Sweep through one or more parameters."""
    # TODO: Implement this
    from aiperf.cli_runner import raise_subcommand_not_implemented

    raise_subcommand_not_implemented(
        "Analyze",
        user_config=user_config,
        service_config=service_config,
        cli_config=cli_config,
    )


@app.command(name="create-template", help="Create a template configuration file")
def create_template(
    user_config: UserConfig | None = None,
    service_config: ServiceConfig | None = None,
    cli_config: CLIConfig | None = None,
) -> None:
    """Create a template configuration file."""
    # TODO: Implement this
    from aiperf.cli_runner import raise_subcommand_not_implemented

    raise_subcommand_not_implemented(
        "Create Template",
        user_config=user_config,
        service_config=service_config,
        cli_config=cli_config,
    )


@app.command(name="validate", help="Validate the configuration file")
def validate(
    user_config: UserConfig | None = None,
    service_config: ServiceConfig | None = None,
    cli_config: CLIConfig | None = None,
) -> None:
    """Validate the configuration file."""
    # TODO: Implement this
    from aiperf.cli_runner import raise_subcommand_not_implemented

    raise_subcommand_not_implemented(
        "Validate Configuration",
        user_config=user_config,
        service_config=service_config,
        cli_config=cli_config,
    )


if __name__ == "__main__":
    sys.exit(app())
