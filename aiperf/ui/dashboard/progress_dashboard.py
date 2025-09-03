# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.visual import VisualType
from textual.widgets import ProgressBar, Static

from aiperf.common.enums import CreditPhase
from aiperf.common.models import RecordsStats, RequestsStats
from aiperf.ui.dashboard.custom_widgets import MaximizableWidget
from aiperf.ui.utils import format_elapsed_time, format_eta


class ProgressDashboard(Container, MaximizableWidget):
    """Textual widget that displays Textual progress bars for profile execution."""

    DEFAULT_CSS = """
    ProgressDashboard {
        height: 1fr;
        border: round $primary;
        border-title-color: $primary;
        border-title-style: bold;
        border-title-align: center;
        padding: 0 1 0 1;
    }
    #progress-container {
        height: auto;
        margin: 0 1 1 1;
    }
    .phase-label {
        height: 1;
        color: $primary;
        text-style: bold;
        margin: 0 0 0 0;
    }
    .phase-label.warmup {
        color: $warning;
    }
    .phase-label.profiling {
        color: $primary;
    }
    .phase-label.records {
        color: $success;
    }
    .phase-label.complete {
        color: $success;
    }
    .phase-progress {
        height: 1;
        margin: 0 0 1 0;
    }
    .phase-progress.warmup {
        color: $warning;
    }
    .phase-progress.profiling {
        color: $primary;
    }
    .phase-progress.records {
        color: $success;
    }
    .hidden {
        display: none;
    }
    #stats-display {
        height: auto;
    }
    #stats-display.no-stats {
        height: 1fr;
        content-align: center middle;
        color: $warning;
        text-style: italic;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.border_title = "Profile Progress"

        self.warmup_progress: ProgressBar | None = None
        self.profiling_progress: ProgressBar | None = None
        self.records_progress: ProgressBar | None = None
        self.stats_widget: Static | None = None
        self.records_stats: RecordsStats | None = None
        self.profiling_stats: RequestsStats | None = None
        self.warmup_stats: RequestsStats | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="progress-container"):
            # Warmup progress
            yield Static("Warmup", id="warmup-label", classes="hidden phase-label")
            self.warmup_progress = ProgressBar(
                total=100,
                show_eta=True,
                show_percentage=True,
                id="warmup-progress",
                classes="hidden phase-progress warmup",
            )
            yield self.warmup_progress

            # Profiling progress
            yield Static(
                "Profiling", id="profiling-label", classes="hidden phase-label"
            )
            self.profiling_progress = ProgressBar(
                total=100,
                show_eta=True,
                show_percentage=True,
                id="profiling-progress",
                classes="hidden phase-progress profiling",
            )
            yield self.profiling_progress

            # Records progress
            yield Static(
                "Records Processing", id="records-label", classes="hidden phase-label"
            )
            self.records_progress = ProgressBar(
                total=100,
                show_eta=True,
                show_percentage=True,
                id="records-progress",
                classes="hidden phase-progress records",
            )
            yield self.records_progress

        self.stats_widget = Static(
            "Waiting for profile data...",
            id="stats-display",
            classes="no-stats",
        )
        yield self.stats_widget

    def update_progress_bar(
        self,
        progress_bar: ProgressBar,
        label_id: str,
        stats: RequestsStats | RecordsStats,
    ) -> None:
        """Update a progress bar and its label."""
        if not stats.total_expected_requests:
            return

        # Show the progress bar and label if they're hidden
        if progress_bar.has_class("hidden"):
            progress_bar.remove_class("hidden")
            label = self.query_one(f"#{label_id}")
            label.remove_class("hidden")

        # Update progress
        progress_bar.update(
            progress=stats.finished or 0, total=stats.total_expected_requests
        )

        # Update label color when complete
        if stats.is_complete:
            label = self.query_one(f"#{label_id}")
            label.add_class("complete")

    def on_warmup_progress(self, warmup_stats: RequestsStats) -> None:
        """Callback for warmup progress updates."""
        if not self.warmup_stats:
            self.query_one("#stats-display").remove_class("no-stats")
        self.warmup_stats = warmup_stats
        if self.warmup_progress:
            self.update_progress_bar(self.warmup_progress, "warmup-label", warmup_stats)
        self.update_display(CreditPhase.WARMUP, self.warmup_stats)

    def on_profiling_progress(self, profiling_stats: RequestsStats) -> None:
        """Callback for profiling progress updates."""
        if not self.profiling_stats:
            self.query_one("#stats-display").remove_class("no-stats")
        self.profiling_stats = profiling_stats
        if self.profiling_progress:
            self.update_progress_bar(
                self.profiling_progress, "profiling-label", profiling_stats
            )
        self.update_display(CreditPhase.PROFILING, self.profiling_stats)

    def on_records_progress(self, records_stats: RecordsStats) -> None:
        """Callback for records progress updates."""
        if not self.records_stats:
            self.query_one("#stats-display").remove_class("no-stats")
        self.records_stats = records_stats
        if self.records_progress:
            self.update_progress_bar(
                self.records_progress, "records-label", records_stats
            )
        # NOTE: Send the profiling stats to the display, not the records stats
        self.update_display(CreditPhase.PROFILING, self.profiling_stats)

    def update_display(
        self, phase: CreditPhase, stats: RequestsStats | RecordsStats | None = None
    ) -> None:
        """Update the stats display."""
        if self.stats_widget:
            self.stats_widget.update(self.create_stats_table(phase, stats))

    def _get_status(self) -> Text:
        """Get the status of the profile."""
        if self.records_stats and self.records_stats.is_complete:
            return Text("Complete", style="bold green")
        elif self.profiling_stats and self.profiling_stats.is_complete:
            return Text("Processing", style="bold green")
        elif self.profiling_stats:
            return Text("Profiling", style="bold yellow")
        elif self.warmup_stats:
            return Text("Warmup", style="bold yellow")
        else:
            return Text("Waiting for profile data...", style="dim")

    def create_stats_table(
        self, phase: CreditPhase, stats: RequestsStats | RecordsStats | None = None
    ) -> VisualType:
        """Create a table with the profile status and progress."""
        stats_table = Table.grid(padding=(0, 1, 0, 0))
        stats_table.add_column(style="bold cyan", justify="right")
        stats_table.add_column(style="bold white")

        if not stats:
            return stats_table

        stats_table.add_row("Status:", self._get_status())

        if stats.total_expected_requests:
            stats_table.add_row(
                "Progress:",
                f"{stats.finished or 0:,} / {stats.total_expected_requests:,} requests "
                f"({stats.progress_percent:.1f}%)",
            )

        if self.records_stats:
            error_percent = 0.0
            if self.records_stats.total_records:
                error_percent = (
                    (self.records_stats.errors or 0) / self.records_stats.total_records * 100
                )  # fmt: skip
            error_color = (
                "green"
                if error_percent == 0
                else "red"
                if error_percent > 10
                else "yellow"
            )
            stats_table.add_row(
                "Errors:",
                f"[{error_color}]{self.records_stats.errors or 0:,} / {self.records_stats.total_records or 0:,} "
                f"({error_percent:.1f}%)[/{error_color}]",
            )

        stats_table.add_row("Request Rate:", f"{stats.per_second or 0:,.1f} requests/s")

        if self.records_stats:
            stats_table.add_row(
                "Processing Rate:",
                f"{self.records_stats.per_second or 0:,.1f} records/s",
            )

        if not stats.is_complete:
            # Display request stats while profiling
            if stats.start_ns:
                stats_table.add_row("Elapsed:", format_elapsed_time(stats.elapsed_time))
            if stats.eta:
                stats_table.add_row("ETA:", format_eta(stats.eta))
        elif self.records_stats:
            # Display record processing stats after profiling
            if self.records_stats.start_ns:
                stats_table.add_row(
                    "Elapsed:", format_elapsed_time(self.records_stats.elapsed_time)
                )
            if self.records_stats.eta:
                stats_table.add_row("Records ETA:", format_eta(self.records_stats.eta))

        return stats_table
