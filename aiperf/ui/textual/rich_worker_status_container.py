# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time
from enum import Enum

from pydantic import Field
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Label, Static

from aiperf.common.enums import CreditPhase
from aiperf.common.messages import WorkerHealthMessage
from aiperf.common.pydantic_utils import AIPerfBaseModel
from aiperf.common.utils import format_bytes
from aiperf.common.worker_models import WorkerPhaseTaskStats


class WorkerStatus(str, Enum):
    """Enum for worker status classifications."""

    HEALTHY = "healthy"
    HIGH_LOAD = "high_load"
    ERROR = "error"
    IDLE = "idle"
    STALE = "stale"


class WorkerStatusSummary(AIPerfBaseModel):
    """Pydantic model for worker status summary statistics."""

    healthy_count: int = Field(default=0, description="Number of healthy workers")
    warning_count: int = Field(
        default=0, description="Number of workers with high load"
    )
    error_count: int = Field(default=0, description="Number of workers with errors")
    idle_count: int = Field(default=0, description="Number of idle workers")
    stale_count: int = Field(default=0, description="Number of stale workers")

    @property
    def total_count(self) -> int:
        """Total number of workers."""
        return (
            self.healthy_count
            + self.warning_count
            + self.error_count
            + self.idle_count
            + self.stale_count
        )


class WorkerStatusData(AIPerfBaseModel):
    """Pydantic model for individual worker status data."""

    worker_id: str = Field(..., description="Worker service ID")
    status: WorkerStatus = Field(..., description="Current worker status")
    in_progress_tasks: int = Field(default=0, description="Number of tasks in progress")
    completed_tasks: int = Field(default=0, description="Number of completed tasks")
    failed_tasks: int = Field(default=0, description="Number of failed tasks")
    cpu_usage: float = Field(default=0.0, description="CPU usage percentage")
    memory_display: str = Field(default="0 MB", description="Formatted memory usage")
    io_read_display: str = Field(default="0 B", description="Formatted read I/O")
    io_write_display: str = Field(default="0 B", description="Formatted write I/O")


