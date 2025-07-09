# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import TYPE_CHECKING

from rich.console import RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from aiperf.common.enums import CreditPhase
from aiperf.common.utils import format_duration
from aiperf.ui.dashboard_element import DashboardElement

if TYPE_CHECKING:
    from aiperf.progress.progress_tracker import ProgressTracker


class ProfileProgressElement(DashboardElement):
    """Profile progress dashboard element for the dashboard."""

    key = "profile_progress"
    title = Text("Profile Progress", style="bold")
    border_style = "green"
    height = 20
    title_align = "left"

    def __init__(self, progress_tracker: "ProgressTracker") -> None:
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.progress_tracker = progress_tracker

    def get_content(self) -> RenderableType:
        """Get the content for the profile progress element."""
        profile_run = self.progress_tracker.current_profile_run
        if profile_run is None:
            return Text("No profile run active", style="dim")

        # Create a panel with multiple sections
        return Panel.fit(
            self._create_status_table(profile_run),
            title=f"Profile: {profile_run.profile_id or 'N/A'}",
            border_style="green",
        )

    def _create_status_table(self, profile_run) -> Table:
        """Create a table showing profile status."""
        active_phase = self.progress_tracker.active_credit_phase

        # Pad each column by 1 space
        progress_table = Table.grid(padding=(0, 1, 0, 0))
        progress_table.add_column(style="bold cyan", justify="right")
        progress_table.add_column(style="bold white")

        if profile_run.is_complete:
            status = Text("Complete", style="bold green")
        else:
            status = Text("Processing", style="bold yellow")

        progress_table.add_row("Status:", status)
        progress_table.add_row(
            "Active Phase:", Text(active_phase or "N/A", style="bold white")
        )

        # Show phase-specific stats
        if active_phase in profile_run.phases:
            phase_stats = profile_run.phases[active_phase]

            # Request stats
            if phase_stats.total:
                progress_percent = (phase_stats.completed / phase_stats.total) * 100
                progress_table.add_row(
                    "Requests:",
                    Text(
                        f"{phase_stats.completed}/{phase_stats.total} ({progress_percent:.1f}%)"
                    ),
                )
            else:
                progress_table.add_row("Requests:", Text(f"{phase_stats.completed}"))

            # Request rate
            if active_phase in profile_run.computed_stats:
                computed = profile_run.computed_stats[active_phase]
                if computed.requests_per_second:
                    progress_table.add_row(
                        "Request Rate:",
                        Text(f"{computed.requests_per_second:.1f} req/s"),
                    )
                if computed.requests_eta:
                    progress_table.add_row(
                        "Request ETA:", Text(format_duration(computed.requests_eta))
                    )

        # Processing stats
        if active_phase in profile_run.processing_stats:
            processing_stats = profile_run.processing_stats[active_phase]

            error_percent = 0.0
            if processing_stats.processed > 0:
                error_percent = (
                    processing_stats.errors / processing_stats.processed
                ) * 100

            # Color palette for error percentages
            error_color = (
                "green"
                if error_percent == 0
                else "red"
                if error_percent > 10
                else "yellow"
            )

            progress_table.add_row("Processed:", Text(f"{processing_stats.processed}"))
            progress_table.add_row(
                "Errors:",
                Text(
                    f"{processing_stats.errors} ({error_percent:.1f}%)",
                    style=error_color,
                ),
            )

            # Processing rate
            if active_phase in profile_run.computed_stats:
                computed = profile_run.computed_stats[active_phase]
                if computed.records_per_second:
                    progress_table.add_row(
                        "Processing Rate:",
                        Text(f"{computed.records_per_second:.1f} rec/s"),
                    )
                if computed.records_eta:
                    progress_table.add_row(
                        "Processing ETA:", Text(format_duration(computed.records_eta))
                    )

        # Worker stats summary
        if profile_run.worker_task_stats:
            worker_count = len(profile_run.worker_task_stats)
            active_workers = sum(
                1
                for worker_stats in profile_run.worker_task_stats.values()
                if active_phase in worker_stats
                and worker_stats[active_phase].in_progress > 0
            )

            progress_table.add_row(
                "Workers:", Text(f"{active_workers}/{worker_count} active")
            )

        # Phase timing
        if active_phase in profile_run.phases:
            phase_stats = profile_run.phases[active_phase]
            if phase_stats.start_ns:
                import time

                elapsed_ns = time.time_ns() - phase_stats.start_ns
                elapsed_sec = elapsed_ns / 1_000_000_000
                progress_table.add_row(
                    "Phase Duration:", Text(format_duration(elapsed_sec))
                )

        return progress_table

    def _create_phase_overview_table(self, profile_run) -> Table:
        """Create a table showing all phases."""
        phases_table = Table()
        phases_table.add_column("Phase", style="bold")
        phases_table.add_column("Status", style="bold")
        phases_table.add_column("Progress", style="bold")
        phases_table.add_column("Rate", style="bold")

        for phase in CreditPhase:
            if phase in profile_run.phases:
                phase_stats = profile_run.phases[phase]

                # Status
                if phase_stats.is_complete:
                    status = Text("Complete", style="green")
                elif phase_stats.is_started:
                    status = Text("Running", style="yellow")
                else:
                    status = Text("Pending", style="dim")

                # Progress
                if phase_stats.total:
                    progress_percent = (phase_stats.completed / phase_stats.total) * 100
                    progress_text = f"{phase_stats.completed}/{phase_stats.total} ({progress_percent:.1f}%)"
                else:
                    progress_text = f"{phase_stats.completed}"

                # Rate
                rate_text = "--"
                if phase in profile_run.computed_stats:
                    computed = profile_run.computed_stats[phase]
                    if computed.requests_per_second:
                        rate_text = f"{computed.requests_per_second:.1f} req/s"

                phases_table.add_row(
                    phase.value,
                    status,
                    progress_text,
                    rate_text,
                )
            else:
                phases_table.add_row(
                    phase.value,
                    Text("Not Started", style="dim"),
                    "--",
                    "--",
                )

        return phases_table
