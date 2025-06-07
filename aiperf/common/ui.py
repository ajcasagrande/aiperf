#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import time

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from aiperf.common.config.endpoint_config import EndPointConfig
from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.data_exporter.console_exporter import ConsoleExporter
from aiperf.common.hooks import (
    AIPerfHook,
    HooksMixin,
    on_start,
    on_stop,
    supports_hooks,
)
from aiperf.common.messages import ProfileProgressMessage, ProfileResultsMessage


class RequestsPerSecondColumn(ProgressColumn):
    """Custom column to display requests per second."""

    def render(self, task) -> Text:
        """Render the requests per second for a task."""

        if task.finished:
            # If the task is completed, use the req_per_second field (covers the whole profile)
            text = (
                f"{task.fields['req_per_second']:.1f} req/s"
                if "req_per_second" in task.fields
                else "-- req/s"
            )
        else:
            # Otherwise, use the speed field (dynamic window over time)
            text = "-- req/s" if task.speed is None else f"{task.speed:.1f} req/s"

        return Text(text, style="progress.data.speed")


@supports_hooks(AIPerfHook.ON_INIT, AIPerfHook.ON_START, AIPerfHook.ON_STOP)
class ConsoleUIMixin(HooksMixin):
    """Mixin for updating the console UI."""

    def __init__(self) -> None:
        super().__init__()
        self.console = Console()
        self.live: Live = Live(console=self.console)

    async def initialize(self) -> None:
        """Initialize the console UI."""
        await self.run_hooks_async(AIPerfHook.ON_INIT)

    async def start(self) -> None:
        """Start the console UI."""
        self.live.start()
        await self.run_hooks_async(AIPerfHook.ON_START)

    async def stop(self) -> None:
        """Stop the console UI."""
        await self.run_hooks_async(AIPerfHook.ON_STOP)
        self.live.stop()


class ProfileProgressDashboardMixin(ConsoleUIMixin):
    """Mixin for updating the profile progress dashboard."""

    def __init__(self) -> None:
        super().__init__()
        self.progress: Progress | None = None
        self.task_id: TaskID | None = None
        self.start_time_ns: int | None = None
        self.error_count: int = 0
        self.error_rate: float = 0.0

    @on_start
    async def run_profile_progress_dashboard(self) -> None:
        """Run the profile progress dashboard."""
        # Create progress bar with custom columns
        self.progress = Progress(
            SpinnerColumn(),
            "[bold blue]{task.description}",
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            RequestsPerSecondColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            expand=True,
        )

        panel = Panel(
            Text("Waiting for profile data...", style="dim"),
            title="AIPerf Dashboard",
            border_style="blue",
        )
        self.live.update(panel, refresh=True)

    def _create_progress_dashboard(self) -> Panel:
        """Create the main dashboard layout."""
        # Create stats table
        stats_table = Table.grid(padding=1)
        stats_table.add_column(style="cyan", no_wrap=True)
        stats_table.add_column(style="white")

        if self.task_id is not None:
            task = self.progress.tasks[self.task_id]

            # Calculate additional metrics
            completion_pct = (
                (task.completed / task.total * 100)
                if task.total and task.total > 0 and task.completed is not None
                else 0
            )
            elapsed_time = task.elapsed or 0

            stats_table.add_row(
                "Status:", "Processing" if not task.finished else "Complete"
            )
            stats_table.add_row(
                "Progress:", f"{task.completed:,} / {task.total:,} requests"
            )
            stats_table.add_row("Completion:", f"{completion_pct:.1f}%")
            # stats_table.add_row("Errors:", f"{self.error_count:,} ()")
            stats_table.add_row(
                "Rate:",
                f"{task.speed:.1f} req/s" if task.speed else "-- req/s",
            )
            stats_table.add_row("Elapsed:", f"{elapsed_time:.1f}s")

            if (
                task.speed
                and task.speed > 0
                and not task.finished
                and task.total is not None
                and task.completed is not None
            ):
                remaining_requests = task.total - task.completed
                eta_seconds = remaining_requests / task.speed
                stats_table.add_row("ETA:", f"{eta_seconds:.1f}s")

        # Combine progress bar and stats
        dashboard_content = Table.grid()
        dashboard_content.add_column()
        dashboard_content.add_row(self.progress)
        dashboard_content.add_row("")  # Spacing
        dashboard_content.add_row(stats_table)

        return Panel(
            dashboard_content,
            title="[bold blue]AIPerf Profile Dashboard",
            border_style="blue",
            padding=(1, 2),
        )

    @on_stop
    async def stop_profile_progress_dashboard(self) -> None:
        """Stop the profile progress dashboard."""
        self.progress = None
        self.task_id = None

    def update_profile_progress(self, message: ProfileProgressMessage) -> None:
        """
        Update the profile progress with rich dashboard display.
        """
        if not self.progress:
            return

        # Initialize start time and task on first update
        if self.start_time_ns is None or self.task_id is None:
            self.start_time_ns = message.sweep_start_ns
            self.task_id = self.progress.add_task(
                "Processing Requests",
                total=message.total,
                completed=message.completed,
            )

        # Calculate requests per second
        elapsed_seconds = (
            (message.request_ns or time.perf_counter_ns()) - self.start_time_ns
        ) / NANOS_PER_SECOND

        req_per_second = (
            message.completed / elapsed_seconds if (elapsed_seconds or 0) > 0 else 0.0
        )

        self.error_count = message.errors
        self.error_rate = self.error_count / message.total

        # Update the progress task
        self.progress.update(
            self.task_id,
            completed=message.completed,
            total=message.total,
            req_per_second=req_per_second,
        )

        # Update the live display
        self.live.update(self._create_progress_dashboard())


class FinalResultsDashboardMixin(ConsoleUIMixin):
    """Mixin for updating the final results dashboard."""

    def __init__(self) -> None:
        super().__init__()

        # TODO: make this take in the endpoint config
        self.console_exporter: ConsoleExporter = ConsoleExporter(
            live=self.live,
            endpoint_config=EndPointConfig(
                type="console",
                streaming=True,
            ),
        )


class AIPerfUI(ProfileProgressDashboardMixin, FinalResultsDashboardMixin):
    """
    AIPerfUI is a class that provides a UI for the AIPerf system.
    """

    _instance: "AIPerfUI | None" = None

    def __init__(self) -> None:
        super().__init__()

    @classmethod
    def get_instance(cls) -> "AIPerfUI":
        """Get the singleton instance of the AIPerfUI."""
        if cls._instance is None:
            cls._instance = AIPerfUI()
        return cls._instance  # type: ignore[reportUnboundVariable]

    async def process_final_results(self, message: ProfileResultsMessage) -> None:
        """Export the final results."""
        print(message.records)
        self.console_exporter.export(message.records)
        self.console.print("[bold green]Profile complete!")
