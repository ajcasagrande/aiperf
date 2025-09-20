# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
from enum import Enum
from typing import Any

from rich.console import Console

from aiperf.common.config.dev_config import print_developer_mode_warning
from aiperf.common.constants import AIPERF_DEV_MODE
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import ProcessRecordsResult
from aiperf.common.protocols import AIPerfUIProtocol, ServiceManagerProtocol
from aiperf.controller.proxy_manager import ProxyManager
from aiperf.controller.system_utils import (
    display_configuration_errors,
    display_startup_errors,
)
from aiperf.exporters.exporter_manager import ExporterManager


class ShutdownReason(Enum):
    """Reasons for system shutdown."""

    NORMAL = "normal"
    STARTUP_ERROR = "startup_error"
    CONFIGURATION_ERROR = "configuration_error"
    SIGNAL_RECEIVED = "signal_received"
    CANCELLED = "cancelled"


class ShutdownManager(AIPerfLoggerMixin):
    """Unified shutdown manager that handles all shutdown scenarios cleanly."""

    def __init__(
        self,
        service_manager: ServiceManagerProtocol,
        proxy_manager: ProxyManager,
        ui: AIPerfUIProtocol,
        user_config: Any,
        service_config: Any,
        comms: Any = None,
    ) -> None:
        super().__init__()
        self.service_manager = service_manager
        self.proxy_manager = proxy_manager
        self.ui = ui
        self.user_config = user_config
        self.service_config = service_config
        self.comms = comms

        self._startup_errors: list[dict] = []
        self._configuration_errors: list = []
        self._profile_results: ProcessRecordsResult | None = None
        self._was_cancelled = False
        self._shutdown_in_progress = False

    async def shutdown(
        self,
        reason: ShutdownReason = ShutdownReason.NORMAL,
        startup_errors: list[dict] | None = None,
        configuration_errors: list | None = None,
        profile_results: ProcessRecordsResult | None = None,
        was_cancelled: bool = False,
    ) -> int:
        """Unified shutdown method that handles all scenarios.

        Returns:
            Exit code (0 for success, 1 for error/cancellation)
        """
        if self._shutdown_in_progress:
            self.warning("Shutdown already in progress, forcing exit")
            os._exit(1)

        self._shutdown_in_progress = True
        self._startup_errors = startup_errors or []
        self._configuration_errors = configuration_errors or []
        self._profile_results = profile_results
        self._was_cancelled = was_cancelled

        self.debug(f"Starting shutdown with reason: {reason.value}")

        # Set up emergency exit timer for startup errors
        emergency_timer = None
        if reason == ShutdownReason.STARTUP_ERROR:
            emergency_timer = asyncio.create_task(self._emergency_exit_timer())

        try:
            # Determine if this is an emergency shutdown
            is_emergency = reason in (
                ShutdownReason.STARTUP_ERROR,
                ShutdownReason.SIGNAL_RECEIVED,
            )
            shutdown_timeout = 15.0 if is_emergency else 30.0

            await asyncio.wait_for(
                self._perform_shutdown(is_emergency), timeout=shutdown_timeout
            )

        except asyncio.TimeoutError:
            self.warning(f"Shutdown timed out after {shutdown_timeout}s, forcing exit")
        except Exception as e:
            self.error(f"Shutdown failed: {e}")
        finally:
            if emergency_timer and not emergency_timer.done():
                emergency_timer.cancel()

        # Determine exit code
        exit_code = 0
        if self._startup_errors or self._configuration_errors or self._was_cancelled:
            exit_code = 1

        self.debug(f"Shutdown complete, exiting with code {exit_code}")
        os._exit(exit_code)

    async def _emergency_exit_timer(self) -> None:
        """Emergency exit timer for startup errors."""
        await asyncio.sleep(20.0)
        self.warning("Emergency exit timer triggered, forcing process termination")
        os._exit(1)

    async def _perform_shutdown(self, is_emergency: bool) -> None:
        """Perform the actual shutdown steps."""
        steps = [
            ("services", self._shutdown_services),
            ("communications", self._shutdown_communications),
            ("proxy_manager", self._shutdown_proxy_manager),
            ("ui", self._shutdown_ui),
            ("results", self._export_results),
            ("errors", self._display_errors),
        ]

        for step_name, step_func in steps:
            try:
                timeout = 3.0 if is_emergency else 10.0
                await asyncio.wait_for(step_func(is_emergency), timeout=timeout)
            except asyncio.TimeoutError:
                self.warning(f"Shutdown step '{step_name}' timed out")
            except Exception as e:
                self.warning(f"Shutdown step '{step_name}' failed: {e}")

    async def _shutdown_services(self, is_emergency: bool) -> None:
        """Shutdown all services."""
        if is_emergency:
            await self.service_manager.kill_all_services()
        else:
            await self.service_manager.shutdown_all_services()

    async def _shutdown_communications(self, is_emergency: bool) -> None:
        """Shutdown communications."""
        if self.comms:
            await self.comms.stop()

    async def _shutdown_proxy_manager(self, is_emergency: bool) -> None:
        """Shutdown proxy manager."""
        await self.proxy_manager.stop()

    async def _shutdown_ui(self, is_emergency: bool) -> None:
        """Shutdown UI and wait for tasks."""
        await self.ui.stop()
        if not is_emergency:
            await self.ui.wait_for_tasks()

    async def _export_results(self, is_emergency: bool) -> None:
        """Export results if available and not emergency shutdown."""
        if is_emergency or not self._profile_results:
            return

        if self._startup_errors or self._configuration_errors:
            return

        if (
            not self._profile_results
            or not self._profile_results.results
            or not self._profile_results.results.records
        ):
            self.warning("No profile results to export")
            return

        await self._print_post_benchmark_info()

    async def _display_errors(self, is_emergency: bool) -> None:
        """Display any collected errors."""
        # Give terminal time to settle after UI cleanup
        await asyncio.sleep(0.1)

        if self._startup_errors:
            display_startup_errors(self._startup_errors)

        if self._configuration_errors:
            display_configuration_errors(self._configuration_errors)

        # Print developer mode warning if enabled
        if AIPERF_DEV_MODE:
            try:
                print_developer_mode_warning()
            except Exception as e:
                self.warning(f"Failed to print developer mode warning: {e}")

    async def _print_post_benchmark_info(self) -> None:
        """Print post benchmark info and metrics to the console."""
        console = Console()
        if console.width < 100:
            console.width = 100

        exporter_manager = ExporterManager(
            results=self._profile_results.results,
            input_config=self.user_config,
            service_config=self.service_config,
        )
        await exporter_manager.export_console(console=console)

        console.print()
        self._print_cli_command(console)
        self._print_benchmark_duration(console)
        self._print_exported_file_infos(exporter_manager, console)

        if self._was_cancelled:
            console.print(
                "[italic yellow]The profile run was cancelled early. Results shown may be incomplete or inaccurate.[/italic yellow]"
            )

        console.print()
        console.file.flush()

    def _print_exported_file_infos(
        self, exporter_manager: ExporterManager, console: Console
    ) -> None:
        """Print the exported file infos."""
        file_infos = exporter_manager.get_exported_file_infos()
        for file_info in file_infos:
            console.print(
                f"[bold green]{file_info.export_type}[/bold green]: [cyan]{file_info.file_path.resolve()}[/cyan]"
            )

    def _print_cli_command(self, console: Console) -> None:
        """Print the CLI command that was used to run the benchmark."""
        console.print(
            f"[bold green]CLI Command:[/bold green] [italic]{self.user_config.cli_command}[/italic]"
        )

    def _print_benchmark_duration(self, console: Console) -> None:
        """Print the duration of the benchmark."""
        from aiperf.metrics.types.benchmark_duration_metric import (
            BenchmarkDurationMetric,
        )

        duration = (
            self._profile_results.get(BenchmarkDurationMetric.tag)
            if self._profile_results
            else None
        )
        if duration:
            duration = duration.to_display_unit()
            duration_str = f"[bold green]{BenchmarkDurationMetric.header}[/bold green]: {duration.avg:.2f} {duration.unit}"
            if self._was_cancelled:
                duration_str += " [italic yellow](cancelled early)[/italic yellow]"
            console.print(duration_str)
