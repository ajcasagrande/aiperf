# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import time
from abc import ABC, abstractmethod
from typing import ClassVar

from rich.align import Align, AlignMethod
from rich.console import Console, Group, RenderableType
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.style import StyleType
from rich.table import Table
from rich.text import Text

from aiperf.common.hooks import (
    AIPerfLifecycleMixin,
    aiperf_auto_task,
    on_start,
    on_stop,
)
from aiperf.common.messages import WorkerHealthMessage
from aiperf.common.utils import format_bytes, format_duration
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.logs_mixin import LogsDashboardMixin

logger = logging.getLogger(__name__)


class DashboardElement(ABC):
    """Base class for dashboard elements."""

    key: ClassVar[str]
    title: ClassVar[Text | str | None] = None
    border_style: ClassVar[StyleType | None] = None
    title_align: ClassVar[AlignMethod] = "center"
    height: ClassVar[int | None] = None
    width: ClassVar[int | None] = None
    expand: ClassVar[bool] = True

    @abstractmethod
    def get_content(self) -> RenderableType:
        """Get the content for the dashboard element."""
        raise NotImplementedError("Subclasses must implement get_content")

    def get_panel(self) -> Panel:
        """Get the panel for the dashboard element."""
        return Panel(
            self.get_content(),
            title=self.title,
            border_style=self.border_style if self.border_style else "none",
            title_align=self.title_align,
            height=self.height,
            width=self.width,
            expand=self.expand,
        )


class HeaderElement(DashboardElement):
    """Header element for the dashboard."""

    key = "header"
    border_style = "bright_green"

    def get_content(self) -> RenderableType:
        """Get the content for the header element."""
        return Align.center(Text("NVIDIA AIPerf Dashboard", style="bold bright_green"))


class ProfileProgressElement(DashboardElement):
    """Profile progress element for the dashboard."""

    key = "profile_progress"
    title = Text("Profile Progress", style="bold")
    border_style = "cyan"

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
        self.progress_tracker = progress_tracker
        self.progress_task_id: TaskID | None = None
        self.records_task_id: TaskID | None = None
        self.progress_bar = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            expand=True,
        )
        self.records_progress_bar = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            expand=True,
        )

    def get_content(self) -> RenderableType:
        """Create the progress panel with performance metrics."""

        if not self.progress_tracker.current_profile:
            return Align.center(
                Text("Waiting for performance data...", style="dim yellow"),
                vertical="middle",
            )

        profile = self.progress_tracker.current_profile

        # Update progress task
        if self.progress_task_id is None and profile.total_expected_requests:
            self.progress_task_id = self.progress_bar.add_task(
                "Executing requests...", total=profile.total_expected_requests
            )
        elif self.progress_task_id is not None:
            self.progress_bar.update(
                self.progress_task_id, completed=profile.requests_completed or 0
            )

        # Update records progress task
        if self.records_task_id is None and profile.total_expected_requests:
            self.records_task_id = self.records_progress_bar.add_task(
                "Processing results...", total=profile.total_expected_requests
            )
        elif self.records_task_id is not None:
            self.records_progress_bar.update(
                self.records_task_id, completed=profile.requests_processed or 0
            )

        progress_table = Table.grid(padding=(0, 1, 0, 0))
        progress_table.add_column(style="bold cyan", justify="right")
        progress_table.add_column(style="bold white")

        if profile.is_complete:
            status = Text("Complete", style="bold green")
        elif profile.was_cancelled:
            status = Text("Cancelled", style="bold red")
        else:
            status = Text("Processing", style="bold yellow")

        error_rate = 0.0
        if profile.requests_processed and profile.requests_processed > 0:
            error_rate = (
                (profile.request_errors or 0) / profile.requests_processed * 100
            )

        error_color = (
            "green" if error_rate == 0 else "red" if error_rate > 10 else "yellow"
        )

        progress_table.add_row("Status:", status)
        progress_table.add_row(
            "Progress:",
            f"{profile.requests_completed or 0:,} / {profile.total_expected_requests or 0:,} requests "
            f"({(profile.requests_completed or 0) / (profile.total_expected_requests or 1) * 100:.1f}%)",
        )
        progress_table.add_row(
            "Errors:",
            f"[{error_color}]{profile.request_errors or 0:,} / {profile.requests_processed or 0:,} ({error_rate:.1f}%)[/{error_color}]",
        )
        progress_table.add_row(
            "Request Rate:", f"{profile.requests_per_second or 0:.1f} req/s"
        )
        progress_table.add_row(
            "Processing Rate:", f"{profile.processed_per_second or 0:.1f} req/s"
        )
        progress_table.add_row("Elapsed:", format_duration(profile.elapsed_time))
        progress_table.add_row("Request ETA:", format_duration(profile.eta))
        progress_table.add_row("Results ETA:", format_duration(profile.processing_eta))

        return Group(self.progress_bar, self.records_progress_bar, progress_table)


