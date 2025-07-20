# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from rich.console import Console, Group
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

from aiperf.common.enums import CreditPhase
from aiperf.progress.progress_tracker import ProgressTracker


class SimpleProfileProgress:
    """Simple Rich-based progress display for profile execution."""

    def __init__(
        self, progress_tracker: ProgressTracker, console: Console | None = None
    ) -> None:
        self.progress_tracker = progress_tracker
        self.console = console or Console()

        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            expand=True,
        )

        self.warmup_task_id: TaskID | None = None
        self.profiling_task_id: TaskID | None = None
        self.processing_task_id: TaskID | None = None

    def start(self) -> None:
        """Start the progress display."""
        self.progress.start()

    def stop(self) -> None:
        """Stop the progress display."""
        self.progress.stop()

    def update(self) -> None:
        """Update progress bars based on current tracker state."""
        if not self.progress_tracker.current_profile_run:
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

    def get_status_text(self) -> Text:
        """Get current status as Rich text."""
        if not self.progress_tracker.current_profile_run:
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

    def render(self) -> Group:
        """Render the complete progress display."""
        self.update()
        return Group(self.get_status_text(), self.progress)

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
