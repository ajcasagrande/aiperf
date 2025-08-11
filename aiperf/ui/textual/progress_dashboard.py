# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from rich.align import Align
from rich.console import RenderableType
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
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.timer import Timer
from textual.widgets import Static

from aiperf.common.enums import CreditPhase
from aiperf.common.models import RecordsStats, RequestsStats
from aiperf.common.utils import format_duration


class ProgressDashboard(Container):
    """Textual widget that displays Rich progress bars for profile execution."""

    DEFAULT_CSS = """
    ProgressDashboard {
        height: 1fr;
        border: round $primary;
        border-title-color: $primary;
        border-title-style: bold;
        padding: 0 1 0 1;
    }
    #status-display {
        height: auto;
        margin: 0 1 0 1;
    }
    #progress-display {
        height: auto;
        margin: 0 1 0 1;
    }
    #stats-display {
        height: auto;
    }
    #no-stats-message {
        height: 1fr;
        content-align: center middle;
        color: $warning;
        text-style: italic;
    }
    """

    SPINNER_REFRESH_RATE = 0.1  # 10 FPS

    def __init__(self) -> None:
        super().__init__()
        self.border_title = "Profile Progress"

        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            expand=True,
        )

        self.warmup_task_id: TaskID | None = None
        self.profiling_task_id: TaskID | None = None
        self.records_task_id: TaskID | None = None
        self.progress_widget: Static | None = None
        self.stats_widget: Static | None = None
        self.records_stats: RecordsStats | None = None
        self.requests_stats: dict[CreditPhase, RequestsStats] = {}
        self.refresh_timer: Timer | None = None

    def on_mount(self) -> None:
        """Set up the refresh timer when the widget is mounted."""
        self.refresh_timer = self.set_interval(
            self.SPINNER_REFRESH_RATE, self._refresh_display
        )

    def on_unmount(self) -> None:
        """Clean up the timer when the widget is unmounted."""
        if self.refresh_timer:
            self.refresh_timer.stop()

    def _refresh_display(self) -> None:
        """Timer callback to refresh the display for smooth spinner animation."""
        if not self.progress_widget or not self.stats_widget:
            return

        # Only update the progress widget to refresh spinners
        self.progress_widget.update(self.progress)

    def compose(self) -> ComposeResult:
        self.progress_widget = Static(self.progress, id="progress-display")
        self.stats_widget = Static(self._get_stats_table(), id="stats-display")

        yield self.progress_widget
        yield self.stats_widget

    def on_requests_phase_progress(
        self, phase: CreditPhase, requests_stats: RequestsStats
    ) -> None:
        """Callback for requests phase progress updates."""
        self.requests_stats[phase] = requests_stats
        if phase == CreditPhase.WARMUP:
            self.update_warmup_progress(requests_stats)
        elif phase == CreditPhase.PROFILING:
            self.update_profiling_progress(requests_stats)
        self.update_display()

    def update_warmup_progress(self, stats: RequestsStats) -> None:
        """Update the warmup progress."""
        if self.warmup_task_id is None and stats.total_expected_requests:
            self.warmup_task_id = self.progress.add_task(
                "Warmup", total=stats.total_expected_requests
            )
        elif self.warmup_task_id is not None:
            self.progress.update(self.warmup_task_id, completed=stats.completed or 0)
            if stats.is_complete:
                self.progress.update(
                    self.warmup_task_id,
                    description="[green]Warmup[/green]",
                )

    def update_profiling_progress(self, stats: RequestsStats) -> None:
        """Update the profiling progress."""
        if self.profiling_task_id is None and stats.total_expected_requests:
            self.profiling_task_id = self.progress.add_task(
                "Profiling", total=stats.total_expected_requests
            )
        elif self.profiling_task_id is not None:
            self.progress.update(self.profiling_task_id, completed=stats.completed or 0)
            if stats.is_complete:
                self.progress.update(
                    self.profiling_task_id,
                    description="[green]Profiling[/green]",
                )

    def on_records_progress(self, records_stats: RecordsStats) -> None:
        """Callback for records progress updates."""
        self.records_stats = records_stats

        if self.records_task_id is None and records_stats.total_expected_requests:
            self.records_task_id = self.progress.add_task(
                "Records", total=records_stats.total_expected_requests
            )
        elif self.records_task_id is not None:
            self.progress.update(
                self.records_task_id, completed=records_stats.total_records or 0
            )
            if records_stats.is_complete:
                self.progress.update(
                    self.records_task_id,
                    description="[green]Records[/green]",
                )

        self.update_display()

    def update_display(self) -> None:
        """Update the progress display."""
        if not self.progress_widget or not self.stats_widget:
            return
        self.progress_widget.update(self.progress)
        self.stats_widget.update(self._get_stats_table())

    def _get_stats_table(self) -> RenderableType:
        """Create a statistics table similar to the rich version."""
        if not self.records_stats or not self.records_stats.total_expected_requests:
            return Align(
                Text("No profile data available", style="bold italic orange"),
                align="center",
            )

        if not self.records_stats:
            return Align(
                Text("No profile data available", style="bold italic orange"),
                align="center",
            )

        # Create table with padding (same as rich version)
        stats_table = Table.grid(padding=(0, 1, 0, 0))
        stats_table.add_column(style="bold cyan", justify="right")
        stats_table.add_column(style="bold white")

        # Status
        if self.records_stats.is_complete:
            status = Text("Complete", style="bold green")
        else:
            status = Text("Processing", style="bold yellow")

        # Error calculations
        error_percent = 0.0
        if self.records_stats.processed and self.records_stats.processed > 0:
            error_percent = (
                (self.records_stats.errors or 0) / self.records_stats.processed * 100
            )

        error_color = (
            "green" if error_percent == 0 else "red" if error_percent > 10 else "yellow"
        )

        # Add rows to table
        stats_table.add_row("Status:", status)

        # Progress information
        stats = self.requests_stats.get(CreditPhase.PROFILING)
        if stats and stats.total_expected_requests:
            stats_table.add_row(
                "Progress:",
                f"{stats.completed or 0:,} / {stats.total_expected_requests:,} requests "
                f"({stats.progress_percent:.1f}%)",
            )

        # Error information
        stats_table.add_row(
            "Errors:",
            f"[{error_color}]{self.records_stats.errors or 0:,} / {self.records_stats.total_records or 0:,} ({error_percent:.1f}%)[/{error_color}]",
        )

        # Rates
        if stats:
            stats_table.add_row("Request Rate:", f"{stats.per_second or 0:.1f} req/s")
        stats_table.add_row(
            "Processing Rate:", f"{self.records_stats.per_second or 0:.1f} req/s"
        )

        # Timing information
        if stats and stats.start_ns:
            stats_table.add_row("Elapsed:", format_duration(stats.elapsed_time))
        if stats and stats.eta:
            stats_table.add_row("Request ETA:", format_duration(stats.eta))
        if self.records_stats and self.records_stats.eta:
            stats_table.add_row("Results ETA:", format_duration(self.records_stats.eta))

        return stats_table
