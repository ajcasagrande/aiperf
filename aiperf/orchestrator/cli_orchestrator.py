# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
from typing import TYPE_CHECKING

from rich.console import Console

from aiperf.common.base_service import BaseService
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.config.config_defaults import OutputDefaults
from aiperf.common.config.dev_config import print_developer_mode_warning
from aiperf.common.constants import AIPERF_DEV_MODE
from aiperf.common.enums import MessageType, ServiceType
from aiperf.common.factories import AIPerfUIFactory, ServiceFactory
from aiperf.common.hooks import on_init, on_message, on_start, on_stop
from aiperf.common.logging import get_global_log_queue
from aiperf.common.messages import (
    ProcessRecordsResultMessage,
    ProcessTelemetryResultMessage,
    TelemetryStatusMessage,
)
from aiperf.common.models import ProcessRecordsResult, TelemetryResults
from aiperf.common.models.error_models import ExitErrorInfo
from aiperf.common.protocols import AIPerfUIProtocol
from aiperf.controller.controller_utils import print_exit_errors
from aiperf.exporters.exporter_manager import ExporterManager

if TYPE_CHECKING:
    from aiperf.controller.system_controller import SystemController


@ServiceFactory.register(ServiceType.CLI_ORCHESTRATOR)
class CLIOrchestrator(BaseService):
    """CLI Orchestrator service.

    This service is responsible for orchestrating the application lifecycle from the CLI:
    - Managing the UI
    - Monitoring system status
    - Handling results export and display
    - Coordinating with the SystemController for benchmark lifecycle

    This separation allows the SystemController to run independently (e.g., in Kubernetes)
    while the CLI orchestrator runs locally to provide user interface and monitoring.
    """

    def __init__(
        self,
        user_config: UserConfig,
        service_config: ServiceConfig,
        system_controller: "SystemController",
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id or "cli_orchestrator",
        )
        self.debug("Creating CLI Orchestrator")

        # Reference to the system controller for coordination
        self.system_controller = system_controller

        # Create the UI
        self.ui: AIPerfUIProtocol = AIPerfUIFactory.create_instance(
            self.service_config.ui_type,
            service_config=self.service_config,
            user_config=self.user_config,
            log_queue=get_global_log_queue(),
            controller=system_controller,
        )
        self.attach_child_lifecycle(self.ui)

        # Results tracking
        self._profile_results: ProcessRecordsResult | None = None
        self._telemetry_results: TelemetryResults | None = None
        self._profile_results_received = False
        self._should_wait_for_telemetry = False
        self._exit_errors: list[ExitErrorInfo] = []
        self._was_cancelled = False

        # Telemetry status
        self._endpoints_tested: list[str] = []
        self._endpoints_reachable: list[str] = []

        # Shutdown coordination
        self._shutdown_triggered = False
        self._shutdown_lock = asyncio.Lock()

        self.debug("CLI Orchestrator created")

    @on_init
    async def _initialize_orchestrator(self) -> None:
        """Initialize the CLI orchestrator."""
        self.debug("Initializing CLI Orchestrator")

    @on_start
    async def _start_orchestrator(self) -> None:
        """Start the CLI orchestrator."""
        self.debug("CLI Orchestrator started")
        self.info("AIPerf System orchestration started")

    @on_message(MessageType.TELEMETRY_STATUS)
    async def _on_telemetry_status_message(
        self, message: TelemetryStatusMessage
    ) -> None:
        """Handle telemetry status from TelemetryManager."""
        self._endpoints_tested = message.endpoints_tested
        self._endpoints_reachable = message.endpoints_reachable
        self._should_wait_for_telemetry = message.enabled

        if not message.enabled:
            reason_msg = f" - {message.reason}" if message.reason else ""
            self.info(f"GPU telemetry disabled{reason_msg}")
        else:
            self.info(
                f"GPU telemetry enabled - {len(message.endpoints_reachable)}/{len(message.endpoints_tested)} endpoint(s) reachable"
            )

    @on_message(MessageType.PROCESS_RECORDS_RESULT)
    async def _on_process_records_result_message(
        self, message: ProcessRecordsResultMessage
    ) -> None:
        """Handle profile results message."""
        self.debug(lambda: f"Received profile results message: {message}")
        if message.results.errors:
            self.error(
                f"Received process records result message with errors: {message.results.errors}"
            )

        self.debug(lambda: f"Error summary: {message.results.results.error_summary}")

        self._profile_results = message.results

        if not message.results.results:
            self.error(
                f"Received process records result message with no records: {message.results.results}"
            )

        self._profile_results_received = True
        await self._check_and_trigger_shutdown()

    @on_message(MessageType.PROCESS_TELEMETRY_RESULT)
    async def _on_process_telemetry_result_message(
        self, message: ProcessTelemetryResultMessage
    ) -> None:
        """Handle telemetry results message."""
        self.debug(lambda: f"Received telemetry results message: {message}")

        if message.telemetry_result.errors:
            self.warning(
                f"Received process telemetry result message with errors: {message.telemetry_result.errors}"
            )

        self.debug(
            lambda: f"Error summary: {message.telemetry_result.results.error_summary}"
        )

        telemetry_results = message.telemetry_result.results

        if not message.telemetry_result.results:
            self.error(
                f"Received process telemetry result message with no records: {telemetry_results}"
            )

        if telemetry_results:
            telemetry_results.endpoints_tested = self._endpoints_tested
            telemetry_results.endpoints_successful = self._endpoints_reachable

        self._telemetry_results = telemetry_results
        await self._check_and_trigger_shutdown()

    async def _check_and_trigger_shutdown(self) -> None:
        """Check if all required results are received and trigger shutdown."""
        async with self._shutdown_lock:
            if self._shutdown_triggered:
                return

            if not self._profile_results_received:
                return

            telemetry_ready_for_shutdown = (
                not self._should_wait_for_telemetry
                or self._telemetry_results is not None
            )

            if telemetry_ready_for_shutdown:
                self._shutdown_triggered = True
                self.debug("All results received, initiating shutdown")
                await asyncio.shield(self.stop())

    def set_exit_errors(self, errors: list[ExitErrorInfo]) -> None:
        """Set exit errors from the system controller."""
        self._exit_errors = errors

    def set_was_cancelled(self, cancelled: bool) -> None:
        """Set whether the benchmark was cancelled."""
        self._was_cancelled = cancelled

    @on_stop
    async def _stop_orchestrator(self) -> None:
        """Stop the orchestrator and display results."""
        # Wait for the UI to stop before exporting results
        await self.ui.stop()
        await self.ui.wait_for_tasks()
        await asyncio.sleep(0.1)

        if not self._exit_errors:
            await self._print_post_benchmark_info_and_metrics()
        else:
            self._print_exit_errors_and_log_file()

        if AIPERF_DEV_MODE:
            print_developer_mode_warning()

    def _print_exit_errors_and_log_file(self) -> None:
        """Print exit errors and log file info."""
        console = Console()
        print_exit_errors(self._exit_errors, console=console)
        self._print_log_file_info(console)
        console.print()
        console.file.flush()

    async def _print_post_benchmark_info_and_metrics(self) -> None:
        """Print post-benchmark info and metrics."""
        if not self._profile_results or not self._profile_results.results.records:
            self.warning("No profile results to export")
            return

        console = Console()
        if console.width < 100:
            console.width = 100

        exporter_manager = ExporterManager(
            results=self._profile_results.results,
            input_config=self.user_config,
            service_config=self.service_config,
            telemetry_results=self._telemetry_results,
        )

        await exporter_manager.export_data()
        await exporter_manager.export_console(console=console)

        console.print()
        self._print_cli_command(console)
        self._print_benchmark_duration(console)
        self._print_exported_file_infos(exporter_manager, console)
        self._print_log_file_info(console)

        if self._was_cancelled:
            console.print(
                "[italic yellow]The profile run was cancelled early. Results shown may be incomplete or inaccurate.[/italic yellow]"
            )

        console.print()
        console.file.flush()

    def _print_log_file_info(self, console: Console) -> None:
        """Print log file info."""
        log_file = (
            self.user_config.output.artifact_directory
            / OutputDefaults.LOG_FOLDER
            / OutputDefaults.LOG_FILE
        )
        console.print(
            f"[bold green]Log File:[/bold green] [cyan]{log_file.resolve()}[/cyan]"
        )

    def _print_exported_file_infos(
        self, exporter_manager: ExporterManager, console: Console
    ) -> None:
        """Print exported file infos."""
        file_infos = exporter_manager.get_exported_file_infos()
        for file_info in file_infos:
            console.print(
                f"[bold green]{file_info.export_type}[/bold green]: [cyan]{file_info.file_path.resolve()}[/cyan]"
            )

    def _print_cli_command(self, console: Console) -> None:
        """Print the CLI command."""
        console.print(
            f"[bold green]CLI Command:[/bold green] [italic]{self.user_config.cli_command}[/italic]"
        )

    def _print_benchmark_duration(self, console: Console) -> None:
        """Print benchmark duration."""
        from aiperf.metrics.types.benchmark_duration_metric import (
            BenchmarkDurationMetric,
        )

        duration = self._profile_results.get(BenchmarkDurationMetric.tag)
        if duration:
            duration = duration.to_display_unit()
            duration_str = f"[bold green]{BenchmarkDurationMetric.header}[/bold green]: {duration.avg:.2f} {duration.unit}"
            if self._was_cancelled:
                duration_str += " [italic yellow](cancelled early)[/italic yellow]"
            console.print(duration_str)

    def get_exit_code(self) -> int:
        """Get the exit code based on whether there were errors."""
        return 1 if self._exit_errors else 0
