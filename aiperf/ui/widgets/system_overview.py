# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Label, ProgressBar

from aiperf.common.enums import CreditPhase, SystemState
from aiperf.ui.base_widgets import DataDisplayWidget

if TYPE_CHECKING:
    from aiperf.progress.progress_tracker import ProgressTracker


class SystemOverviewWidget(DataDisplayWidget):
    """Clean system overview widget showing essential metrics."""

    DEFAULT_CSS = """
    SystemOverviewWidget {
        border: solid #76b900;
        background: #1a1a1a;
        height: 10;
    }

    SystemOverviewWidget .header {
        background: #76b900;
        color: #000000;
        text-style: bold;
        padding: 0 1;
        dock: top;
        height: 1;
    }

    SystemOverviewWidget .content {
        padding: 1;
        height: 8;
    }

    SystemOverviewWidget .metrics {
        layout: grid;
        grid-size: 3 2;
        grid-gutter: 1;
        height: 5;
    }

    SystemOverviewWidget .metric {
        border: solid #333333;
        background: #222222;
        padding: 0 1;
        text-align: center;
        height: 2;
    }

    SystemOverviewWidget .metric-value {
        color: #00d4aa;
        text-style: bold;
    }

    SystemOverviewWidget .metric-label {
        color: #888888;
    }

    SystemOverviewWidget .progress-section {
        padding-top: 1;
        height: 2;
    }

    SystemOverviewWidget .status-green {
        color: #00ff00;
    }

    SystemOverviewWidget .status-yellow {
        color: #ffaa00;
    }

    SystemOverviewWidget .status-red {
        color: #ff0000;
    }
    """

    widget_title = "System Overview"

    def __init__(self, progress_tracker: "ProgressTracker", **kwargs) -> None:
        super().__init__(progress_tracker, **kwargs)
        self.system_state = SystemState.INITIALIZING

    def compose(self) -> ComposeResult:
        """Compose the system overview widget."""
        with Vertical():
            # Header
            with Horizontal(classes="header"):
                yield Label("NVIDIA AIPerf System")
                yield Label("", id="system-status")

            # Content
            with Vertical(classes="content"):
                # Metrics grid
                with Horizontal(classes="metrics"):
                    yield self._create_metric("total-requests", "0", "Total Requests")
                    yield self._create_metric("success-rate", "0%", "Success Rate")
                    yield self._create_metric("throughput", "0 req/s", "Throughput")
                    yield self._create_metric("active-workers", "0", "Active Workers")
                    yield self._create_metric("avg-latency", "0ms", "Avg Latency")
                    yield self._create_metric("phase-progress", "0%", "Phase Progress")

                # Progress bar
                with Vertical(classes="progress-section"):
                    yield Label("Overall Progress")
                    yield ProgressBar(total=100, id="overall-progress")

    def _create_metric(self, metric_id: str, value: str, label: str) -> Vertical:
        """Create a simple metric display."""
        with Vertical(classes="metric", id=metric_id):
            yield Label(value, classes="metric-value")
            yield Label(label, classes="metric-label")

    def update_content(self) -> None:
        """Update the system overview with current metrics."""
        if not self.progress_tracker or not self.progress_tracker.current_profile_run:
            self._update_empty_state()
            return

        profile_run = self.progress_tracker.current_profile_run
        active_phase = self.progress_tracker.active_credit_phase or CreditPhase.UNKNOWN

        # Update system status
        self._update_system_status(profile_run)

        # Update metrics
        self._update_metrics(profile_run, active_phase)

        # Update progress bar
        self._update_progress_bar(profile_run, active_phase)

    def _update_empty_state(self) -> None:
        """Update widget when no profile run is active."""
        status_label = self.query_one("#system-status", Label)
        status_label.update("System Ready")
        status_label.set_class(False, "status-yellow", "status-red")
        status_label.set_class(True, "status-green")

        # Reset all metrics
        self._update_metric("total-requests", "0")
        self._update_metric("success-rate", "0%")
        self._update_metric("throughput", "0 req/s")
        self._update_metric("active-workers", "0")
        self._update_metric("avg-latency", "0ms")
        self._update_metric("phase-progress", "0%")

        progress_bar = self.query_one("#overall-progress", ProgressBar)
        progress_bar.update(progress=0)

    def _update_system_status(self, profile_run) -> None:
        """Update the system status indicator."""
        status_label = self.query_one("#system-status", Label)

        if profile_run.is_complete:
            status_label.update("Profile Complete")
            status_label.set_class(False, "status-yellow", "status-red")
            status_label.set_class(True, "status-green")
        elif profile_run.is_started:
            status_label.update("Profile Running")
            status_label.set_class(False, "status-green", "status-red")
            status_label.set_class(True, "status-yellow")
        else:
            status_label.update("Profile Initializing")
            status_label.set_class(False, "status-green", "status-yellow")
            status_label.set_class(True, "status-red")

    def _update_metrics(self, profile_run, active_phase: CreditPhase) -> None:
        """Update all metric displays with current values."""
        # Total requests
        total_requests = sum(phase.completed for phase in profile_run.phases.values())
        self._update_metric("total-requests", f"{total_requests:,}")

        # Success rate
        success_rate = self._calculate_success_rate(profile_run, active_phase)
        self._update_metric("success-rate", f"{success_rate:.1f}%")

        # Throughput
        throughput = self._get_current_throughput(profile_run, active_phase)
        self._update_metric("throughput", self.format_rate(throughput))

        # Active workers
        active_workers = self._count_active_workers(profile_run, active_phase)
        total_workers = len(profile_run.worker_task_stats)
        self._update_metric("active-workers", f"{active_workers}/{total_workers}")

        # Average latency
        avg_latency = self._calculate_avg_latency(profile_run)
        self._update_metric("avg-latency", f"{avg_latency:.1f}ms")

        # Phase progress
        phase_progress = self._get_phase_progress(profile_run, active_phase)
        self._update_metric("phase-progress", f"{phase_progress:.1f}%")

    def _update_progress_bar(self, profile_run, active_phase: CreditPhase) -> None:
        """Update the overall progress bar."""
        progress_bar = self.query_one("#overall-progress", ProgressBar)

        if profile_run.is_complete:
            progress_bar.update(progress=100)
            return

        # Calculate overall progress based on completed phases
        total_phases = len(CreditPhase)
        completed_phases = sum(
            1 for phase in profile_run.phases.values() if phase.is_complete
        )

        if active_phase and active_phase in profile_run.phases:
            active_phase_progress = self._get_phase_progress(profile_run, active_phase)
            overall_progress = (completed_phases / total_phases) * 100 + (
                active_phase_progress / total_phases
            )
        else:
            overall_progress = (completed_phases / total_phases) * 100

        progress_bar.update(progress=min(overall_progress, 100))

    def _update_metric(self, metric_id: str, value: str) -> None:
        """Update a metric display."""
        try:
            metric_widget = self.query_one(f"#{metric_id}", Vertical)
            value_label = metric_widget.query_one(Label)
            value_label.update(value)
        except Exception:
            # Widget not found or not ready yet
            pass

    def _calculate_success_rate(self, profile_run, active_phase: CreditPhase) -> float:
        """Calculate overall success rate."""
        if not profile_run.processing_stats:
            return 0.0

        total = sum(
            stats.total_processed for stats in profile_run.processing_stats.values()
        )
        errors = sum(stats.errors for stats in profile_run.processing_stats.values())

        if total == 0:
            return 0.0

        return ((total - errors) / total) * 100

    def _get_current_throughput(self, profile_run, active_phase: CreditPhase) -> float:
        """Get current throughput in requests per second."""
        if not active_phase or active_phase not in profile_run.phases:
            return 0.0

        phase_stats = profile_run.phases[active_phase]
        if not phase_stats.is_started:
            return 0.0

        elapsed_time = phase_stats.elapsed_time
        if elapsed_time <= 0:
            return 0.0

        return phase_stats.completed / elapsed_time

    def _count_active_workers(self, profile_run, active_phase: CreditPhase) -> int:
        """Count the number of active workers."""
        if not profile_run.worker_task_stats:
            return 0

        active_count = 0
        for worker_stats in profile_run.worker_task_stats.values():
            if active_phase in worker_stats:
                phase_stats = worker_stats[active_phase]
                if phase_stats.in_progress > 0:
                    active_count += 1

        return active_count

    def _calculate_avg_latency(self, profile_run) -> float:
        """Calculate average latency."""
        # Placeholder - implement based on available metrics
        return 0.0

    def _get_phase_progress(self, profile_run, active_phase: CreditPhase) -> float:
        """Get progress percentage for the current phase."""
        if not active_phase or active_phase not in profile_run.phases:
            return 0.0

        phase_stats = profile_run.phases[active_phase]
        if not phase_stats.total or phase_stats.total <= 0:
            return 0.0

        return (phase_stats.completed / phase_stats.total) * 100
