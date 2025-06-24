# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import sys

from textual.app import ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Label, ProgressBar

from aiperf.common.progress_tracker import ProgressTracker
from aiperf.ui.widgets import (
    DashboardField,
    DashboardFormatter,
    StatusClassifier,
    StatusIndicator,
)

logger = logging.getLogger(__name__)


class ProgressDashboard(Container):
    """Main progress dashboard widget with clean, simplified styling."""

    DEFAULT_CSS = """
    ProgressDashboard {
        border: solid $primary;
        border-title-color: $primary;
        border-title-background: $surface;
        height: 100%;
    }

    #dashboard-content {
        height: 100%;
    }

    #progress-container {
        height: auto;
    }

    #metrics-grid {
        height: auto;
    }

    #progress-label {
        text-align: center;
        text-style: bold;
        color: $text;
        margin: 0 0 1 0;
    }

    StatusIndicator {
        height: 1;
        margin: 0 0 1 0;
    }
    """

    border_title = "AIPerf Performance Dashboard"

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
        self.progress_tracker = progress_tracker

        # Define all dashboard fields declaratively
        self.fields = [
            DashboardField(
                "status-indicator",
                "Status",
                lambda _, profile: (profile.is_complete, profile.was_cancelled),
                lambda data: "Complete"
                if data[0]
                else "Processing"
                if not data[1]
                else "Cancelled",
                lambda data: StatusClassifier.get_completion_status(data[0]),
            ),
            DashboardField(
                "progress-indicator",
                "Progress",
                lambda _, profile: (
                    profile.requests_completed,
                    profile.total_expected_requests,
                ),
                lambda data: DashboardFormatter.format_count_with_total(
                    data[0], data[1]
                ),
                show_dot=False,
            ),
            DashboardField(
                "completion-indicator",
                "Completion",
                lambda _, profile: (
                    (
                        profile.requests_completed
                        / (profile.total_expected_requests or sys.maxsize)
                        * 100
                    )
                    if profile.total_expected_requests is not None
                    and profile.total_expected_requests > 0
                    else 0
                ),
                DashboardFormatter.format_percentage,
                show_dot=False,
            ),
            DashboardField(
                "error-indicator",
                "Errors",
                lambda _, profile: (
                    profile.request_errors,
                    profile.requests_processed,
                    (profile.request_errors / profile.requests_processed) * 100
                    if profile.requests_processed > 0
                    else 0.0,
                ),
                lambda data: DashboardFormatter.format_error_stats(
                    data[0], data[1], data[2]
                ),
                lambda data: StatusClassifier.get_error_status(data[2]),
            ),
            DashboardField(
                "request-rate-indicator",
                "Request Rate",
                lambda _, profile: profile.requests_per_second,
                DashboardFormatter.format_rate,
                show_dot=False,
            ),
            DashboardField(
                "processed-rate-indicator",
                "Processing Rate",
                lambda _, profile: profile.processed_per_second,
                DashboardFormatter.format_rate,
                show_dot=False,
            ),
            DashboardField(
                "elapsed-indicator",
                "Elapsed",
                lambda _, profile: profile.elapsed_time,
                DashboardFormatter.format_duration,
                show_dot=False,
            ),
            DashboardField(
                "eta-indicator",
                "ETA",
                lambda _, profile: profile.eta,
                lambda data: DashboardFormatter.format_duration(data) if data else "--",
                show_dot=False,
            ),
        ]

    def compose(self) -> ComposeResult:
        """Compose the simplified dashboard layout."""
        with Vertical(id="dashboard-content"):
            # Progress Overview
            with Container(id="progress-container"):
                yield ProgressBar(total=100, show_eta=True, show_percentage=True)
                yield Label("", id="progress-label")

            # Performance Metrics - Generated from field definitions
            with Vertical(id="metrics-grid"):
                for field in self.fields:
                    yield StatusIndicator(
                        field.label, id=field.field_id, show_dot=field.show_dot
                    )

    def on_mount(self) -> None:
        """Initialize the dashboard when mounted."""
        self.update_display()

    def update_display(self) -> None:
        """Update all display elements using declarative field system."""
        if not self.is_mounted:
            return

        # Show default content if no profile data is available
        if not self.progress_tracker.current_profile:
            try:
                # Update progress bar with default values
                progress_bar = self.query_one(ProgressBar)
                progress_bar.update(progress=0)

                # Update progress label with default text
                progress_label = self.query_one("#progress-label", Label)
                progress_label.update("Waiting for performance data...")

                # Update all status indicators with default values
                for field in self.fields:
                    try:
                        widget = self.query_one(f"#{field.field_id}", StatusIndicator)
                        widget.update_value("--", "status-idle")
                    except Exception as e:
                        logger.debug(
                            f"Error updating {field.field_id} with default: {e}"
                        )

            except Exception as e:
                logger.debug(f"Error updating display with defaults: {e}")
            return

        try:
            # Update progress bar
            if (
                self.progress_tracker.current_profile.total_expected_requests
                is not None
                and self.progress_tracker.current_profile.total_expected_requests > 0
            ):
                progress_value = min(
                    100,
                    (
                        self.progress_tracker.current_profile.requests_completed
                        / self.progress_tracker.current_profile.total_expected_requests
                    )
                    * 100,
                )
                progress_bar = self.query_one(ProgressBar)
                progress_bar.update(progress=progress_value)

                # Update progress label
                progress_label = self.query_one("#progress-label", Label)
                progress_text = (
                    f"Processing: {self.progress_tracker.current_profile.requests_completed:,} "
                    f"/ {self.progress_tracker.current_profile.total_expected_requests:,} requests"
                )
                progress_label.update(progress_text)

            # Update all status indicators using field definitions
            for field in self.fields:
                field.update(
                    self, self.progress_tracker, self.progress_tracker.current_profile
                )

        except Exception as e:
            logger.debug(f"Display update error: {e}")
