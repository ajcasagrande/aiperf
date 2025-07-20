# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

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
from rich.text import Text
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from aiperf.common.enums import CreditPhase
from aiperf.progress.progress_tracker import ProgressTracker


class SimpleProfileProgressWidget(Widget):
    """Simple textual widget that displays Rich progress bars for profile execution."""

    DEFAULT_CSS = """
    SimpleProfileProgressWidget {
        height: 1fr;
        border: round $primary;
        border-title-color: $primary;
        padding: 1;
    }

    #status-display {
        height: auto;
        margin: 0 0 1 0;
    }

    #progress-display {
        height: 1fr;
    }
    """

    def __init__(self, progress_tracker: ProgressTracker | None = None) -> None:
        super().__init__()
        self.progress_tracker = progress_tracker
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
        self.processing_task_id: TaskID | None = None

        self.status_widget: Static | None = None
        self.progress_widget: Static | None = None

    def compose(self) -> ComposeResult:
        self.status_widget = Static(self._get_status_text(), id="status-display")
        self.progress_widget = Static(self.progress, id="progress-display")

        yield self.status_widget
        yield self.progress_widget

    def set_progress_tracker(self, progress_tracker: ProgressTracker) -> None:
        """Set the progress tracker and reset progress bars."""
        self.progress_tracker = progress_tracker
        self._reset_progress_bars()
        self.update_display()

    def update_display(self) -> None:
        """Update the progress display."""
        if not self.status_widget or not self.progress_widget:
            return

        # Update status text
        self.status_widget.update(self._get_status_text())

        # Update progress bars
        self._update_progress_bars()

        # Update border title
        if self.progress_tracker and self.progress_tracker.current_profile_run:
            profile_id = self.progress_tracker.current_profile_run.profile_id
            self.border_title = f"Profile Progress: {profile_id or 'Unknown'}"
        else:
            self.border_title = "Profile Progress"

    def _get_status_text(self) -> RenderableType:
        """Get current status as Rich text."""
        if not self.progress_tracker or not self.progress_tracker.current_profile_run:
            return Text("Waiting for profile run...", style="dim yellow")

        profile = self.progress_tracker.current_profile_run

        if profile.is_complete:
            return Text("Profile complete", style="bold green")
        elif profile.is_started:
            active_phase = self.progress_tracker.active_phase
            if active_phase:
                return Text(f"Running {active_phase.value}", style="bold cyan")
            return Text("Running", style="bold yellow")
        else:
            return Text("Preparing...", style="dim")

    def _update_progress_bars(self) -> None:
        """Update progress bars based on current tracker state."""
        if not self.progress_tracker or not self.progress_tracker.current_profile_run:
            return

        profile = self.progress_tracker.current_profile_run

        # Handle warmup phase
        if CreditPhase.WARMUP in profile.phase_infos:
            warmup_phase = profile.phase_infos[CreditPhase.WARMUP]
            if self.warmup_task_id is None and warmup_phase.total_expected_requests:
                self.warmup_task_id = self.progress.add_task(
                    "Warmup requests", total=warmup_phase.total_expected_requests
                )
            elif self.warmup_task_id is not None:
                self.progress.update(
                    self.warmup_task_id, completed=warmup_phase.completed or 0
                )
                if warmup_phase.is_complete:
                    self.progress.update(
                        self.warmup_task_id,
                        description="[green]Warmup complete[/green]",
                    )

        # Handle profiling phase
        if CreditPhase.PROFILING in profile.phase_infos:
            profiling_phase = profile.phase_infos[CreditPhase.PROFILING]
            if (
                self.profiling_task_id is None
                and profiling_phase.total_expected_requests
            ):
                self.profiling_task_id = self.progress.add_task(
                    "Profiling requests", total=profiling_phase.total_expected_requests
                )
            elif self.profiling_task_id is not None:
                self.progress.update(
                    self.profiling_task_id, completed=profiling_phase.completed or 0
                )
                if profiling_phase.is_complete:
                    self.progress.update(
                        self.profiling_task_id,
                        description="[green]Profiling complete[/green]",
                    )

            # Add processing progress for profiling phase
            if (
                self.processing_task_id is None
                and profiling_phase.total_expected_requests
                and profiling_phase.is_started
            ):
                self.processing_task_id = self.progress.add_task(
                    "Processing results", total=profiling_phase.total_expected_requests
                )
            elif self.processing_task_id is not None:
                self.progress.update(
                    self.processing_task_id, completed=profiling_phase.processed or 0
                )
                if (
                    profiling_phase.is_complete
                    and profiling_phase.processed
                    == profiling_phase.total_expected_requests
                ):
                    self.progress.update(
                        self.processing_task_id,
                        description="[green]Processing complete[/green]",
                    )

        # Refresh the progress widget
        if self.progress_widget:
            self.progress_widget.update(self.progress)

    def _reset_progress_bars(self) -> None:
        """Reset all progress bars."""
        if self.warmup_task_id is not None:
            self.progress.remove_task(self.warmup_task_id)
            self.warmup_task_id = None

        if self.profiling_task_id is not None:
            self.progress.remove_task(self.profiling_task_id)
            self.profiling_task_id = None

        if self.processing_task_id is not None:
            self.progress.remove_task(self.processing_task_id)
            self.processing_task_id = None
