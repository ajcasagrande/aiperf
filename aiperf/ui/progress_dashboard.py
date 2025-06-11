#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import time

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

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.hooks import on_init, on_stop
from aiperf.common.messages import ProfileProgressMessage, ProfileStatsMessage
from aiperf.ui.base_ui import ConsoleUIMixin


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
            text = "-- req/s" if task.speed is None else f"{task.speed:,.1f} req/s"

        return Text(text, style="progress.data.speed")


class ProfileProgressDashboardMixin(ConsoleUIMixin):
    """Mixin for updating the profile progress dashboard."""

    def __init__(self) -> None:
        super().__init__()
        self.progress: Progress | None = None
        self.task_id: TaskID | None = None
        self.start_perf_counter_ns: int | None = None

        self.error_count: int = 0
        self.error_rate: float = 0.0
        self.total_completed: int = 0
        self.total_requests: int = 0

        # Per-worker statistics
        self.worker_stats: dict[str, int] = {}

    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"

        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60

        if minutes < 60:
            if remaining_seconds < 1:
                return f"{minutes}m"
            return f"{minutes}m {remaining_seconds:.0f}s"

        hours = minutes // 60
        minutes = minutes % 60

        if hours < 24:
            if minutes == 0:
                return f"{hours}h"
            return f"{hours}h {minutes}m"

        days = hours // 24
        hours = hours % 24

        if hours == 0:
            return f"{days}d"
        return f"{days}d {hours}h"

    @on_init
    def _on_init(self) -> None:
        """Create the progress bar."""
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

    def _refresh_progress_dashboard(self) -> Panel:
        """Create the main dashboard layout."""
        # Create stats table
        stats_table = Table.grid(padding=1)
        stats_table.add_column(style="cyan", no_wrap=True, min_width=12)
        stats_table.add_column(style="white")

        if self.task_id is not None and self.progress is not None:
            task = self.progress.tasks[self.task_id]

            # Calculate additional metrics
            completion_pct = (
                (task.completed / task.total * 100)
                if task.total and task.total > 0 and task.completed is not None
                else 0
            )
            elapsed_time = task.elapsed or 0

            # Status with clean indicator
            status_indicator = "●" if not task.finished else "✓"
            status_text = "Processing" if not task.finished else "Complete"
            status_style = "yellow" if not task.finished else "green"

            stats_table.add_row(
                "Status:", f"[{status_style}]{status_indicator}[/] {status_text}"
            )
            stats_table.add_row(
                "Progress:", f"{task.completed:,} / {task.total:,} requests"
            )
            stats_table.add_row("Completion:", f"{completion_pct:.1f}%")

            # Error styling based on rate
            error_style = (
                "green"
                if self.error_rate == 0
                else ("yellow" if self.error_rate < 0.05 else "red")
            )
            stats_table.add_row(
                "Errors:",
                f"[{error_style}]●[/] {self.error_count:,} / {self.total_completed:,} ({self.error_rate:.1%})",
            )
            stats_table.add_row(
                "Rate:",
                f"{task.speed:,.1f} req/s" if task.speed else "-- req/s",
            )
            stats_table.add_row("Elapsed:", self._format_duration(elapsed_time))

            if (
                task.speed
                and task.speed > 0
                and not task.finished
                and task.total is not None
                and task.completed is not None
            ):
                remaining_requests = task.total - task.completed
                eta_seconds = remaining_requests / task.speed
                stats_table.add_row("ETA:", self._format_duration(eta_seconds))

        # Combine progress bar and stats
        dashboard_content = Table.grid()
        dashboard_content.add_column()
        dashboard_content.add_row(self.progress)
        dashboard_content.add_row("")  # Spacing
        dashboard_content.add_row(stats_table)

        # Add worker stats if available
        if self.worker_stats:
            worker_stats_table = self._create_worker_stats_table()
            dashboard_content.add_row("")  # Additional spacing
            dashboard_content.add_row(worker_stats_table)

        return Panel(
            dashboard_content,
            title="[bold blue]AIPerf Profile Dashboard",
            border_style="blue",
            padding=(1, 2),
            width=self.console.width,
            height=self.console.height,
            expand=True,
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
        if self.start_perf_counter_ns is None or self.task_id is None:
            self.start_perf_counter_ns = message.sweep_start_ns
            self.total_requests = message.total
            self.task_id = self.progress.add_task(
                "Processing Requests",
                total=message.total,
                completed=message.completed,
            )

        # Calculate requests per second
        elapsed_seconds = (
            (message.request_ns or time.time_ns()) - self.start_perf_counter_ns
        ) / NANOS_PER_SECOND

        req_per_second = (
            message.completed / elapsed_seconds if (elapsed_seconds or 0) > 0 else 0.0
        )

        # Update the progress task
        self.progress.update(
            self.task_id,
            completed=message.completed,
            total=message.total,
            req_per_second=req_per_second,
        )

        # Update the live display
        self.live.update(self._refresh_progress_dashboard())

    def update_profile_stats(self, message: ProfileStatsMessage) -> None:
        """Update the profile stats."""
        if not self.progress:
            return

        self.error_count = message.error_count
        self.total_completed = message.completed + message.error_count
        self.error_rate = (
            self.error_count / self.total_completed if self.total_completed > 0 else 0.0
        )

        # Update worker statistics
        self.worker_stats = message.worker_stats.copy()

        self.live.update(self._refresh_progress_dashboard())

    def _create_worker_stats_table(self) -> Table:
        """Create a table showing per-worker statistics in a fluid grid layout."""
        if not self.worker_stats:
            worker_table = Table.grid(padding=(0, 1))
            worker_table.add_column(style="dim white", no_wrap=True, width=12)
            worker_table.add_column(style="white", justify="right")
            worker_table.add_row("Workers:", "No data")
            return worker_table

        # Sort workers by request count (descending)
        sorted_workers = sorted(
            self.worker_stats.items(), key=lambda x: x[1], reverse=True
        )

        # Calculate optimal number of columns based on console width
        # Each worker entry needs about 12 characters (e.g., "W0: 1,234")
        console_width = self.console.width if hasattr(self, "console") else 80
        available_width = console_width - 20  # Account for panel padding and margins
        entry_width = 12
        max_cols = max(1, available_width // entry_width)

        # Limit columns to a reasonable number and worker count
        num_workers = len(sorted_workers)
        cols = min(max_cols, num_workers, 6)  # Cap at 6 columns for readability

        # Create the grid table
        worker_table = Table.grid(padding=(0, 1))

        # Add header row
        worker_table.add_column(style="dim white", no_wrap=True, width=12)
        worker_table.add_column(style="white", justify="left", no_wrap=True)
        worker_table.add_row("Workers:", f"{num_workers} active")

        # Add columns for the worker grid
        grid_table = Table.grid(padding=(0, 2))  # More padding between columns
        for _ in range(cols):
            grid_table.add_column(
                style="white", justify="left", no_wrap=True, min_width=entry_width
            )

        # Add workers in rows, filling left to right
        for i in range(0, num_workers, cols):
            row_data = []
            for j in range(cols):
                if i + j < num_workers:
                    worker_id, count = sorted_workers[i + j]
                    # Clean up worker ID for display
                    display_name = worker_id
                    row_data.append(f"{display_name}: {count:,}")
                else:
                    row_data.append("")  # Empty cell for incomplete rows
            grid_table.add_row(*row_data)

        # Combine header and grid
        worker_table.add_row("", "")  # Empty row for spacing
        worker_table.add_row("", grid_table)

        return worker_table
