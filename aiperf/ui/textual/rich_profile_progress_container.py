# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import contextlib
import time
from typing import NamedTuple

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Label, Static

from aiperf.common.enums import CaseInsensitiveStrEnum, CreditPhase
from aiperf.common.utils import format_duration
from aiperf.progress.progress_tracker import ProfileRunProgress, ProgressTracker


class ProfileStatus(CaseInsensitiveStrEnum):
    COMPLETE = "complete"
    PROCESSING = "processing"
    IDLE = "idle"


class ProfileData(NamedTuple):
    profile_id: str | None
    status: ProfileStatus
    active_phase: CreditPhase | None
    requests_completed: int
    requests_total: int | None
    requests_per_second: float | None
    requests_eta: str | None
    processed_count: int
    errors_count: int
    error_percent: float
    records_per_second: float | None
    records_eta: str | None
    active_workers: int
    total_workers: int
    phase_duration: str | None


class PhaseData(NamedTuple):
    phase: CreditPhase
    status: str
    progress: str
    rate: str
    status_style: str


class ProfileProgressStatusWidget(Widget):
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

    .status-label { text-style: bold; color: $accent; text-align: right; padding: 0 1 0 0; }
    .status-value { text-style: bold; color: $text; padding: 0 0 0 1; }
    .status-complete { color: $success; text-style: bold; }
    .status-processing { color: $warning; text-style: bold; }
    .status-idle { color: $text-muted; }
    .error-none { color: $success; text-style: bold; }
    .error-medium { color: $warning; text-style: bold; }
    .error-high { color: $error; text-style: bold; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.border_title = "Profile Progress"
        self._dynamic_labels: list[tuple[str, str]] = []

    def compose(self) -> ComposeResult:
        with Container(id="status-grid"):
            yield Label("Status:", classes="status-label", id="status-label")
            yield Label("Idle", classes="status-value status-idle", id="status-value")
            yield Label("Active Phase:", classes="status-label", id="phase-label")
            yield Label("N/A", classes="status-value", id="phase-value")

    def update_progress(self, profile_data: ProfileData) -> None:
        with contextlib.suppress(Exception):
            self.border_title = f"Profile: {profile_data.profile_id or 'N/A'}"

            # Update status
            status_value = self.query_one("#status-value", Label)
            status_classes = {
                ProfileStatus.COMPLETE: "status-value status-complete",
                ProfileStatus.PROCESSING: "status-value status-processing",
                ProfileStatus.IDLE: "status-value status-idle",
            }
            status_value.update(profile_data.status.value.title())
            status_value.set_classes(status_classes[profile_data.status])

            # Update phase
            self.query_one("#phase-value", Label).update(
                profile_data.active_phase.value if profile_data.active_phase else "N/A"
            )

            # Clear and rebuild dynamic content
            self._clear_dynamic_labels()

            # Add request stats
            if profile_data.requests_total:
                progress_pct = (
                    profile_data.requests_completed / profile_data.requests_total
                ) * 100
                self._add_row(
                    "Requests",
                    f"{profile_data.requests_completed}/{profile_data.requests_total} ({progress_pct:.1f}%)",
                )
            elif profile_data.requests_completed > 0:
                self._add_row("Requests", str(profile_data.requests_completed))

            if profile_data.requests_per_second:
                self._add_row(
                    "Request Rate", f"{profile_data.requests_per_second:.1f} req/s"
                )

            if profile_data.requests_eta:
                self._add_row("Request ETA", profile_data.requests_eta)

            # Add processing stats
            if profile_data.processed_count > 0:
                self._add_row("Processed", str(profile_data.processed_count))

            if profile_data.errors_count > 0 or profile_data.processed_count > 0:
                error_class = f"status-value {'error-none' if profile_data.error_percent == 0 else 'error-high' if profile_data.error_percent > 10 else 'error-medium'}"
                self._add_row(
                    "Errors",
                    f"{profile_data.errors_count} ({profile_data.error_percent:.1f}%)",
                    error_class,
                )

            if profile_data.records_per_second:
                self._add_row(
                    "Processing Rate", f"{profile_data.records_per_second:.1f} rec/s"
                )

            if profile_data.records_eta:
                self._add_row("Processing ETA", profile_data.records_eta)

            # Add worker and timing stats
            if profile_data.total_workers > 0:
                self._add_row(
                    "Workers",
                    f"{profile_data.active_workers}/{profile_data.total_workers} active",
                )

            if profile_data.phase_duration:
                self._add_row("Phase Duration", profile_data.phase_duration)

    def _clear_dynamic_labels(self) -> None:
        for label_id, value_id in self._dynamic_labels:
            with contextlib.suppress(Exception):
                self.query_one(f"#{label_id}").remove()
                self.query_one(f"#{value_id}").remove()
        self._dynamic_labels.clear()

    def _add_row(
        self, label: str, value: str, value_class: str = "status-value"
    ) -> None:
        with contextlib.suppress(Exception):
            status_grid = self.query_one("#status-grid")
            label_id = f"dynamic-label-{len(self._dynamic_labels)}"
            value_id = f"dynamic-value-{len(self._dynamic_labels)}"

            status_grid.mount(Label(f"{label}:", classes="status-label", id=label_id))
            status_grid.mount(Label(value, classes=value_class, id=value_id))
            self._dynamic_labels.append((label_id, value_id))


class PhaseOverviewWidget(Widget):
    DEFAULT_CSS = """
    PhaseOverviewWidget {
        height: auto;
        border: solid $accent;
        border-title-color: $accent;
        min-height: 8;
    }
    DataTable { height: auto; }
    .phase-complete { color: $success; text-style: bold; }
    .phase-running { color: $warning; text-style: bold; }
    .phase-pending { color: $text-muted; }
    .phase-not-started { color: $text-disabled; }
    """

    def __init__(self) -> None:
        super().__init__()
        self.data_table: DataTable | None = None
        self.border_title = "Phase Overview"

    def compose(self) -> ComposeResult:
        self.data_table = DataTable()
        self.data_table.add_columns("Phase", "Status", "Progress", "Rate")
        yield self.data_table

    def update_phases(self, phases_data: list[PhaseData]) -> None:
        if not self.data_table:
            return

        self.data_table.clear()
        for phase_data in phases_data:
            self.data_table.add_row(
                phase_data.phase.value,
                Text(phase_data.status, style=phase_data.status_style),
                phase_data.progress,
                phase_data.rate,
            )


class RichProfileProgressContainer(Container):
    DEFAULT_CSS = """
    RichProfileProgressContainer {
        border: round $primary;
        border-title-color: $primary;
        border-title-background: $surface;
        height: 1fr;
        layout: vertical;
    }

    #status-section { height: auto; margin: 0 0 1 0; }
    #phase-section { height: auto; margin: 0; }
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
        with Vertical():
            with Container(id="status-section"):
                self.status_widget = ProfileProgressStatusWidget()
                yield self.status_widget

            if self.show_phase_overview:
                with Container(id="phase-section"):
                    self.phase_widget = PhaseOverviewWidget()
                    yield self.phase_widget

            if (
                not self.progress_tracker
                or not self.progress_tracker.current_profile_run
            ):
                yield Static("No profile run active", id="no-profile-message")

    def update_progress(self, progress_tracker: ProgressTracker | None = None) -> None:
        if progress_tracker:
            self.progress_tracker = progress_tracker

        if not self.progress_tracker or not self.progress_tracker.current_profile_run:
            self._show_no_profile_message()
            return

        self._remove_no_profile_message()
        profile_run = self.progress_tracker.current_profile_run

        # Process data
        profile_data = self._process_profile_data(profile_run)

        # Update widgets
        if self.status_widget:
            self.status_widget.update_progress(profile_data)

        if self.phase_widget and self.show_phase_overview:
            phases_data = self._process_phases_data(profile_run)
            self.phase_widget.update_phases(phases_data)

    def _show_no_profile_message(self) -> None:
        with contextlib.suppress(Exception):
            if not self.query("#no-profile-message"):
                self.mount(Static("No profile run active", id="no-profile-message"))

    def _remove_no_profile_message(self) -> None:
        with contextlib.suppress(Exception):
            self.query_one("#no-profile-message").remove()

    def _process_profile_data(self, profile_run: ProfileRunProgress) -> ProfileData:
        # Determine status
        if profile_run.is_complete:
            status = ProfileStatus.COMPLETE
        elif profile_run.is_started:
            status = ProfileStatus.PROCESSING
        else:
            status = ProfileStatus.IDLE

        # Get active phase
        active_phase = (
            self.progress_tracker.active_phase if self.progress_tracker else None
        )

        # Initialize defaults
        requests_completed = profile_run.requests_completed or 0
        processed_count = profile_run.requests_processed or 0
        errors_count = profile_run.request_errors or 0

        # Calculate error percentage
        error_percent = (
            (errors_count / processed_count * 100) if processed_count > 0 else 0.0
        )

        # Get phase-specific stats
        requests_total = None
        requests_per_second = None
        requests_eta = None
        records_per_second = None
        records_eta = None
        phase_duration = None

        if active_phase and active_phase in profile_run.phase_infos:
            phase_stats = profile_run.phase_infos[active_phase]
            requests_total = phase_stats.total_expected_requests

            # Get rates and ETAs from properties
            requests_per_second = profile_run.requests_per_second
            records_per_second = profile_run.processed_per_second

            if profile_run.requests_eta:
                requests_eta = format_duration(profile_run.requests_eta)
            if profile_run.processing_eta:
                records_eta = format_duration(profile_run.processing_eta)

            # Calculate phase duration
            if phase_stats.start_ns:
                elapsed_ns = time.time_ns() - phase_stats.start_ns
                elapsed_sec = elapsed_ns / 1_000_000_000
                phase_duration = format_duration(elapsed_sec)

        return ProfileData(
            profile_id=profile_run.profile_id,
            status=status,
            active_phase=active_phase,
            requests_completed=requests_completed,
            requests_total=requests_total,
            requests_per_second=requests_per_second,
            requests_eta=requests_eta,
            processed_count=processed_count,
            errors_count=errors_count,
            error_percent=error_percent,
            records_per_second=records_per_second,
            records_eta=records_eta,
            active_workers=0,  # Not available in ProfileRunProgress
            total_workers=0,  # Not available in ProfileRunProgress
            phase_duration=phase_duration,
        )

    def _process_phases_data(self, profile_run: ProfileRunProgress) -> list[PhaseData]:
        phases_data = []

        for phase in CreditPhase:
            if phase in profile_run.phase_infos:
                phase_stats = profile_run.phase_infos[phase]

                # Determine status and style
                if phase_stats.is_complete:
                    status, status_style = "Complete", "phase-complete"
                elif phase_stats.is_started:
                    status, status_style = "Running", "phase-running"
                else:
                    status, status_style = "Pending", "phase-pending"

                # Calculate progress
                if phase_stats.total_expected_requests:
                    progress_percent = (
                        phase_stats.completed / phase_stats.total_expected_requests
                    ) * 100
                    progress = f"{phase_stats.completed}/{phase_stats.total_expected_requests} ({progress_percent:.1f}%)"
                else:
                    progress = str(phase_stats.completed)

                # Get rate info
                rate = "--"
                if (
                    hasattr(phase_stats, "requests_per_second")
                    and phase_stats.requests_per_second
                ):
                    rate = f"{phase_stats.requests_per_second:.1f} req/s"

                phases_data.append(
                    PhaseData(phase, status, progress, rate, status_style)
                )
            else:
                phases_data.append(
                    PhaseData(phase, "Not Started", "--", "--", "phase-not-started")
                )

        return phases_data

    def set_progress_tracker(self, progress_tracker: ProgressTracker) -> None:
        self.progress_tracker = progress_tracker
        self.update_progress()

    def toggle_phase_overview(self) -> None:
        self.show_phase_overview = not self.show_phase_overview

        if self.show_phase_overview and not self.phase_widget:
            with contextlib.suppress(Exception):
                phase_section = self.query_one("#phase-section")
                self.phase_widget = PhaseOverviewWidget()
                phase_section.mount(self.phase_widget)
                self.update_progress()
        elif not self.show_phase_overview and self.phase_widget:
            with contextlib.suppress(Exception):
                self.phase_widget.remove()
                self.phase_widget = None

    def get_current_status(self) -> ProfileStatus:
        if not self.progress_tracker or not self.progress_tracker.current_profile_run:
            return ProfileStatus.IDLE

        profile_run = self.progress_tracker.current_profile_run
        if profile_run.is_complete:
            return ProfileStatus.COMPLETE
        elif profile_run.is_started:
            return ProfileStatus.PROCESSING
        else:
            return ProfileStatus.IDLE