class WorkerStatusTable(Widget):
    """Table widget for displaying worker status information."""

    DEFAULT_CSS = """
    WorkerStatusTable {
        height: 1fr;
        border: solid $accent;
        border-title-color: $accent;
    }

    DataTable {
        height: 1fr;
    }

    .status-healthy {
        color: $success;
        text-style: bold;
    }

    .status-high-load {
        color: $warning;
        text-style: bold;
    }

    .status-error {
        color: $error;
        text-style: bold;
    }

    .status-idle {
        color: $text-muted;
    }

    .status-stale {
        color: $surface-darken-1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.data_table: DataTable | None = None
        self.border_title = "Worker Status Table"

    def compose(self) -> ComposeResult:
        """Compose the table widget."""
        self.data_table = DataTable()
        self.data_table.add_columns(
            "Worker ID",
            "Status",
            "Active",
            "Completed",
            "Failed",
            "CPU",
            "Memory",
            "Read",
            "Write",
        )
        yield self.data_table

    def update_workers(self, workers_data: list[WorkerStatusData]) -> None:
        """Update the table with new worker data."""
        if not self.data_table:
            return

        # Clear existing data
        self.data_table.clear()

        # Add worker rows
        for worker in workers_data:
            status_style = f"status-{worker.status.value.replace('_', '-')}"
            self.data_table.add_row(
                worker.worker_id,
                Text(worker.status.value.replace("_", " ").title(), style=status_style),
                f"{worker.in_progress_tasks:,}",
                f"{worker.completed_tasks:,}",
                f"{worker.failed_tasks:,}",
                f"{worker.cpu_usage:.1f}%",
                worker.memory_display,
                worker.io_read_display,
                worker.io_write_display,
            )


class WorkerStatusSummaryWidget(Widget):
    """Widget for displaying worker status summary."""

    DEFAULT_CSS = """
    WorkerStatusSummaryWidget {
        height: 3;
        border: solid $primary;
        border-title-color: $primary;
    }

    #summary-content {
        layout: horizontal;
        height: 1fr;
        align: center middle;
    }

    .summary-item {
        margin: 0 1;
        text-align: center;
    }

    .summary-healthy {
        color: $success;
        text-style: bold;
    }

    .summary-warning {
        color: $warning;
        text-style: bold;
    }

    .summary-error {
        color: $error;
        text-style: bold;
    }

    .summary-idle {
        color: $text-muted;
    }

    .summary-stale {
        color: $surface-darken-1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.border_title = "Worker Summary"

    def compose(self) -> ComposeResult:
        """Compose the summary widget."""
        with Horizontal(id="summary-content"):
            yield Label("Summary: ", classes="summary-item")
            yield Label(
                "0 healthy", id="healthy-count", classes="summary-item summary-healthy"
            )
            yield Label("•", classes="summary-item")
            yield Label(
                "0 high load",
                id="warning-count",
                classes="summary-item summary-warning",
            )
            yield Label("•", classes="summary-item")
            yield Label(
                "0 errors", id="error-count", classes="summary-item summary-error"
            )
            yield Label("•", classes="summary-item")
            yield Label("0 idle", id="idle-count", classes="summary-item summary-idle")
            yield Label("•", classes="summary-item")
            yield Label(
                "0 stale", id="stale-count", classes="summary-item summary-stale"
            )

    def update_summary(self, summary: WorkerStatusSummary) -> None:
        """Update the summary display."""
        try:
            self.query_one("#healthy-count", Label).update(
                f"{summary.healthy_count} healthy"
            )
            self.query_one("#warning-count", Label).update(
                f"{summary.warning_count} high load"
            )
            self.query_one("#error-count", Label).update(
                f"{summary.error_count} errors"
            )
            self.query_one("#idle-count", Label).update(f"{summary.idle_count} idle")
            self.query_one("#stale-count", Label).update(f"{summary.stale_count} stale")
        except Exception:
            pass  # Silently handle cases where widgets aren't mounted yet


class RichWorkerStatusContainer(Container):
    """Textual container that encapsulates the Rich workers dashboard functionality.

    This container replicates the functionality of the Rich WorkerStatusElement,
    providing the same table layout, status determination logic, and summary statistics.
    """

    DEFAULT_CSS = """
    RichWorkerStatusContainer {
        border: round $primary;
        border-title-color: $primary;
        border-title-background: $surface;
        height: 1fr;
        layout: vertical;
    }

    #summary-section {
        height: auto;
        margin: 0 0 1 0;
    }

    #table-section {
        height: 1fr;
        margin: 0;
    }

    #no-workers-message {
        height: 1fr;
        content-align: center middle;
        color: $warning;
        text-style: italic;
    }
    """

    def __init__(
        self,
        worker_health: dict[str, WorkerHealthMessage] | None = None,
        worker_last_seen: dict[str, float] | None = None,
        stale_threshold: float = 30.0,
        error_rate_threshold: float = 0.1,
        high_cpu_threshold: float = 75.0,
    ) -> None:
        super().__init__()
        self.worker_health = worker_health or {}
        self.worker_last_seen = worker_last_seen or {}
        self.stale_threshold = stale_threshold
        self.error_rate_threshold = error_rate_threshold
        self.high_cpu_threshold = high_cpu_threshold

        self.summary_widget: WorkerStatusSummaryWidget | None = None
        self.table_widget: WorkerStatusTable | None = None

        self.border_title = "Worker Status Monitor"

    def compose(self) -> ComposeResult:
        """Compose the container layout."""
        with Vertical():
            with Container(id="summary-section"):
                self.summary_widget = WorkerStatusSummaryWidget()
                yield self.summary_widget

            with Container(id="table-section"):
                if not self.worker_health:
                    yield Static("No worker data available", id="no-workers-message")
                else:
                    self.table_widget = WorkerStatusTable()
                    yield self.table_widget

    def update_worker_health(
        self,
        worker_health: dict[str, WorkerHealthMessage],
        worker_last_seen: dict[str, float] | None = None,
    ) -> None:
        """Update the container with new worker health data."""
        self.worker_health = worker_health
        if worker_last_seen:
            self.worker_last_seen = worker_last_seen

        # Update last seen time for current workers
        current_time = time.time()
        for worker_id in worker_health:
            if worker_id not in self.worker_last_seen:
                self.worker_last_seen[worker_id] = current_time

        self._refresh_display()

    def update_worker_last_seen(
        self, worker_id: str, timestamp: float | None = None
    ) -> None:
        """Update the last seen timestamp for a specific worker."""
        self.worker_last_seen[worker_id] = timestamp or time.time()
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the display with current worker data."""
        if not self.worker_health:
            self._show_no_workers_message()
            return

        # Process worker data
        workers_data, summary = self._process_worker_data()

        # Update summary
        if self.summary_widget:
            self.summary_widget.update_summary(summary)

        # Update table
        if self.table_widget:
            self.table_widget.update_workers(workers_data)
        elif workers_data:
            # Create table if it doesn't exist
            self._create_table_widget()

    def _show_no_workers_message(self) -> None:
        """Show the no workers message."""
        try:
            # Remove table if it exists
            if self.table_widget:
                self.table_widget.remove()
                self.table_widget = None

            # Show no workers message
            table_section = self.query_one("#table-section")
            if not table_section.query("#no-workers-message"):
                table_section.mount(
                    Static("No worker data available", id="no-workers-message")
                )
        except Exception:
            pass  # Silently handle mounting issues

    def _create_table_widget(self) -> None:
        """Create and mount the table widget."""
        try:
            table_section = self.query_one("#table-section")

            # Remove no workers message if it exists
            try:
                no_workers_msg = table_section.query_one("#no-workers-message")
                no_workers_msg.remove()
            except Exception:
                pass

            # Create and mount table
            self.table_widget = WorkerStatusTable()
            table_section.mount(self.table_widget)

            # Update with current data
            workers_data, _ = self._process_worker_data()
            self.table_widget.update_workers(workers_data)
        except Exception:
            pass  # Silently handle mounting issues

    def _process_worker_data(
        self,
    ) -> tuple[list[WorkerStatusData], WorkerStatusSummary]:
        """Process worker health data and return formatted data and summary."""
        current_time = time.time()
        workers_data = []
        summary = WorkerStatusSummary()

        for service_id, health in sorted(self.worker_health.items()):
            worker_id = service_id
            last_seen = self.worker_last_seen.get(service_id, current_time)

            # Get task stats for steady state phase
            if CreditPhase.STEADY_STATE in health.task_stats:
                task_stats = health.task_stats[CreditPhase.STEADY_STATE]
            else:
                task_stats = WorkerPhaseTaskStats(
                    total=0,
                    completed=0,
                    failed=0,
                )

            # Determine worker status
            status = self._determine_worker_status(
                health, task_stats, last_seen, current_time
            )

            # Update summary counts
            self._update_summary_counts(summary, status)

            # Format memory display
            memory_mb = health.process.memory_usage
            memory_display = (
                f"{memory_mb / 1024:.1f} GB"
                if memory_mb >= 1024
                else f"{memory_mb:.0f} MB"
            )

            # Format I/O display (handle potential None values)
            io_read_display = "0 B"
            io_write_display = "0 B"

            if health.process.io_counters:
                try:
                    if hasattr(health.process.io_counters, "read_chars"):
                        io_read_display = format_bytes(
                            health.process.io_counters.read_chars
                        )
                    if hasattr(health.process.io_counters, "write_chars"):
                        io_write_display = format_bytes(
                            health.process.io_counters.write_chars
                        )
                except (AttributeError, TypeError):
                    pass  # Use default values if attributes don't exist

            # Create worker data
            worker_data = WorkerStatusData(
                worker_id=worker_id,
                status=status,
                in_progress_tasks=task_stats.in_progress,
                completed_tasks=task_stats.completed,
                failed_tasks=task_stats.failed,
                cpu_usage=health.process.cpu_usage,
                memory_display=memory_display,
                io_read_display=io_read_display,
                io_write_display=io_write_display,
            )

            workers_data.append(worker_data)

        return workers_data, summary

    def _determine_worker_status(
        self,
        health: WorkerHealthMessage,
        task_stats: WorkerPhaseTaskStats,
        last_seen: float,
        current_time: float,
    ) -> WorkerStatus:
        """Determine the status of a worker based on health and task statistics."""
        # Check if worker is stale
        if current_time - last_seen > self.stale_threshold:
            return WorkerStatus.STALE

        # Check error rate
        error_rate = task_stats.failed / task_stats.total if task_stats.total > 0 else 0
        if error_rate > self.error_rate_threshold:
            return WorkerStatus.ERROR

        # Check CPU usage
        if health.process.cpu_usage > self.high_cpu_threshold:
            return WorkerStatus.HIGH_LOAD

        # Check if idle (no tasks processed)
        if task_stats.total == 0:
            return WorkerStatus.IDLE

        # Default to healthy
        return WorkerStatus.HEALTHY

    def _update_summary_counts(
        self, summary: WorkerStatusSummary, status: WorkerStatus
    ) -> None:
        """Update summary counts based on worker status."""
        if status == WorkerStatus.HEALTHY:
            summary.healthy_count += 1
        elif status == WorkerStatus.HIGH_LOAD:
            summary.warning_count += 1
        elif status == WorkerStatus.ERROR:
            summary.error_count += 1
        elif status == WorkerStatus.IDLE:
            summary.idle_count += 1
        elif status == WorkerStatus.STALE:
            summary.stale_count += 1

    def on_mount(self) -> None:
        """Handle widget mounting."""
        self._refresh_display()

    def clear_workers(self) -> None:
        """Clear all worker data."""
        self.worker_health.clear()
        self.worker_last_seen.clear()
        self._refresh_display()

    def get_worker_count(self) -> int:
        """Get the total number of workers."""
        return len(self.worker_health)

    def get_summary(self) -> WorkerStatusSummary:
        """Get the current worker status summary."""
        if not self.worker_health:
            return WorkerStatusSummary()

        _, summary = self._process_worker_data()
        return summary
