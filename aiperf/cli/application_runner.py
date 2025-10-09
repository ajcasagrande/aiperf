# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Top-level application runner that coordinates UI, deployment, and results."""

import asyncio
import contextlib
import sys

from rich.console import Console

from aiperf.cli.base_runner import BaseDeploymentRunner
from aiperf.cli.kubernetes_runner import KubernetesDeploymentRunner
from aiperf.cli.local_runner import LocalDeploymentRunner
from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.config.config_defaults import OutputDefaults
from aiperf.common.config.dev_config import print_developer_mode_warning
from aiperf.common.constants import AIPERF_DEV_MODE
from aiperf.common.enums import ServiceRunType
from aiperf.common.models import ProcessRecordsResult
from aiperf.common.models.error_models import ExitErrorInfo
from aiperf.controller.controller_utils import print_exit_errors
from aiperf.exporters.exporter_manager import ExporterManager


class ApplicationRunner:
    """Top-level application coordinator.

    This class is responsible for:
    - Selecting the appropriate deployment mode (local vs Kubernetes)
    - Running the deployment
    - Coordinating results display
    - Managing application-level concerns (logging, errors, cleanup)
    """

    def __init__(
        self,
        user_config: UserConfig,
        service_config: ServiceConfig,
    ):
        self.user_config = user_config
        self.service_config = service_config
        self.logger = AIPerfLogger(__name__)

        # Select deployment runner based on service run type
        self.runner = self._create_runner()

        # Results and errors
        self._profile_results: ProcessRecordsResult | None = None
        self._exit_errors: list[ExitErrorInfo] = []
        self._was_cancelled = False

    def _create_runner(self) -> BaseDeploymentRunner:
        """Create the appropriate deployment runner based on config."""
        if self.service_config.service_run_type == ServiceRunType.KUBERNETES:
            self.logger.info("Using Kubernetes deployment mode")
            return KubernetesDeploymentRunner(
                user_config=self.user_config,
                service_config=self.service_config,
            )
        else:
            self.logger.info("Using local deployment mode")
            return LocalDeploymentRunner(
                user_config=self.user_config,
                service_config=self.service_config,
            )

    def run(self) -> None:
        """Run the application synchronously.

        This is the main entry point called from the CLI.
        """
        try:
            # Run the async runner
            if not self.service_config.developer.disable_uvloop:
                with contextlib.suppress(ImportError):
                    import uvloop

                    uvloop.run(self._run_async())
                    return

            asyncio.run(self._run_async())

        except KeyboardInterrupt:
            self.logger.info("Application interrupted by user")
            self._was_cancelled = True
        except Exception as e:
            self.logger.exception(f"Application error: {e}")
            sys.exit(1)

    async def _run_async(self) -> None:
        """Run the application asynchronously."""
        try:
            # Run the deployment
            self._profile_results = await self.runner.run()

            # Display results
            if not self._exit_errors:
                await self._print_post_benchmark_info_and_metrics()
            else:
                self._print_exit_errors_and_log_file()

        except Exception as e:
            self.logger.exception(f"Deployment failed: {e}")
            raise
        finally:
            # Print developer mode warning if enabled
            if AIPERF_DEV_MODE:
                print_developer_mode_warning()

    async def _print_post_benchmark_info_and_metrics(self) -> None:
        """Print post benchmark info and metrics to the console."""
        if not self._profile_results or not self._profile_results.results.records:
            self.logger.warning("No profile results to export")
            return

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
        self._print_log_file_info(console)
        if self._was_cancelled:
            console.print(
                "[italic yellow]The profile run was cancelled early. Results shown may be incomplete or inaccurate.[/italic yellow]"
            )

        console.print()
        console.file.flush()

    def _print_exit_errors_and_log_file(self) -> None:
        """Print post exit errors and log file info to the console."""
        console = Console()
        print_exit_errors(self._exit_errors, console=console)
        self._print_log_file_info(console)
        console.print()
        console.file.flush()

    def _print_log_file_info(self, console: Console) -> None:
        """Print the log file info."""
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

        if not self._profile_results:
            return

        duration = self._profile_results.get(BenchmarkDurationMetric.tag)
        if duration:
            duration = duration.to_display_unit()
            duration_str = f"[bold green]{BenchmarkDurationMetric.header}[/bold green]: {duration.avg:.2f} {duration.unit}"
            if self._was_cancelled:
                duration_str += " [italic yellow](cancelled early)[/italic yellow]"
            console.print(duration_str)
