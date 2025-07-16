# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time
from enum import Enum

from pydantic import Field
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Label, Static

from aiperf.common.enums import CreditPhase
from aiperf.common.pydantic_utils import AIPerfBaseModel
from aiperf.common.utils import format_duration
from aiperf.progress.progress_tracker import ProfileRunProgress, ProgressTracker


class ProfileStatus(str, Enum):
    """Enum for profile status classifications."""

    COMPLETE = "complete"
    PROCESSING = "processing"
    IDLE = "idle"


class ProfileProgressData(AIPerfBaseModel):
    """Pydantic model for profile progress information."""

    profile_id: str | None = Field(default=None, description="Profile identifier")
    status: ProfileStatus = Field(..., description="Current profile status")
    active_phase: CreditPhase | None = Field(
        default=None, description="Currently active phase"
    )

    # Request statistics
    requests_completed: int = Field(
        default=0, description="Number of completed requests"
    )
    requests_total: int | None = Field(
        default=None, description="Total number of requests"
    )
    requests_progress_percent: float | None = Field(
        default=None, description="Request completion percentage"
    )
    requests_per_second: float | None = Field(
        default=None, description="Request rate per second"
    )
    requests_eta: str | None = Field(
        default=None, description="Estimated time to completion for requests"
    )

    # Processing statistics
    processed_count: int = Field(default=0, description="Number of processed records")
    errors_count: int = Field(default=0, description="Number of processing errors")
    error_percent: float = Field(default=0.0, description="Error rate percentage")
    records_per_second: float | None = Field(
        default=None, description="Processing rate per second"
    )
    records_eta: str | None = Field(
        default=None, description="Estimated time to completion for processing"
    )

    # Worker statistics
    active_workers: int = Field(default=0, description="Number of active workers")
    total_workers: int = Field(default=0, description="Total number of workers")

    # Phase timing
    phase_duration: str | None = Field(
        default=None, description="Duration of current phase"
    )

    @property
    def error_color_class(self) -> str:
        """Get the CSS class for error color coding."""
        if self.error_percent == 0:
            return "error-none"
        elif self.error_percent > 10:
            return "error-high"
        else:
            return "error-medium"


class PhaseOverviewData(AIPerfBaseModel):
    """Pydantic model for phase overview information."""

    phase: CreditPhase = Field(..., description="Phase identifier")
    status: str = Field(..., description="Phase status")
    progress: str = Field(..., description="Progress display text")
    rate: str = Field(..., description="Rate display text")
    status_style: str = Field(..., description="CSS style for status")


