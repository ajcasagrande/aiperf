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
from aiperf.common.models import AIPerfBaseModel, WorkerPhaseTaskStats
from aiperf.common.models.health_models import IOCounters
from aiperf.common.utils import format_bytes


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
        self._columns_setup = False
        self._sort_column = 5  # CPU column index (0-based)
        self._sort_reverse = True  # Sort CPU descending by default
        self._column_names = [
            "Worker ID",
            "Status",
            "Active",
            "Completed",
            "Failed",
            "CPU",
            "Memory",
            "Read",
            "Write",
        ]
        self._column_keys: list = []

    def compose(self) -> ComposeResult:
        """Compose the table widget."""
        self.data_table = DataTable(cursor_type="row", show_cursor=False)
        yield self.data_table

    def _setup_columns(self) -> None:
        """Setup table columns after mounting."""
        if not self.data_table or self._columns_setup:
            return

        self._add_columns_with_indicators()
        self._columns_setup = True

    def _add_columns_with_indicators(self) -> None:
        """Add columns with sort indicators."""
        if not self.data_table:
            return

        # Clear existing columns
        self.data_table.clear(columns=True)
        self._column_keys = []

        # Add columns with appropriate indicators and store keys
        for i, column_name in enumerate(self._column_names):
            if i == self._sort_column:
                # Add sort indicator to the sorted column
                indicator = " ↓" if self._sort_reverse else " ↑"
                header_text = column_name + indicator
            else:
                # No indicator for other columns
                header_text = column_name + "  "

            column_key = self.data_table.add_column(header_text)
            self._column_keys.append(column_key)

    def _update_column_headers(self) -> None:
        """Update column headers with sort indicators."""
        if not self.data_table:
            return

        # Store current data before clearing
        current_data = []
        if self.data_table.row_count > 0:
            for row_key in self.data_table.rows:
                row_data = self.data_table.get_row(row_key)
                current_data.append(row_data)

        # Recreate columns with new indicators
        self._add_columns_with_indicators()

        # Restore the data
        for row_data in current_data:
            self.data_table.add_row(*row_data)

        # Apply the sort using the correct column key
        if self.data_table.row_count > 0 and self._column_keys:
            sort_column_key = self._column_keys[self._sort_column]
            self.data_table.sort(sort_column_key, reverse=self._sort_reverse)

    def on_mount(self) -> None:
        """Handle widget mounting."""
        self._setup_columns()

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Handle column header clicks for sorting."""
        if not self.data_table:
            return

        column_index = event.column_index

        # Toggle sort direction if clicking the same column
        if column_index == self._sort_column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = column_index
            # Default sort directions for different columns
            if column_index in [2, 3, 4, 5]:  # Active, Completed, Failed, CPU
                self._sort_reverse = True  # Descending for numeric columns
            else:
                self._sort_reverse = False  # Ascending for text columns

        # Update column headers with new sort indicators
        self._update_column_headers()

    def update_workers(self, workers_data: list[WorkerStatusData]) -> None:
        """Update the table with new worker data."""
        if not self.data_table:
            return

        # Ensure columns are setup
        self._setup_columns()

        # Clear existing data
        self.data_table.clear()

        # Add worker rows
        for worker in workers_data:
            # Map status to Rich style strings
            status_styles = {
                WorkerStatus.HEALTHY: "bold #6fbc76",
                WorkerStatus.HIGH_LOAD: "bold yellow",
                WorkerStatus.ERROR: "bold red",
                WorkerStatus.IDLE: "dim",
                WorkerStatus.STALE: "dim white",
            }

            status_style = status_styles.get(worker.status, "white")

            self.data_table.add_row(
                Text(worker.worker_id, style="bold cyan"),
                Text(
                    worker.status.value.replace("_", " ").title(),
                    style=status_style,
                    justify="right",
                ),
                f"{worker.in_progress_tasks:,}",
                f"{worker.completed_tasks:,}",
                f"{worker.failed_tasks:,}",
                f"{worker.cpu_usage:.1f}%",
                worker.memory_display,
                worker.io_read_display,
                worker.io_write_display,
            )

        # Apply current sort if we have data
        if self.data_table.row_count > 0 and self._column_keys:
            sort_column_key = self._column_keys[self._sort_column]
            self.data_table.sort(sort_column_key, reverse=self._sort_reverse)


class RichWorkerStatusContainer(Container):
    """Textual container that displays worker status information in a single panel."""

    DEFAULT_CSS = """
    RichWorkerStatusContainer {
        border: round $primary;
        border-title-color: $primary;
        border-title-background: $surface;
        height: 1fr;
        layout: vertical;
    }

    #summary-content {
        height: 1;
        layout: horizontal;
        align: left middle;
        margin: 0 1 1 1;
    }

    .summary-item {
        margin: 0 1;
    }

    .summary-title {
        text-style: bold;
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

    #table-section {
        height: 1fr;
        margin: 0 1 1 1;
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

        self.table_widget: WorkerStatusTable | None = None

        self.border_title = "Worker Status"

    def compose(self) -> ComposeResult:
        """Compose the container layout."""
        with Vertical():
            with Horizontal(id="summary-content"):
                yield Label("Summary: ", classes="summary-item summary-title")
                yield Label(
                    "0 healthy",
                    id="healthy-count",
                    classes="summary-item summary-healthy",
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
                yield Label(
                    "0 idle", id="idle-count", classes="summary-item summary-idle"
                )
                yield Label("•", classes="summary-item")
                yield Label(
                    "0 stale", id="stale-count", classes="summary-item summary-stale"
                )

            with Container(id="table-section"):
                if not self.worker_health:
                    yield Static("No worker data available", id="no-workers-message")
                else:
                    self.table_widget = WorkerStatusTable()
                    yield self.table_widget

    def update_worker_health(
        self,
        message: WorkerHealthMessage,
    ) -> None:
        """Update the container with new worker health data."""
        self.worker_health[message.service_id] = message
        self.worker_last_seen[message.service_id] = time.time()
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
        self._update_summary_display(summary)

        # Update table
        if self.table_widget:
            self.table_widget.update_workers(workers_data)
        elif workers_data:
            # Create table if it doesn't exist
            self._create_table_widget()

    def _update_summary_display(self, summary: WorkerStatusSummary) -> None:
        """Update the summary display with colored labels."""
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

    def _show_no_workers_message(self) -> None:
        """Show the no workers message."""
        try:
            # Update summary to show no workers
            self._update_summary_display(WorkerStatusSummary())

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
            if CreditPhase.PROFILING in health.task_stats:
                task_stats = health.task_stats[CreditPhase.PROFILING]
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
                    if isinstance(health.process.io_counters, IOCounters):
                        io_read_display = format_bytes(
                            health.process.io_counters.read_chars
                        )
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
