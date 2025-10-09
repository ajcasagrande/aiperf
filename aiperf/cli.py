# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Main CLI entry point for the AIPerf system."""

################################################################################
# NOTE: Keep the imports here to a minimum. This file is read every time
# the CLI is run, including to generate the help text. Any imports here
# will cause a performance penalty during this process.
################################################################################

import sys

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
    with exit_on_error(title="Error Running AIPerf System"):
        from aiperf.common.config import load_service_config
        from aiperf.common.config.config_validators import NO_GPU_FLAG

        # Parse --gpu-telemetry from cli_command to work around cyclopts bug
        if user_config.cli_command and "--gpu-telemetry" in user_config.cli_command:
            # Flag was provided - extract URLs if any
            parts = user_config.cli_command.split()
            try:
                idx = parts.index("--gpu-telemetry")
                # Collect URLs after the flag (until next flag or end)
                urls = []
                for i in range(idx + 1, len(parts)):
                    if parts[i].startswith("-"):
                        break
                    urls.append(parts[i])
                # None means "flag provided with defaults", list means "flag with URLs"
                user_config.gpu_telemetry = urls if urls else None
            except (ValueError, IndexError):
                user_config.gpu_telemetry = None
        else:
            # Flag not provided - keep sentinel to indicate no display
            user_config.gpu_telemetry = NO_GPU_FLAG

        service_config = service_config or load_service_config()

        # Check if Kubernetes mode is enabled
        if service_config.kubernetes.enabled:
            from aiperf.orchestrator.kubernetes_runner import run_aiperf_kubernetes

            run_aiperf_kubernetes(user_config, service_config)
        else:
            from aiperf.orchestrator.runner import run_aiperf_system

            run_aiperf_system(user_config, service_config)


if __name__ == "__main__":
    sys.exit(app())
