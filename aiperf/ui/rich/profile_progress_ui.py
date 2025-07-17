# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from rich.align import Align
from rich.console import Group, RenderableType
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

from aiperf.common.enums._timing import CreditPhase
from aiperf.common.utils import format_duration
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.rich.dashboard_element import DashboardElement


class ProfileProgressElement(DashboardElement):
    """Profile progress element for the dashboard.

    This element displays the progress of the current profile along with the progress of
    the results processing.
    """

    key = "profile_progress"
    title = Text("Profile Progress", style="bold")
    border_style = "cyan"

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
        self.progress_tracker = progress_tracker
        self.progress_task_id: TaskID | None = None
        self.records_task_id: TaskID | None = None
        self.current_phase: CreditPhase | None = None
        self.progress_task_ids: dict[CreditPhase, list[TaskID]] = {}

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

    def get_content(self) -> RenderableType:
        """Create the progress panel with benchmark status."""

        if not self.progress_tracker.current_profile_run:
            return Align.center(
                Text("Waiting for benchmark data...", style="dim yellow"),
                vertical="middle",
            )

        profile = self.progress_tracker.current_profile_run

        if self.current_phase != profile.active_phase:
            self.current_phase = profile.active_phase
            for task_ids in self.progress_task_ids.values():
                for task_id in task_ids:
                    self.progress_bar.remove_task(task_id)
            self.progress_bar.refresh()
            self.progress_task_ids.clear()

        if self.current_phase is None:
            return Align.center(
                Text("Waiting for benchmark data...", style="dim yellow"),
                vertical="middle",
            )

        phase = profile.phase_infos.get(self.current_phase)
        if phase is None:
            return Align.center(
                Text("Waiting for benchmark data...", style="dim yellow"),
                vertical="middle",
            )

        # Create or update requests progress bar
        if (
            self.progress_task_ids.get(phase.type) is None
            and phase.total_expected_requests
        ):
            self.progress_task_ids[phase.type] = [
                self.progress_bar.add_task(
                    f"Executing {phase.type.capitalize()} requests...",
                    total=phase.total_expected_requests,
                )
            ]
            if phase.type == CreditPhase.PROFILING:
                self.progress_task_ids[phase.type].append(
                    self.progress_bar.add_task(
                        "Processing results...", total=phase.total_expected_requests
                    )
                )
        elif self.progress_task_ids.get(phase.type) is not None:
            task_ids = self.progress_task_ids.get(phase.type)
            if task_ids and len(task_ids) >= 1:
                self.progress_bar.update(
                    task_ids[0],
                    completed=phase.completed or 0,
                )
            if task_ids and len(task_ids) >= 2:
                self.progress_bar.update(
                    task_ids[1],
                    completed=phase.processed or 0,
                )

        # Pad each column by 1 space
        progress_table = Table.grid(padding=(0, 1, 0, 0))
        progress_table.add_column(style="bold cyan", justify="right")
        progress_table.add_column(style="bold white")

        if phase.is_complete:
            status = Text("Complete", style="bold green")
        else:
            status = Text("Processing", style="bold yellow")

        error_percent = 0.0
        if phase.processed and phase.processed > 0:
            error_percent = (phase.errors or 0) / phase.processed * 100

        # TODO: Color palette for error percentages? Or always red if above 0?
        error_color = (
            "green" if error_percent == 0 else "red" if error_percent > 10 else "yellow"
        )

        progress_table.add_row("Status:", status)
        progress_table.add_row(
            "Progress:",
            f"{phase.sent or 0:,} / {phase.total_expected_requests or 0:,} requests "
            f"({(phase.sent or 0) / (phase.total_expected_requests or 1) * 100:.1f}%)",
        )
        progress_table.add_row(
            "Errors:",
            f"[{error_color}]{phase.errors or 0:,} / {phase.processed or 0:,} ({error_percent:.1f}%)[/{error_color}]",
        )
        progress_table.add_row(
            "Request Rate:", f"{phase.records_per_second or 0:.1f} req/s"
        )
        progress_table.add_row(
            "Processing Rate:", f"{phase.records_per_second or 0:.1f} req/s"
        )
        progress_table.add_row("Elapsed:", format_duration(phase.elapsed_time))
        progress_table.add_row("Request ETA:", format_duration(phase.requests_eta))
        progress_table.add_row("Results ETA:", format_duration(phase.records_eta))

        return Group(self.progress_bar, progress_table)
