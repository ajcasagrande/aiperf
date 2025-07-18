# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import contextlib

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Label, ProgressBar

from aiperf.common.enums import CreditPhase
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.utils import format_duration
from aiperf.progress.progress_tracker import ProgressTracker


class ProgressDashboard(Container, AIPerfLoggerMixin):
    """Profile progress dashboard with Rich-inspired styling."""

    DEFAULT_CSS = """
    ProgressDashboard {
        border: round cyan;
        border-title-color: cyan;
        border-title-background: $surface;
        border-title-style: bold;
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
        border: solid $primary-lighten-1;
        padding: 1;
        margin: 1 0 0 0;
    }

    .metric-line {
        height: 1;
        layout: horizontal;
        margin: 0 0 0 0;
        padding: 0 1 0 0;
    }

    .metric-label {
        text-style: bold;
        color: cyan;
        width: 18;
        text-align: right;
        padding: 0 1 0 0;
    }

    .metric-value {
        text-style: bold;
        color: white;
        padding: 0 0 0 0;
    }

    .status-complete { color: green; }
    .status-processing { color: yellow; }
    .status-cancelled { color: red; }
    .status-idle { color: $text-muted; }
    .error-none { color: green; }
    .error-medium { color: yellow; }
    .error-high { color: red; }

    #progress-label, #records-label {
        text-align: center;
        text-style: bold;
        color: $text;
        margin: 0 0 0 0;
    }

    #records-label {
        margin: 0 0 1 0;
    }

    #status-header {
        text-align: center;
        text-style: bold;
        color: cyan;
        margin: 0 0 1 0;
    }
    """

    border_title = "Profile Progress"

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
        self.progress_tracker = progress_tracker

    def compose(self) -> ComposeResult:
        with Vertical():
            # Progress bars section
            with Container(id="progress-section"):
                yield ProgressBar(
                    total=100, show_eta=True, show_percentage=True, id="main-progress"
                )
                yield Label("Executing requests...", id="progress-label")
                yield ProgressBar(
                    total=100,
                    show_eta=True,
                    show_percentage=True,
                    id="records-progress",
                )
                yield Label("Processing results...", id="records-label")

            # Status and metrics section
            with Container(id="metrics-section"):
                yield Label("Benchmark Status", id="status-header")

                with Container(classes="metric-line"):
                    yield Label("Status:", classes="metric-label")
                    yield Label(
                        "Idle", classes="metric-value status-idle", id="status-value"
                    )

                with Container(classes="metric-line"):
                    yield Label("Progress:", classes="metric-label")
                    yield Label("--", classes="metric-value", id="progress-value")

                with Container(classes="metric-line"):
                    yield Label("Errors:", classes="metric-label")
                    yield Label("--", classes="metric-value", id="errors-value")

                with Container(classes="metric-line"):
                    yield Label("Request Rate:", classes="metric-label")
                    yield Label("--", classes="metric-value", id="request-rate-value")

                with Container(classes="metric-line"):
                    yield Label("Processing Rate:", classes="metric-label")
                    yield Label(
                        "--", classes="metric-value", id="processing-rate-value"
                    )

                with Container(classes="metric-line"):
                    yield Label("Elapsed:", classes="metric-label")
                    yield Label("--", classes="metric-value", id="elapsed-value")

                with Container(classes="metric-line"):
                    yield Label("Request ETA:", classes="metric-label")
                    yield Label("--", classes="metric-value", id="request-eta-value")

                with Container(classes="metric-line"):
                    yield Label("Results ETA:", classes="metric-label")
                    yield Label("--", classes="metric-value", id="results-eta-value")

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
            phase_info = profile_run.phase_infos.get(CreditPhase.PROFILING)
            if not phase_info:
                self._show_idle_state()
                return

            self._update_progress(phase_info)
            self._update_status(profile_run, phase_info)
            self._update_metrics(profile_run, phase_info)

        except Exception as e:
            self.debug(lambda e=e: f"Display update error: {e}")

        self.refresh()

    def _show_idle_state(self) -> None:
        """Show idle state for all widgets."""
        updates = [
            ("main-progress", lambda w: w.update(progress=0)),
            ("records-progress", lambda w: w.update(progress=0)),
            ("progress-label", lambda w: w.update("Waiting for benchmark data...")),
            ("records-label", lambda w: w.update("Processing results...")),
            (
                "status-value",
                lambda w: w.update("Idle") or w.set_classes("metric-value status-idle"),
            ),
            ("progress-value", lambda w: w.update("--")),
            ("request-rate-value", lambda w: w.update("--")),
            ("processing-rate-value", lambda w: w.update("--")),
            ("errors-value", lambda w: w.update("--")),
            ("elapsed-value", lambda w: w.update("--")),
            ("request-eta-value", lambda w: w.update("--")),
            ("results-eta-value", lambda w: w.update("--")),
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
                # Update request progress bar
                progress_value = min(
                    100,
                    (phase_info.completed / phase_info.total_expected_requests) * 100,
                )
                self.query_one("#main-progress", ProgressBar).update(
                    progress=progress_value
                )

                progress_text = (
                    f"Executing {CreditPhase.PROFILING.value.capitalize()} requests..."
                )
                self.query_one("#progress-label", Label).update(progress_text)

                # Update records progress bar
                processed_count = phase_info.processed or 0
                records_progress_value = min(
                    100, (processed_count / phase_info.total_expected_requests) * 100
                )
                self.query_one("#records-progress", ProgressBar).update(
                    progress=records_progress_value
                )

    def _update_status(self, profile_run, phase_info) -> None:
        """Update status indicator."""
        with contextlib.suppress(Exception):
            status_widget = self.query_one("#status-value", Label)

            if phase_info.is_complete:
                status_widget.update("Complete")
                status_widget.set_classes("metric-value status-complete")
            elif profile_run.was_cancelled:
                status_widget.update("Cancelled")
                status_widget.set_classes("metric-value status-cancelled")
            elif phase_info.is_started:
                status_widget.update("Processing")
                status_widget.set_classes("metric-value status-processing")
            else:
                status_widget.update("Idle")
                status_widget.set_classes("metric-value status-idle")

    def _update_metrics(self, profile_run, phase_info) -> None:
        """Update all metrics with Rich-style formatting."""
        with contextlib.suppress(Exception):
            # Progress count
            if phase_info.total_expected_requests:
                sent = phase_info.sent or 0
                total = phase_info.total_expected_requests
                progress_pct = (sent / total) * 100 if total > 0 else 0
                progress_text = f"{sent:,} / {total:,} requests ({progress_pct:.1f}%)"
            else:
                progress_text = f"{phase_info.completed:,} requests"
            self.query_one("#progress-value", Label).update(progress_text)

            # Errors with color coding
            error_count = phase_info.errors or 0
            processed_count = phase_info.processed or 0
            if processed_count > 0:
                error_percent = (error_count / processed_count) * 100
                error_text = (
                    f"{error_count:,} / {processed_count:,} ({error_percent:.1f}%)"
                )
                error_class = "metric-value " + (
                    "error-none"
                    if error_percent == 0
                    else "error-high"
                    if error_percent > 10
                    else "error-medium"
                )
            else:
                error_text = f"{error_count:,} / {processed_count:,} (0.0%)"
                error_class = "metric-value error-none"

            error_widget = self.query_one("#errors-value", Label)
            error_widget.update(error_text)
            error_widget.set_classes(error_class)

            # Rates
            rate_text = (
                f"{profile_run.requests_per_second:.1f} req/s"
                if profile_run.requests_per_second
                else "0.0 req/s"
            )
            self.query_one("#request-rate-value", Label).update(rate_text)

            proc_rate_text = (
                f"{profile_run.processed_per_second:.1f} req/s"
                if profile_run.processed_per_second
                else "0.0 req/s"
            )
            self.query_one("#processing-rate-value", Label).update(proc_rate_text)

            # Time metrics
            elapsed_text = (
                format_duration(profile_run.elapsed_time)
                if profile_run.elapsed_time
                else "00:00:00"
            )
            self.query_one("#elapsed-value", Label).update(elapsed_text)

            request_eta_text = (
                format_duration(profile_run.requests_eta)
                if profile_run.requests_eta
                else "--"
            )
            self.query_one("#request-eta-value", Label).update(request_eta_text)

            results_eta_text = (
                format_duration(profile_run.processing_eta)
                if profile_run.processing_eta
                else "--"
            )
            self.query_one("#results-eta-value", Label).update(results_eta_text)
