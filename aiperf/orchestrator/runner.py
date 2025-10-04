# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Runner module for coordinating the CLI Orchestrator and System Controller."""

import asyncio
import contextlib
import os
import random

from aiperf.cli_utils import raise_startup_error_and_exit
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums.ui_enums import AIPerfUIType


def run_aiperf_system(
    user_config: UserConfig,
    service_config: ServiceConfig,
) -> None:
    """Run the AIPerf system with orchestrator and system controller.

    This is the main entry point that coordinates:
    1. System Controller - manages services and benchmark lifecycle
    2. CLI Orchestrator - manages UI, monitoring, and results display

    Args:
        user_config: User configuration for the benchmark
        service_config: Service configuration options
    """
    from aiperf.common.aiperf_logger import AIPerfLogger
    from aiperf.common.logging import get_global_log_queue
    from aiperf.module_loader import ensure_modules_loaded

    logger = AIPerfLogger(__name__)

    log_queue = None
    if service_config.ui_type == AIPerfUIType.DASHBOARD:
        log_queue = get_global_log_queue()
    else:
        from aiperf.common.logging import setup_rich_logging

        setup_rich_logging(user_config, service_config)

    logger.info("Starting AIPerf System")

    try:
        ensure_modules_loaded()
    except Exception as e:
        raise_startup_error_and_exit(
            f"Error loading modules: {e}",
            title="Error Loading Modules",
        )

    try:
        exit_code = _run_system(
            user_config=user_config,
            service_config=service_config,
            log_queue=log_queue,
        )
        os._exit(exit_code)
    except Exception:
        logger.exception("Error running AIPerf System")
        raise
    finally:
        logger.debug("AIPerf System exited")


def _run_system(
    user_config: UserConfig,
    service_config: ServiceConfig,
    log_queue=None,
) -> int:
    """Run the system with both controller and orchestrator.

    Returns:
        Exit code (0 for success, 1 for failure)
    """

    async def _run():
        from aiperf.common.logging import setup_child_process_logging

        if user_config.input.random_seed is not None:
            random.seed(user_config.input.random_seed)
            with contextlib.suppress(ImportError):
                import numpy as np

                np.random.seed(user_config.input.random_seed)

        from aiperf.controller import SystemController

        # Create SystemController
        system_controller = SystemController(
            service_config=service_config,
            user_config=user_config,
            service_id="system_controller",
        )

        setup_child_process_logging(
            log_queue, system_controller.service_id, service_config, user_config
        )

        from aiperf.orchestrator import CLIOrchestrator

        # Create CLIOrchestrator
        orchestrator = CLIOrchestrator(
            service_config=service_config,
            user_config=user_config,
            system_controller=system_controller,
        )

        try:
            # Initialize both components
            await system_controller.initialize()
            await orchestrator.initialize()

            # Start both components
            await system_controller.start()
            await orchestrator.start()

            # Wait for orchestrator to complete (it waits for results)
            await orchestrator.stopped_event.wait()

            # Transfer state from controller to orchestrator
            orchestrator.set_exit_errors(system_controller.get_exit_errors())
            orchestrator.set_was_cancelled(system_controller.was_cancelled())

            # Stop the system controller if not already stopped
            if not system_controller.stop_requested:
                await system_controller.stop()

            await system_controller.stopped_event.wait()

            return orchestrator.get_exit_code()

        except Exception as e:
            system_controller.exception(f"Unhandled exception in system: {e}")
            return 1

    with contextlib.suppress(asyncio.CancelledError):
        if not service_config.developer.disable_uvloop:
            import uvloop

            return uvloop.run(_run())
        else:
            return asyncio.run(_run())
