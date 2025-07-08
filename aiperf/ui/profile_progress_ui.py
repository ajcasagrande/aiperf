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

from aiperf.common.utils import format_duration
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.dashboard_element import DashboardElement


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
        """Create the progress panel with benchmark status."""

        if not self.progress_tracker.current_profile:
            return Align.center(
                Text("Waiting for benchmark data...", style="dim yellow"),
                vertical="middle",
            )

        profile = self.progress_tracker.current_profile

        # Create or update requests progress bar
        if self.progress_task_id is None and profile.total_expected_requests:
            self.progress_task_id = self.progress_bar.add_task(
                "Executing requests...", total=profile.total_expected_requests
            )
        elif self.progress_task_id is not None:
            self.progress_bar.update(
                self.progress_task_id, completed=profile.requests_completed or 0
            )

        # Create or update results progress bar
        if self.records_task_id is None and profile.total_expected_requests:
            self.records_task_id = self.records_progress_bar.add_task(
                "Processing results...", total=profile.total_expected_requests
            )
        elif self.records_task_id is not None:
            self.records_progress_bar.update(
                self.records_task_id, completed=profile.requests_processed or 0
            )

        # Pad each column by 1 space
        progress_table = Table.grid(padding=(0, 1, 0, 0))
        progress_table.add_column(style="bold cyan", justify="right")
        progress_table.add_column(style="bold white")

        if profile.is_complete:
            status = Text("Complete", style="bold green")
        elif profile.was_cancelled:
            status = Text("Cancelled", style="bold red")
        else:
            status = Text("Processing", style="bold yellow")

        error_percent = 0.0
        if profile.requests_processed and profile.requests_processed > 0:
            error_percent = (
                (profile.request_errors or 0) / profile.requests_processed * 100
            )

        # TODO: Color palette for error percentages? Or always red if above 0?
        error_color = (
            "green" if error_percent == 0 else "red" if error_percent > 10 else "yellow"
        )

        progress_table.add_row("Status:", status)
        progress_table.add_row(
            "Progress:",
            f"{profile.requests_completed or 0:,} / {profile.total_expected_requests or 0:,} requests "
            f"({(profile.requests_completed or 0) / (profile.total_expected_requests or 1) * 100:.1f}%)",
        )
        progress_table.add_row(
            "Errors:",
            f"[{error_color}]{profile.request_errors or 0:,} / {profile.requests_processed or 0:,} ({error_percent:.1f}%)[/{error_color}]",
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
