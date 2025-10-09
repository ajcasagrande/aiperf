# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Main CLI entry point for the AIPerf system."""

print("DEBUG: main.py loading...", flush=True)

################################################################################
# NOTE: Keep the imports here to a minimum. This file is read every time
# the CLI is run, including to generate the help text. Any imports here
# will cause a performance penalty during this process.
################################################################################

import sys

print("DEBUG: sys imported", flush=True)

from cyclopts import App

from aiperf.cli_utils import exit_on_error
from aiperf.common.config import ServiceConfig, UserConfig

app = App(name="aiperf", help="NVIDIA AIPerf")


@app.command(name="profile")
def profile(
    user_config: UserConfig,
    service_config: ServiceConfig | None = None,
) -> None:
    """Run the Profile subcommand.

    Args:
        user_config: User configuration for the benchmark
        service_config: Service configuration options
    """
    print("DEBUG: profile() called", flush=True)
    with exit_on_error(title="Error Running AIPerf System"):
        from aiperf.cli_runner import run_system_controller
        from aiperf.common.config import load_service_config

        service_config = service_config or load_service_config()

        run_system_controller(user_config, service_config)


def main():
    """Main entry point for the aiperf CLI."""
    print("DEBUG: main() called", flush=True)
    result = app()
    print(f"DEBUG: app() returned {result}", flush=True)
    sys.exit(result)


if __name__ == "__main__":
    main()
