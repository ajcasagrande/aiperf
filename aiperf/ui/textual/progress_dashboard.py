# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import contextlib

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Label, ProgressBar

from aiperf.common.enums.timing_enums import CreditPhase
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.utils import format_duration
from aiperf.progress.progress_tracker import ProgressTracker


class ProgressDashboard(Container, AIPerfLoggerMixin):
    """Main progress dashboard widget with clean, simplified styling."""

    DEFAULT_CSS = """
    ProgressDashboard {
        border: round $primary;
        border-title-color: $primary;
        border-title-background: $surface;
        height: 100%;
        layout: vertical;
        padding: 1;
    }

    #progress-section {
        height: auto;
        margin: 0 0 1 0;
    }

    #metrics-section {
        height: auto;
        layout: vertical;
    }

    .metric-line {
        height: 1;
        layout: horizontal;
        margin: 0 0 0 0;
        padding: 0;
    }

    .metric-label {
        text-style: bold;
        color: $accent;
        width: 20;
        text-align: right;
        padding: 0 1 0 0;
    }

    .metric-value {
        text-style: bold;
        color: $text;
        padding: 0 0 0 1;
    }

    .status-complete { color: $success; }
    .status-processing { color: $warning; }
    .status-cancelled { color: $error; }
    .status-idle { color: $text-muted; }
    .error-none { color: $success; }
    .error-medium { color: $warning; }
    .error-high { color: $error; }

    #progress-label, #records-label {
        text-align: center;
        text-style: bold;
        color: $text;
        margin: 0 0 0 0;
    }
    """

    border_title = "AIPerf Performance Dashboard"

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
        self.progress_tracker = progress_tracker

    def compose(self) -> ComposeResult:
        with Vertical():
            # Progress section
            with Container(id="progress-section"):
                yield ProgressBar(
                    total=100, show_eta=True, show_percentage=True, id="main-progress"
                )
                yield Label("Waiting for performance data...", id="progress-label")
                yield ProgressBar(
                    total=100,
                    show_eta=True,
                    show_percentage=True,
                    id="records-progress",
                )
                yield Label("Records processing: --", id="records-label")

            # Metrics list
            with Container(id="metrics-section"):
                with Container(classes="metric-line"):
                    yield Label("Status:", classes="metric-label")
                    yield Label(
                        "Idle", classes="metric-value status-idle", id="status-value"
                    )

                with Container(classes="metric-line"):
                    yield Label("Progress:", classes="metric-label")
                    yield Label("--", classes="metric-value", id="progress-value")

                with Container(classes="metric-line"):
                    yield Label("Request Rate:", classes="metric-label")
                    yield Label("--", classes="metric-value", id="request-rate-value")

                with Container(classes="metric-line"):
                    yield Label("Processing Rate:", classes="metric-label")
                    yield Label(
                        "--", classes="metric-value", id="processing-rate-value"
                    )

                with Container(classes="metric-line"):
                    yield Label("Errors:", classes="metric-label")
                    yield Label("--", classes="metric-value", id="errors-value")

                with Container(classes="metric-line"):
                    yield Label("Elapsed:", classes="metric-label")
                    yield Label("--", classes="metric-value", id="elapsed-value")

                with Container(classes="metric-line"):
                    yield Label("ETA:", classes="metric-label")
                    yield Label("--", classes="metric-value", id="eta-value")

                with Container(classes="metric-line"):
                    yield Label("Completion:", classes="metric-label")
                    yield Label("--", classes="metric-value", id="completion-value")

    def on_mount(self) -> None:
        self.update_display()

    def update_display(self) -> None:
        if not self.is_mounted:
            return

        profile_run = self.progress_tracker.current_profile_run
        if not profile_run:
            self._show_idle_state()
            return

        try:
            # Get phase info
            phase_info = profile_run.phase_infos.get(CreditPhase.PROFILING)
            if not phase_info:
                self._show_idle_state()
                return

            self._update_progress(phase_info)
            self._update_status(profile_run)
            self._update_metrics(profile_run, phase_info)

        except Exception as e:
            self.debug(f"Display update error: {e}")

        self.refresh()

    def _show_idle_state(self) -> None:
        """Show idle state for all widgets."""
        updates = [
            ("main-progress", lambda w: w.update(progress=0)),
            ("records-progress", lambda w: w.update(progress=0)),
            ("progress-label", lambda w: w.update("Waiting for performance data...")),
            ("records-label", lambda w: w.update("Records processing: --")),
            (
                "status-value",
                lambda w: w.update("Idle") or w.set_classes("metric-value status-idle"),
            ),
            ("progress-value", lambda w: w.update("--")),
            ("request-rate-value", lambda w: w.update("--")),
            ("processing-rate-value", lambda w: w.update("--")),
            ("errors-value", lambda w: w.update("--")),
            ("elapsed-value", lambda w: w.update("--")),
            ("eta-value", lambda w: w.update("--")),
            ("completion-value", lambda w: w.update("--")),
        ]

        for widget_id, update_func in updates:
            with contextlib.suppress(Exception):
                widget = self.query_one(f"#{widget_id}")
                update_func(widget)

    def _update_progress(self, phase_info) -> None:
        """Update progress bars and labels."""
        with contextlib.suppress(Exception):
            if (
                phase_info.total_expected_requests
                and phase_info.total_expected_requests > 0
            ):
                progress_value = min(
                    100,
                    (phase_info.completed / phase_info.total_expected_requests) * 100,
                )
                self.query_one("#main-progress", ProgressBar).update(
                    progress=progress_value
                )

                progress_text = f"Requests: {phase_info.completed:,} / {phase_info.total_expected_requests:,}"
                self.query_one("#progress-label", Label).update(progress_text)

            if (
                phase_info.total_expected_requests
                and phase_info.total_expected_requests > 0
            ):
                processed_count = phase_info.processed or 0
                records_progress_value = min(
                    100, (processed_count / phase_info.total_expected_requests) * 100
                )
                self.query_one("#records-progress", ProgressBar).update(
                    progress=records_progress_value
                )

                records_text = f"Records processed: {processed_count:,} / {phase_info.total_expected_requests:,}"
                self.query_one("#records-label", Label).update(records_text)

    def _update_status(self, profile_run) -> None:
        """Update status indicator."""
        with contextlib.suppress(Exception):
            status_widget = self.query_one("#status-value", Label)

            if profile_run.is_complete:
                status_widget.update("Complete")
                status_widget.set_classes("metric-value status-complete")
            elif profile_run.was_cancelled:
                status_widget.update("Cancelled")
                status_widget.set_classes("metric-value status-cancelled")
            elif profile_run.is_started:
                status_widget.update("Processing")
                status_widget.set_classes("metric-value status-processing")
            else:
                status_widget.update("Idle")
                status_widget.set_classes("metric-value status-idle")

    def _update_metrics(self, profile_run, phase_info) -> None:
        """Update all metrics."""
        with contextlib.suppress(Exception):
            if phase_info.total_expected_requests:
                progress_text = (
                    f"{phase_info.completed:,} / {phase_info.total_expected_requests:,}"
                )
            else:
                progress_text = f"{phase_info.completed:,}"
            self.query_one("#progress-value", Label).update(progress_text)

            rate_text = (
                f"{profile_run.requests_per_second:.1f} req/s"
                if profile_run.requests_per_second
                else "--"
            )
            self.query_one("#request-rate-value", Label).update(rate_text)

            proc_rate_text = (
                f"{profile_run.processed_per_second:.1f} rec/s"
                if profile_run.processed_per_second
                else "--"
            )
            self.query_one("#processing-rate-value", Label).update(proc_rate_text)

            error_count = phase_info.errors or 0
            processed_count = phase_info.processed or 0
            if processed_count > 0:
                error_percent = (error_count / processed_count) * 100
                error_text = f"{error_count} ({error_percent:.1f}%)"
                error_class = "metric-value " + (
                    "error-none"
                    if error_percent == 0
                    else "error-high"
                    if error_percent > 10
                    else "error-medium"
                )
            else:
                error_text = f"{error_count} (0.0%)"
                error_class = "metric-value error-none"

            error_widget = self.query_one("#errors-value", Label)
            error_widget.update(error_text)
            error_widget.set_classes(error_class)

            elapsed_text = (
                format_duration(profile_run.elapsed_time)
                if profile_run.elapsed_time
                else "--"
            )
            self.query_one("#elapsed-value", Label).update(elapsed_text)

            eta_text = format_duration(profile_run.eta) if profile_run.eta else "--"
            self.query_one("#eta-value", Label).update(eta_text)

            if (
                phase_info.total_expected_requests
                and phase_info.total_expected_requests > 0
            ):
                completion_percent = (
                    phase_info.completed / phase_info.total_expected_requests
                ) * 100
                completion_text = f"{completion_percent:.1f}%"
            else:
                completion_text = "--"
            self.query_one("#completion-value", Label).update(completion_text)
