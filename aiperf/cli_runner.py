# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""CLI runner for AIPerf - delegates to ApplicationRunner."""

from aiperf.cli.application_runner import ApplicationRunner
from aiperf.common.config import ServiceConfig, UserConfig


def run_system_controller(
    user_config: UserConfig,
    service_config: ServiceConfig,
) -> None:
    """Run AIPerf with the given configuration.

    This function creates an ApplicationRunner and delegates to it.
    The ApplicationRunner will handle:
    - Selecting deployment mode (local vs Kubernetes)
    - Managing UI lifecycle
    - Coordinating SystemController
    - Displaying results
    """
    runner = ApplicationRunner(
        user_config=user_config,
        service_config=service_config,
    )
    runner.run()
