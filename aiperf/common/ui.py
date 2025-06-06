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

from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import MessageType
from aiperf.common.messages import Message, ProfileProgressMessage


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


class AIPerfUI:
    """
    AIPerfUI is a class that provides a UI for the AIPerf system.
    """

    def __init__(self) -> None:
        self.console = Console()
        self.live: Live | None = None
        self.progress: Progress | None = None
        self.task_id: TaskID | None = None
        self.start_time_ns: int | None = None
        self.last_update_time: float | None = None

    def run(self) -> None:
        """Start the live dashboard."""
        if self.live is None:
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

            # Create the main dashboard layout
            dashboard = self._create_dashboard()

            self.live = Live(
                dashboard,
                console=self.console,
                refresh_per_second=4,
                vertical_overflow="visible",
            )
            self.live.start()

    def stop(self) -> None:
        """Stop the live dashboard."""
        if self.live:
            self.live.stop()
            self.live = None
        self.progress = None
        self.task_id = None

    def update(self, message: Message) -> None:
        match message.message_type:
            case MessageType.PROFILE_PROGRESS:
                self.update_profile_progress(message)
            case _:
                pass

    def update_profile_progress(self, progress: ProfileProgressMessage) -> None:
        """
        Update the profile progress with rich dashboard display.
        """
        if not self.progress or not self.live:
            return

        payload = progress.payload
        current_time = time.time()

        # Initialize start time and task on first update
        if self.start_time_ns is None or self.task_id is None:
            self.start_time_ns = payload.sweep_start_ns
            self.task_id = self.progress.add_task(
                "Processing Requests",
                total=payload.total,
                completed=payload.completed,
            )

        # Calculate requests per second
        elapsed_seconds = (payload.timestamp - self.start_time_ns) / NANOS_PER_SECOND
        req_per_second = (
            payload.completed / elapsed_seconds if elapsed_seconds > 0 else 0.0
        )

        # Update the progress task
        self.progress.update(
            self.task_id,
            completed=payload.completed,
            total=payload.total,
            req_per_second=req_per_second,
        )

        # Update the live display
        self.live.update(self._create_dashboard())
        self.last_update_time = current_time

    def _create_dashboard(self) -> Panel:
        """Create the main dashboard layout."""
        if not self.progress:
            return Panel(
                Text("Waiting for profile data...", style="dim"),
                title="AIPerf Dashboard",
                border_style="blue",
            )

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