class WorkerStatusElement(DashboardElement):
    """Worker status element for the dashboard."""

    key = "worker_status"
    title = Text("Worker Status", style="bold")
    border_style = "blue"

    def __init__(
        self,
        worker_health: dict[str, WorkerHealthMessage],
        worker_last_seen: dict[str, float],
    ) -> None:
        super().__init__()
        self.worker_health = worker_health
        self.worker_last_seen = worker_last_seen

    def get_content(self) -> RenderableType:
        """Get the content for the worker status element."""
        if not self.worker_health:
            return Align.center(
                Text("No worker data available", style="dim yellow"), vertical="middle"
            )

        workers_table = Table.grid(padding=(0, 2, 0, 0))
        workers_table.add_column("Worker ID", style="cyan", width=15)
        workers_table.add_column("Status", width=9)
        workers_table.add_column("Tasks", min_width=6, justify="right")
        workers_table.add_column("Completed", min_width=6, justify="right")
        workers_table.add_column("CPU", min_width=5, justify="right")
        workers_table.add_column("Memory", min_width=6, justify="right")
        workers_table.add_column("Read", min_width=8, justify="right")
        workers_table.add_column("Write", min_width=8, justify="right")

        workers_table.add_row(
            *[column.header for column in workers_table.columns], style="bold"
        )

        current_time = time.time()

        # Summary counters
        healthy_count = 0
        warning_count = 0
        error_count = 0
        idle_count = 0
        stale_count = 0

        for service_id, health in sorted(self.worker_health.items()):
            worker_name = service_id
            last_seen = self.worker_last_seen.get(service_id, current_time)

            # Determine status
            if current_time - last_seen > 30:  # 30 seconds
                status = Text("Stale", style="dim white")
                stale_count += 1
            else:
                error_rate = (
                    health.failed_tasks / health.total_tasks
                    if health.total_tasks > 0
                    else 0
                )

                if error_rate > 0.1:  # More than 10% error rate
                    status = Text("Error", style="bold red")
                    error_count += 1
                elif health.cpu_usage > 75:  # High CPU usage
                    status = Text("High Load", style="bold yellow")
                    warning_count += 1
                elif health.total_tasks == 0:  # No tasks processed
                    status = Text("Idle", style="dim")
                    idle_count += 1
                else:
                    status = Text("Healthy", style="bold green")
                    healthy_count += 1

            memory_mb = health.memory_usage
            if memory_mb >= 1024:
                memory_display = f"{memory_mb / 1024:.1f} GB"
            else:
                memory_display = f"{memory_mb:.0f} MB"

            workers_table.add_row(
                worker_name,
                status,
                f"{health.in_progress_tasks:,}",
                f"{health.completed_tasks:,}",
                f"{health.cpu_usage:.1f}%",
                memory_display,
                f"{format_bytes(health.io_counters.read_chars)}",
                f"{format_bytes(health.io_counters.write_chars)}",
            )

        # Create summary
        summary_text = Text.assemble(
            Text("Summary: ", style="bold"),
            Text(f"{healthy_count} healthy", style="green"),
            Text(" • "),
            Text(f"{warning_count} high load", style="yellow"),
            Text(" • "),
            Text(f"{error_count} errors", style="red"),
            Text(" • "),
            Text(f"{idle_count} idle", style="dim"),
            Text(" • "),
            Text(f"{stale_count} stale", style="dim white"),
        )

        return Group(summary_text, workers_table)


class AIPerfRichDashboard(LogsDashboardMixin, AIPerfLifecycleMixin):
    """Main AIPerf Rich Dashboard with live updates."""

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
        self.console = Console()
        self.progress_tracker = progress_tracker
        self.worker_health: dict[str, WorkerHealthMessage] = {}
        self.worker_last_seen: dict[str, float] = {}

        self.elements: dict[str, DashboardElement] = {
            HeaderElement.key: HeaderElement(),
            ProfileProgressElement.key: ProfileProgressElement(self.progress_tracker),
            WorkerStatusElement.key: WorkerStatusElement(
                self.worker_health, self.worker_last_seen
            ),
        }

        self.layout = self._create_layout()
        self.live: Live | None = None
        self.running = False

    def _create_layout(self) -> Layout:
        """Create the main layout for the dashboard."""
        layout = Layout()

        layout.split_column(
            Layout(name=HeaderElement.key, size=3),
            Layout(name="body", ratio=2),
            Layout(name="logs", size=12),
        )

        layout["body"].split_row(Layout(name="left"), Layout(name="right", ratio=1))

        layout["left"].split_column(
            Layout(name=ProfileProgressElement.key),
        )

        layout["right"].split_row(Layout(name=WorkerStatusElement.key, ratio=1))

        return layout

    def _get_logs_panel(self) -> Panel:
        """Create the logs panel with recent log entries."""
        return Panel(
            self._create_logs_table(),
            title="[bold]System Logs[/bold]",
            border_style="yellow",
            height=12,
            title_align="left",
        )

    @aiperf_auto_task(interval=0.1)
    async def _update_logs(self) -> None:
        """Update the dashboard display."""
        if not self.running:
            return

        self.layout["logs"].update(self._get_logs_panel())

    def update_display(self) -> None:
        """Update the dashboard display."""
        if not self.running:
            return

        try:
            for element in self.elements.values():
                self.layout[element.key].update(element.get_panel())
        except Exception as e:
            logger.error(f"Error updating dashboard display: {e}")

    def refresh_element(self, element_key: str) -> None:
        """Refresh the specified element."""
        self.layout[element_key].update(self.elements[element_key].get_panel())

    def update_worker_health(self, health_message: WorkerHealthMessage) -> None:
        """Update worker health information."""
        self.worker_health[health_message.service_id] = health_message
        self.worker_last_seen[health_message.service_id] = time.time()

    @on_start
    async def _start(self) -> None:
        """Start the live dashboard."""
        self.running = True
        self.live = Live(
            self.layout,
            console=self.console,
            refresh_per_second=4,
            screen=True,
        )
        self.live.start()
        self.update_display()

    @on_stop
    async def _stop(self) -> None:
        """Stop the live dashboard."""
        self.running = False

        if self.live:
            # Store final state before stopping, then print it to persist it.
            self.final_renderable = self.live.renderable
            self.live.stop()
            if self.final_renderable:
                self.console.print(self.final_renderable)
