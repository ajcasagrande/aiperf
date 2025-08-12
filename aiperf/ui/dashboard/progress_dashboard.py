# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

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
from textual.visual import VisualType
from textual.widgets import Static

from aiperf.common.enums import CreditPhase
from aiperf.common.models import RecordsStats, RequestsStats
from aiperf.common.models.progress_models import StatsProtocol
from aiperf.ui.utils import format_duration


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
    #stats-display.no-stats {
        height: 1fr;
        content-align: center middle;
        color: $warning 50%;
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

        self.task_ids: dict[str, TaskID] = {}
        self.progress_widget: Static | None = None
        self.stats_widget: Static | None = None
        self.records_stats: RecordsStats | None = None
        self.requests_stats: dict[CreditPhase, RequestsStats] = {}
        self.refresh_timer: Timer | None = None

    def on_mount(self) -> None:
        """Set up the refresh timer when the widget is mounted."""
        self.refresh_timer = self.set_interval(
            self.SPINNER_REFRESH_RATE, self.refresh_timer_callback
        )

    def on_unmount(self) -> None:
        """Clean up the timer when the widget is unmounted."""
        if self.refresh_timer:
            self.refresh_timer.stop()

    def refresh_timer_callback(self) -> None:
        """Callback for the refresh timer to update the progress widget."""
        if self.progress_widget:
            self.progress_widget.update(self.progress)

    def compose(self) -> ComposeResult:
        self.progress_widget = Static(self.progress, id="progress-display")
        yield self.progress_widget

        self.stats_widget = Static(
            "Waiting for profile data...",
            id="stats-display",
            classes="no-stats",
        )
        yield self.stats_widget

    def create_or_update_progress(self, name: str, stats: StatsProtocol) -> None:
        """Create or update the progress for a given task."""
        task_id = self.task_ids.get(name)
        if task_id is None and stats.total_expected_requests:
            self.task_ids[name] = self.progress.add_task(
                name, total=stats.total_expected_requests
            )
        elif task_id is not None:
            self.progress.update(task_id, completed=stats.finished)
            if stats.is_complete:
                self.progress.update(
                    task_id,
                    description=f"[green]{name}[/green]",
                )

    def on_requests_phase_progress(
        self, phase: CreditPhase, requests_stats: RequestsStats
    ) -> None:
        """Callback for requests phase progress updates."""
        if not self.requests_stats:
            self.query_one("#stats-display").remove_class("no-stats")
        self.requests_stats[phase] = requests_stats
        self.create_or_update_progress(phase.name.title(), requests_stats)
        self.update_display()

    def on_records_progress(self, records_stats: RecordsStats) -> None:
        """Callback for records progress updates."""
        if not self.records_stats:
            self.query_one("#stats-display").remove_class("no-stats")
        self.records_stats = records_stats
        self.create_or_update_progress("Records", records_stats)
        self.update_display()

    def update_display(self) -> None:
        """Update the progress display."""
        if self.progress_widget:
            self.progress_widget.update(self.progress)
        if self.stats_widget:
            self.stats_widget.update(self.create_stats_table())

    def _get_status(self) -> Text:
        """Get the status of the profile."""
        if self.records_stats and self.records_stats.is_complete:
            return Text("Complete", style="bold green")
        elif self.requests_stats.get(CreditPhase.PROFILING):
            return Text("Profiling", style="bold yellow")
        elif self.requests_stats.get(CreditPhase.WARMUP):
            return Text("Warmup", style="bold yellow")
        else:
            return Text("Waiting for profile data...", style="dim")

    def create_stats_table(self) -> VisualType:
        """Create a statistics table similar to the rich version."""
        stats_table = Table.grid(padding=(0, 1, 0, 0))
        stats_table.add_column(style="bold cyan", justify="right")
        stats_table.add_column(style="bold white")

        profiling_stats = self.requests_stats.get(CreditPhase.PROFILING)
        if not profiling_stats:
            return stats_table

        stats_table.add_row("Status:", self._get_status())

        if profiling_stats.total_expected_requests:
            stats_table.add_row(
                "Progress:",
                f"{profiling_stats.completed or 0:,} / {profiling_stats.total_expected_requests:,} requests "
                f"({profiling_stats.progress_percent:.1f}%)",
            )

        if not self.records_stats:
            return stats_table

        error_percent = 0.0
        if self.records_stats.total_records:
            error_percent = (
                (self.records_stats.errors or 0) / self.records_stats.total_records * 100
            )  # fmt: skip
        error_color = (
            "green" if error_percent == 0 else "red" if error_percent > 10 else "yellow"
        )
        stats_table.add_row(
            "Errors:",
            f"[{error_color}]{self.records_stats.errors or 0:,} / {self.records_stats.total_records or 0:,} "
            f"({error_percent:.1f}%)[/{error_color}]",
        )

        if not profiling_stats.is_complete:
            # Display request stats while profiling
            stats_table.add_row(
                "Request Rate:", f"{profiling_stats.per_second or 0:.1f} req/s"
            )
            if profiling_stats.start_ns:
                stats_table.add_row(
                    "Elapsed:", format_duration(profiling_stats.elapsed_time)
                )
            if profiling_stats.eta:
                stats_table.add_row(
                    "Profiling ETA:", format_duration(profiling_stats.eta)
                )
        else:
            # Display record processing stats after profiling
            stats_table.add_row(
                "Processing Rate:", f"{self.records_stats.per_second or 0:.1f} records/sec"
            )  # fmt: skip
            if self.records_stats.start_ns:
                stats_table.add_row(
                    "Elapsed:", format_duration(self.records_stats.elapsed_time)
                )
            if self.records_stats.eta:
                stats_table.add_row(
                    "Records ETA:", format_duration(self.records_stats.eta)
                )

        return stats_table
