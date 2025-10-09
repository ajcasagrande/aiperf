# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Local (multiprocess) deployment runner for AIPerf."""

import asyncio
import signal
from typing import Any

from aiperf.cli.base_runner import BaseDeploymentRunner
from aiperf.cli_utils import raise_startup_error_and_exit
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums.ui_enums import AIPerfUIType
from aiperf.common.factories import AIPerfUIFactory
from aiperf.common.logging import get_global_log_queue, setup_rich_logging
from aiperf.common.models import ProcessRecordsResult
from aiperf.common.protocols import AIPerfUIProtocol


class LocalDeploymentRunner(BaseDeploymentRunner):
    """Runs AIPerf locally using multiprocess deployment.

    This runner:
    - Creates and manages UI independently
    - Starts SystemController via bootstrap
    - Coordinates shutdown
    - Collects results from controller
    """

    def __init__(self, user_config: UserConfig, service_config: ServiceConfig):
        super().__init__(user_config, service_config)
        self.ui: AIPerfUIProtocol | None = None
        self.controller: Any = None  # SystemController instance
        self._stop_event = asyncio.Event()
        self._signal_handler_setup = False

    async def run(self) -> ProcessRecordsResult | None:
        """Run AIPerf locally."""
        self.logger.info("Starting AIPerf in local mode")

        try:
            # Setup logging
            await self._setup_logging()

            # Setup signal handlers
            self._setup_signal_handlers()

            # Create UI (for non-Dashboard UIs)
            await self._create_ui()

            # Start UI (for non-Dashboard UIs)
            if self.ui:
                await self.ui.initialize()
                await self.ui.start()

            # Load modules
            self._load_modules()

            # Create and run System Controller
            # (Dashboard UI will be created during controller bootstrap)
            await self._run_controller()

            # Return results
            return self._profile_results

        except Exception as e:
            self.logger.exception(f"Error running AIPerf locally: {e}")
            raise
        finally:
            await self.stop()

    async def _setup_logging(self) -> None:
        """Setup logging based on UI type."""
        # Always setup logging for the main process
        setup_rich_logging(self.user_config, self.service_config)

    async def _create_ui(self) -> None:
        """Create UI instance independently of controller.

        Note: For Dashboard UI, we delay creation until after controller is created
        since it needs a controller reference. For other UIs, we create them now.
        """
        if self.service_config.ui_type == AIPerfUIType.DASHBOARD:
            # Dashboard UI needs controller reference, create it later
            return

        log_queue = None
        self.ui = AIPerfUIFactory.create_instance(
            self.service_config.ui_type,
            service_config=self.service_config,
            user_config=self.user_config,
            log_queue=log_queue,
            controller=None,
        )

    def _load_modules(self) -> None:
        """Load required modules."""
        from aiperf.module_loader import ensure_modules_loaded

        try:
            ensure_modules_loaded()
        except Exception as e:
            raise_startup_error_and_exit(
                f"Error loading modules: {e}",
                title="Error Loading Modules",
            )

    async def _run_controller(self) -> None:
        """Create and run the System Controller."""
        from aiperf.controller import SystemController

        log_queue = None
        if self.service_config.ui_type == AIPerfUIType.DASHBOARD:
            log_queue = get_global_log_queue()

        self.logger.info("Starting AIPerf System Controller")

        try:
            # Run controller in async context
            await self._bootstrap_controller(
                SystemController,
                service_id="system_controller",
                service_config=self.service_config,
                user_config=self.user_config,
                log_queue=log_queue,
                ui=self.ui,  # Pass UI to controller for event coordination
            )
        except Exception:
            self.logger.exception("Error running AIPerf System Controller")
            raise
        finally:
            self.logger.debug("AIPerf System Controller exited")

    async def _bootstrap_controller(
        self,
        service_class: type,
        service_id: str,
        service_config: ServiceConfig,
        user_config: UserConfig,
        log_queue: Any,
        ui: AIPerfUIProtocol | None,
    ) -> None:
        """Bootstrap and run the controller service.

        This is similar to bootstrap_and_run_service but adapted for async context.
        """
        # Import here to avoid circular dependency
        from aiperf.common.logging import setup_child_process_logging
        from aiperf.module_loader import ensure_modules_loaded

        ensure_modules_loaded()

        # Create controller instance
        self.controller = service_class(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )

        # Create Dashboard UI now if needed (it requires controller reference)
        if self.service_config.ui_type == AIPerfUIType.DASHBOARD and not ui:
            log_queue = get_global_log_queue()
            self.ui = AIPerfUIFactory.create_instance(
                self.service_config.ui_type,
                service_config=service_config,
                user_config=user_config,
                log_queue=log_queue,
                controller=self.controller,
            )
            ui = self.ui
            # Initialize and start Dashboard UI
            await ui.initialize()
            await ui.start()

        setup_child_process_logging(
            log_queue, self.controller.service_id, service_config, user_config
        )

        # Run controller lifecycle
        await self.controller.initialize()
        await self.controller.start()
        await self.controller.stopped_event.wait()

        # Extract results before stopping
        if hasattr(self.controller, "_profile_results"):
            self._profile_results = self.controller._profile_results

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        if self._signal_handler_setup:
            return

        loop = asyncio.get_running_loop()

        def signal_handler(sig: int) -> None:
            self.logger.info(f"Received signal {sig}, initiating shutdown")
            asyncio.create_task(self.stop())

        loop.add_signal_handler(signal.SIGINT, signal_handler, signal.SIGINT)
        loop.add_signal_handler(signal.SIGTERM, signal_handler, signal.SIGTERM)
        self._signal_handler_setup = True

    async def stop(self) -> None:
        """Stop all components gracefully."""
        if self._stop_event.is_set():
            return

        self._stop_event.set()
        self.logger.info("Stopping local deployment")

        # Stop UI first (it's independent)
        if self.ui:
            try:
                await self.ui.stop()
                await self.ui.wait_for_tasks()
            except Exception as e:
                self.logger.error(f"Error stopping UI: {e}")

        # Controller should already be stopped (we wait for it)
        # But if not, we can stop it here
        if self.controller and not self.controller.was_stopped:
            try:
                await self.controller.stop()
            except Exception as e:
                self.logger.error(f"Error stopping controller: {e}")