class ProfileProgressStatusWidget(Widget):
    """Widget for displaying profile progress status information."""

    DEFAULT_CSS = """
    ProfileProgressStatusWidget {
        height: auto;
        border: solid $primary;
        border-title-color: $primary;
        layout: vertical;
        padding: 1;
    }

    #status-grid {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 2fr;
        grid-rows: auto;
        height: auto;
    }

    .status-label {
        text-style: bold;
        color: $accent;
        text-align: right;
        padding: 0 1 0 0;
    }

    .status-value {
        text-style: bold;
        color: $text;
        padding: 0 0 0 1;
    }

    .status-complete {
        color: $success;
        text-style: bold;
    }

    .status-processing {
        color: $warning;
        text-style: bold;
    }

    .status-idle {
        color: $text-muted;
    }

    .error-none {
        color: $success;
        text-style: bold;
    }

    .error-medium {
        color: $warning;
        text-style: bold;
    }

    .error-high {
        color: $error;
        text-style: bold;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.border_title = "Profile Progress"
        self._status_labels: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        """Compose the status widget."""
        with Container(id="status-grid"):
            yield Label("Status:", classes="status-label", id="status-label")
            yield Label("Idle", classes="status-value status-idle", id="status-value")

            yield Label("Active Phase:", classes="status-label", id="phase-label")
            yield Label("N/A", classes="status-value", id="phase-value")

    def update_progress(self, progress_data: ProfileProgressData) -> None:
        """Update the widget with new progress data."""
        try:
            # Update profile ID in border title
            profile_title = f"Profile: {progress_data.profile_id or 'N/A'}"
            self.border_title = profile_title

            # Update status
            status_value = self.query_one("#status-value", Label)
            if progress_data.status == ProfileStatus.COMPLETE:
                status_value.update("Complete")
                status_value.set_classes("status-value status-complete")
            elif progress_data.status == ProfileStatus.PROCESSING:
                status_value.update("Processing")
                status_value.set_classes("status-value status-processing")
            else:
                status_value.update("Idle")
                status_value.set_classes("status-value status-idle")

            # Update active phase
            phase_value = self.query_one("#phase-value", Label)
            phase_value.update(
                progress_data.active_phase.value
                if progress_data.active_phase
                else "N/A"
            )

            # Clear existing dynamic labels
            self._clear_dynamic_labels()

            # Add request statistics
            if progress_data.requests_total:
                self._add_status_row(
                    "Requests",
                    f"{progress_data.requests_completed}/{progress_data.requests_total} "
                    f"({progress_data.requests_progress_percent:.1f}%)",
                )
            elif progress_data.requests_completed > 0:
                self._add_status_row("Requests", str(progress_data.requests_completed))

            # Add request rate
            if progress_data.requests_per_second:
                self._add_status_row(
                    "Request Rate", f"{progress_data.requests_per_second:.1f} req/s"
                )

            # Add request ETA
            if progress_data.requests_eta:
                self._add_status_row("Request ETA", progress_data.requests_eta)

            # Add processing statistics
            if progress_data.processed_count > 0:
                self._add_status_row("Processed", str(progress_data.processed_count))

            if progress_data.errors_count > 0 or progress_data.processed_count > 0:
                error_class = f"status-value {progress_data.error_color_class}"
                self._add_status_row(
                    "Errors",
                    f"{progress_data.errors_count} ({progress_data.error_percent:.1f}%)",
                    error_class,
                )

            # Add processing rate
            if progress_data.records_per_second:
                self._add_status_row(
                    "Processing Rate", f"{progress_data.records_per_second:.1f} rec/s"
                )

            # Add processing ETA
            if progress_data.records_eta:
                self._add_status_row("Processing ETA", progress_data.records_eta)

            # Add worker statistics
            if progress_data.total_workers > 0:
                self._add_status_row(
                    "Workers",
                    f"{progress_data.active_workers}/{progress_data.total_workers} active",
                )

            # Add phase duration
            if progress_data.phase_duration:
                self._add_status_row("Phase Duration", progress_data.phase_duration)

        except Exception:
            pass  # Silently handle cases where widgets aren't mounted yet

    def _clear_dynamic_labels(self) -> None:
        """Clear dynamically added status labels."""
        for label_id, value_id in self._status_labels:
            try:
                self.query_one(f"#{label_id}").remove()
                self.query_one(f"#{value_id}").remove()
            except Exception:
                pass
        self._status_labels.clear()

    def _add_status_row(
        self, label: str, value: str, value_class: str = "status-value"
    ) -> None:
        """Add a status row dynamically."""
        try:
            status_grid = self.query_one("#status-grid")

            # Generate unique IDs
            label_id = f"dynamic-label-{len(self._status_labels)}"
            value_id = f"dynamic-value-{len(self._status_labels)}"

            # Create and mount labels
            label_widget = Label(f"{label}:", classes="status-label", id=label_id)
            value_widget = Label(value, classes=value_class, id=value_id)

            status_grid.mount(label_widget)
            status_grid.mount(value_widget)

            # Track for cleanup
            self._status_labels.append((label_id, value_id))

        except Exception:
            pass  # Silently handle mounting issues


class PhaseOverviewWidget(Widget):
    """Widget for displaying phase overview table."""

    DEFAULT_CSS = """
    PhaseOverviewWidget {
        height: auto;
        border: solid $accent;
        border-title-color: $accent;
        min-height: 8;
    }

    DataTable {
        height: auto;
    }

    .phase-complete {
        color: $success;
        text-style: bold;
    }

    .phase-running {
        color: $warning;
        text-style: bold;
    }

    .phase-pending {
        color: $text-muted;
    }

    .phase-not-started {
        color: $text-disabled;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.data_table: DataTable | None = None
        self.border_title = "Phase Overview"

    def compose(self) -> ComposeResult:
        """Compose the phase overview widget."""
        self.data_table = DataTable()
        self.data_table.add_columns("Phase", "Status", "Progress", "Rate")
        yield self.data_table

    def update_phases(self, phases_data: list[PhaseOverviewData]) -> None:
        """Update the phase overview with new data."""
        if not self.data_table:
            return

        # Clear existing data
        self.data_table.clear()

        # Add phase rows
        for phase_data in phases_data:
            self.data_table.add_row(
                phase_data.phase.value,
                Text(phase_data.status, style=phase_data.status_style),
                phase_data.progress,
                phase_data.rate,
            )


class RichProfileProgressContainer(Container):
    """Textual container that encapsulates the Rich profile progress dashboard functionality.

    This container replicates the functionality of the Rich ProfileProgressElement,
    providing the same status display, phase information, and progress tracking.
    """

    DEFAULT_CSS = """
    RichProfileProgressContainer {
        border: round $primary;
        border-title-color: $primary;
        border-title-background: $surface;
        height: 1fr;
        layout: vertical;
    }

    #status-section {
        height: auto;
        margin: 0 0 1 0;
    }

    #phase-section {
        height: auto;
        margin: 0;
    }

    #no-profile-message {
        height: 1fr;
        content-align: center middle;
        color: $warning;
        text-style: italic;
    }
    """

    def __init__(
        self,
        progress_tracker: ProgressTracker | None = None,
        show_phase_overview: bool = True,
    ) -> None:
        super().__init__()
        self.progress_tracker = progress_tracker
        self.show_phase_overview = show_phase_overview

        self.status_widget: ProfileProgressStatusWidget | None = None
        self.phase_widget: PhaseOverviewWidget | None = None

        self.border_title = "Profile Progress Monitor"

    def compose(self) -> ComposeResult:
        """Compose the container layout."""
        with Vertical():
            with Container(id="status-section"):
                self.status_widget = ProfileProgressStatusWidget()
                yield self.status_widget

            if self.show_phase_overview:
                with Container(id="phase-section"):
                    self.phase_widget = PhaseOverviewWidget()
                    yield self.phase_widget

            # Show message if no profile is active
            if (
                not self.progress_tracker
                or not self.progress_tracker.current_profile_run
            ):
                yield Static("No profile run active", id="no-profile-message")

    def update_progress(self, progress_tracker: ProgressTracker | None = None) -> None:
        """Update the container with new progress data."""
        if progress_tracker:
            self.progress_tracker = progress_tracker

        if not self.progress_tracker:
            self._show_no_profile_message()
            return

        profile_run = self.progress_tracker.current_profile_run
        if not profile_run:
            self._show_no_profile_message()
            return

        # Remove no profile message if it exists
        self._remove_no_profile_message()

        # Process profile data
        progress_data = self._process_profile_data(profile_run)

        # Update status widget
        if self.status_widget:
            self.status_widget.update_progress(progress_data)

        # Update phase overview widget
        if self.phase_widget and self.show_phase_overview:
            phases_data = self._process_phases_data(profile_run)
            self.phase_widget.update_phases(phases_data)

    def _show_no_profile_message(self) -> None:
        """Show the no profile message."""
        try:
            # Check if message already exists
            if not self.query("#no-profile-message"):
                self.mount(Static("No profile run active", id="no-profile-message"))
        except Exception:
            pass  # Silently handle mounting issues

    def _remove_no_profile_message(self) -> None:
        """Remove the no profile message."""
        try:
            no_profile_msg = self.query_one("#no-profile-message")
            no_profile_msg.remove()
        except Exception:
            pass  # Message might not exist

    def _process_profile_data(
        self, profile_run: ProfileRunProgress
    ) -> ProfileProgressData:
        """Process profile run data into a structured format."""
        # Determine status
        if profile_run.is_complete:
            status = ProfileStatus.COMPLETE
        elif profile_run.is_started:
            status = ProfileStatus.PROCESSING
        else:
            status = ProfileStatus.IDLE

        # Get active phase
        active_phase = (
            self.progress_tracker.active_credit_phase if self.progress_tracker else None
        )

        # Initialize progress data
        progress_data = ProfileProgressData(
            profile_id=profile_run.profile_id,
            status=status,
            active_phase=active_phase,
        )

        # Process phase-specific stats
        if active_phase and active_phase in profile_run.phases:
            phase_stats = profile_run.phases[active_phase]

            # Request statistics
            progress_data.requests_completed = phase_stats.completed
            progress_data.requests_total = phase_stats.total_expected_requests

            if phase_stats.total_expected_requests:
                progress_data.requests_progress_percent = (
                    phase_stats.completed / phase_stats.total_expected_requests
                ) * 100

            # Request rate and ETA
            if active_phase in profile_run.computed_stats:
                computed = profile_run.computed_stats[active_phase]
                progress_data.requests_per_second = computed.requests_per_second
                progress_data.requests_eta = (
                    format_duration(computed.requests_eta)
                    if computed.requests_eta
                    else None
                )

        # Processing statistics
        if active_phase and active_phase in profile_run.processing_stats:
            processing_stats = profile_run.processing_stats[active_phase]

            progress_data.processed_count = processing_stats.processed
            progress_data.errors_count = processing_stats.errors

            if processing_stats.processed > 0:
                progress_data.error_percent = (
                    processing_stats.errors / processing_stats.processed
                ) * 100

            # Processing rate and ETA
            if active_phase in profile_run.computed_stats:
                computed = profile_run.computed_stats[active_phase]
                progress_data.records_per_second = computed.records_per_second
                progress_data.records_eta = (
                    format_duration(computed.records_eta)
                    if computed.records_eta
                    else None
                )

        # Worker statistics
        if profile_run.worker_task_stats:
            progress_data.total_workers = len(profile_run.worker_task_stats)

            if active_phase:
                progress_data.active_workers = sum(
                    1
                    for worker_stats in profile_run.worker_task_stats.values()
                    if active_phase in worker_stats
                    and worker_stats[active_phase].in_progress > 0
                )

        # Phase timing
        if active_phase and active_phase in profile_run.phases:
            phase_stats = profile_run.phases[active_phase]
            if phase_stats.start_ns:
                elapsed_ns = time.time_ns() - phase_stats.start_ns
                elapsed_sec = elapsed_ns / 1_000_000_000
                progress_data.phase_duration = format_duration(elapsed_sec)

        return progress_data

    def _process_phases_data(
        self, profile_run: ProfileRunProgress
    ) -> list[PhaseOverviewData]:
        """Process phases data for the overview table."""
        phases_data = []

        for phase in CreditPhase:
            if phase in profile_run.phases:
                phase_stats = profile_run.phases[phase]

                # Status
                if phase_stats.is_complete:
                    status = "Complete"
                    status_style = "phase-complete"
                elif phase_stats.is_started:
                    status = "Running"
                    status_style = "phase-running"
                else:
                    status = "Pending"
                    status_style = "phase-pending"

                # Progress
                if phase_stats.total_expected_requests:
                    progress_percent = (
                        phase_stats.completed / phase_stats.total_expected_requests
                    ) * 100
                    progress = f"{phase_stats.completed}/{phase_stats.total_expected_requests} ({progress_percent:.1f}%)"
                else:
                    progress = str(phase_stats.completed)

                # Rate
                rate = "--"
                if phase in profile_run.computed_stats:
                    computed = profile_run.computed_stats[phase]
                    if computed.requests_per_second:
                        rate = f"{computed.requests_per_second:.1f} req/s"

                phases_data.append(
                    PhaseOverviewData(
                        phase=phase,
                        status=status,
                        progress=progress,
                        rate=rate,
                        status_style=status_style,
                    )
                )
            else:
                phases_data.append(
                    PhaseOverviewData(
                        phase=phase,
                        status="Not Started",
                        progress="--",
                        rate="--",
                        status_style="phase-not-started",
                    )
                )

        return phases_data

    def on_mount(self) -> None:
        """Handle widget mounting."""
        self.update_progress()

    def set_progress_tracker(self, progress_tracker: ProgressTracker) -> None:
        """Set the progress tracker and update display."""
        self.progress_tracker = progress_tracker
        self.update_progress()

    def toggle_phase_overview(self) -> None:
        """Toggle the phase overview display."""
        self.show_phase_overview = not self.show_phase_overview

        if self.show_phase_overview and not self.phase_widget:
            # Add phase overview widget
            try:
                phase_section = self.query_one("#phase-section")
                self.phase_widget = PhaseOverviewWidget()
                phase_section.mount(self.phase_widget)
                self.update_progress()
            except Exception:
                pass
        elif not self.show_phase_overview and self.phase_widget:
            # Remove phase overview widget
            try:
                self.phase_widget.remove()
                self.phase_widget = None
            except Exception:
                pass

    def get_current_status(self) -> ProfileStatus:
        """Get the current profile status."""
        if not self.progress_tracker or not self.progress_tracker.current_profile_run:
            return ProfileStatus.IDLE

        profile_run = self.progress_tracker.current_profile_run
        if profile_run.is_complete:
            return ProfileStatus.COMPLETE
        elif profile_run.is_started:
            return ProfileStatus.PROCESSING
        else:
            return ProfileStatus.IDLE
