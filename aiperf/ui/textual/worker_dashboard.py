# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import contextlib
import time
from typing import NamedTuple

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Label
from textual.widgets._data_table import ColumnKey, RowKey

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums import CaseInsensitiveStrEnum
from aiperf.common.models import AIPerfBaseModel, IOCounters, WorkerStats
from aiperf.common.utils import format_bytes

_logger = AIPerfLogger(__name__)


class WorkerStatus(CaseInsensitiveStrEnum):
    HEALTHY = "healthy"
    HIGH_LOAD = "high_load"
    ERROR = "error"
    IDLE = "idle"
    STALE = "stale"

    @property
    def style(self) -> str:
        styles = {
            self.HEALTHY: "bold #6fbc76",
            self.HIGH_LOAD: "bold yellow",
            self.ERROR: "bold red",
            self.IDLE: "dim",
            self.STALE: "dim white",
        }
        return styles[self]


class WorkerStatusSummary(AIPerfBaseModel):
    healthy_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    idle_count: int = 0
    stale_count: int = 0


class WorkerData(NamedTuple):
    worker_id: str
    status: WorkerStatus
    in_progress: int
    completed: int
    failed: int
    cpu_usage: float | None
    memory_mb: float | None
    io_read_bytes: int
    io_write_bytes: int


class WorkerStatusTable(Widget):
    DEFAULT_CSS = """
    WorkerStatusTable {
        height: 1fr;
        &:focus {
            background-tint: $primary 0%;
        }
    }
    DataTable {
        height: 1fr;
        scrollbar-size-vertical: 1;
        scrollbar-size-horizontal: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.data_table: DataTable | None = None
        self._sort_column = 0  # Worker ID column
        self._sort_reverse = False
        self._worker_row_keys: dict[str, RowKey] = {}  # worker_id -> row_key mapping
        self._columns_initialized = False
        self._column_keys: dict[str, ColumnKey] = {}

    def compose(self) -> ComposeResult:
        self.data_table = DataTable(cursor_type="row", show_cursor=False)
        yield self.data_table

    def on_mount(self) -> None:
        if self.data_table and not self._columns_initialized:
            self._initialize_columns()

    def _initialize_columns(self) -> None:
        """Initialize table columns."""
        if not self.data_table:
            return

        columns = [
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
        for col in columns:
            self._column_keys[col] = self.data_table.add_column(
                Text(col, justify="right")
            )
        self._columns_initialized = True
        self.data_table.fixed_columns = 1

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        if not self.data_table:
            return

        if event.column_index == self._sort_column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = event.column_index
            # Active, Completed, Failed, CPU
            self._sort_reverse = event.column_index in [2, 3, 4, 5]

        # Re-sort when user clicks headers
        # For now, fall back to simple rebuild on sort to maintain simplicity
        current_data = getattr(self, "_last_data", [])
        if current_data:
            self.update_workers(current_data)

    def _format_worker_row(self, worker: WorkerData) -> list:
        """Format worker data into row cells."""
        memory_display = (
            f"{format_bytes(int(worker.memory_mb * 1024 * 1024))}"
            if worker.memory_mb is not None
            else "N/A"
        )

        return [
            Text(worker.worker_id, style="bold cyan", justify="right"),
            Text(
                worker.status.value.replace("_", " ").title(),
                style=worker.status.style,
                justify="right",
            ),
            Text(f"{worker.in_progress:,}", justify="right"),
            Text(f"{worker.completed:,}", justify="right"),
            Text(f"{worker.failed:,}", justify="right"),
            Text(
                f"{worker.cpu_usage:.1f}%" if worker.cpu_usage is not None else "N/A",
                justify="right",
            ),
            Text(memory_display, justify="right"),
            Text(format_bytes(worker.io_read_bytes), justify="right"),
            Text(format_bytes(worker.io_write_bytes), justify="right"),
        ]

    def update_single_worker(self, worker_data: WorkerData) -> None:
        """Update a single worker's row if it exists, or add it if new."""
        if not self.data_table or not self.data_table.is_mounted:
            return

        if not self._columns_initialized:
            self._initialize_columns()

        worker_id = worker_data.worker_id
        row_cells = self._format_worker_row(worker_data)

        if worker_id in self._worker_row_keys:
            # Update existing worker row
            row_key = self._worker_row_keys[worker_id]

            # Validate that the row still exists in the table
            try:
                # Check if row exists by trying to get its coordinate
                self.data_table.get_row(row_key)
            except Exception:
                # Row doesn't exist anymore, add it as new
                row_key = self.data_table.add_row(*row_cells)
                self._worker_row_keys[worker_id] = row_key
                # Refresh the display after adding new row
                self.data_table.refresh()
                return

            # Update each cell in the row using column names for better API compatibility
            column_names = [
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

            cells_updated = 0
            for col_name, cell_value in zip(column_names, row_cells, strict=False):
                try:
                    self.data_table.update_cell(
                        row_key,
                        self._column_keys[col_name],
                        cell_value,
                        update_width=True,
                    )
                    cells_updated += 1
                except Exception as e:
                    _logger.error(
                        f"Error updating cell {col_name} for worker {worker_id}: {e!r}"
                    )

            # Refresh the display after updating cells
            if cells_updated > 0:
                self.data_table.refresh()
        else:
            # Add new worker row
            row_key = self.data_table.add_row(*row_cells)
            self._worker_row_keys[worker_id] = row_key
            # Refresh the display after adding new row
            self.data_table.refresh()

    def remove_worker(self, worker_id: str) -> None:
        """Remove a worker row from the table."""
        if not self.data_table or worker_id not in self._worker_row_keys:
            return

        row_key = self._worker_row_keys[worker_id]
        with contextlib.suppress(Exception):
            self.data_table.remove_row(row_key)

        del self._worker_row_keys[worker_id]

    def update_workers(self, workers_data: list[WorkerData]) -> None:
        """Update workers with full rebuild (used for sorting or major changes)."""
        if not self.data_table:
            return

        if not self._columns_initialized:
            self._initialize_columns()

        self._last_data = workers_data
        self.data_table.clear()
        self._worker_row_keys.clear()

        # Sort data
        if workers_data:
            sort_key_funcs = [
                lambda w: w.worker_id,
                lambda w: w.status.value,
                lambda w: w.in_progress,
                lambda w: w.completed,
                lambda w: w.failed,
                lambda w: w.cpu_usage or 0,
                lambda w: w.memory_mb or 0,
                lambda w: w.io_read_bytes,
                lambda w: w.io_write_bytes,
            ]
            workers_data = sorted(
                workers_data,
                key=sort_key_funcs[self._sort_column],
                reverse=self._sort_reverse,
            )

        # Add all rows
        for worker in workers_data:
            row_cells = self._format_worker_row(worker)
            row_key = self.data_table.add_row(*row_cells)
            self._worker_row_keys[worker.worker_id] = row_key

    def clear_workers(self) -> None:
        """Clear all worker data."""
        if self.data_table:
            self.data_table.clear()
        self._worker_row_keys.clear()


class WorkerDashboard(Container):
    DEFAULT_CSS = """
    WorkerDashboard {
        border: round $primary;
        border-title-color: $primary;
        border-title-style: bold;
        height: 1fr;
        layout: vertical;
    }

    #summary-content {
        height: 1;
        layout: horizontal;
        align: left middle;
        margin: 0 1 0 1;
    }

    .summary-item { margin: 0 1; }
    .summary-title { text-style: bold; }
    .summary-healthy { color: $success; text-style: bold; }
    .summary-warning { color: $warning; text-style: bold; }
    .summary-error { color: $error; text-style: bold; }
    .summary-idle { color: $text-muted; }
    .summary-stale { color: $surface-darken-1; }

    #table-section {
        height: 1fr;
        margin: 0 0 0 1;
    }
    """

    def __init__(
        self,
        stale_threshold: float = 30.0,
        error_rate_threshold: float = 0.1,
        high_cpu_threshold: float = 75.0,
    ) -> None:
        super().__init__()
        self.worker_stats: dict[str, WorkerStats] = {}
        self.stale_threshold = stale_threshold
        self.error_rate_threshold = error_rate_threshold
        self.high_cpu_threshold = high_cpu_threshold
        self.table_widget: WorkerStatusTable | None = None
        self.border_title = "Worker Status"

    def compose(self) -> ComposeResult:
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
                # Always create the table widget - it will be empty initially
                self.table_widget = WorkerStatusTable()
                yield self.table_widget

    def on_worker_stats_update(self, worker_id: str, worker_stats: WorkerStats) -> None:
        """Handle individual worker updates efficiently."""
        self.worker_stats[worker_id] = worker_stats

        # Process this single worker's data
        worker_data = self._process_single_worker_data(worker_id, worker_stats)

        # Update just this worker in the table
        if self.table_widget:
            self.table_widget.update_single_worker(worker_data)

        # Update summary with all workers
        self._update_summary_from_all_workers()

    def _process_single_worker_data(
        self, worker_id: str, worker_stats: WorkerStats
    ) -> WorkerData:
        """Process data for a single worker."""
        current_time = time.time_ns()
        last_seen = worker_stats.update_ns or current_time

        # Get task stats
        task_stats = worker_stats.tasks

        # Determine status
        status = self._get_worker_status(worker_stats, last_seen, current_time)

        # Get I/O data
        io_read = io_write = 0
        if (
            worker_stats.health
            and worker_stats.health.io_counters
            and isinstance(worker_stats.health.io_counters, IOCounters)
        ):
            io_read = worker_stats.health.io_counters.read_chars or 0
            io_write = worker_stats.health.io_counters.write_chars or 0

        return WorkerData(
            worker_id=worker_id,
            status=status,
            in_progress=task_stats.in_progress,
            completed=task_stats.completed,
            failed=task_stats.failed,
            cpu_usage=worker_stats.health.cpu_usage if worker_stats.health else None,
            memory_mb=worker_stats.health.memory_usage if worker_stats.health else None,
            io_read_bytes=io_read,
            io_write_bytes=io_write,
        )

    def _update_summary_from_all_workers(self) -> None:
        """Update summary from all current workers."""
        if not self.worker_stats:
            self._update_summary(WorkerStatusSummary())
            return

        _, summary = self._process_worker_data()
        self._update_summary(summary)

    def _refresh_display(self) -> None:
        """Full refresh display (used when workers are removed or major changes)."""
        if not self.worker_stats:
            self._update_summary(WorkerStatusSummary())
            if self.table_widget:
                self.table_widget.clear_workers()
            return

        workers_data, summary = self._process_worker_data()
        self._update_summary(summary)

        if self.table_widget:
            self.table_widget.update_workers(workers_data)

    def _update_summary(self, summary: WorkerStatusSummary) -> None:
        updates = [
            ("healthy-count", f"{summary.healthy_count} healthy"),
            ("warning-count", f"{summary.warning_count} high load"),
            ("error-count", f"{summary.error_count} errors"),
            ("idle-count", f"{summary.idle_count} idle"),
            ("stale-count", f"{summary.stale_count} stale"),
        ]

        for label_id, text in updates:
            with contextlib.suppress(Exception):
                self.query_one(f"#{label_id}", Label).update(text)

    def _process_worker_data(self) -> tuple[list[WorkerData], WorkerStatusSummary]:
        workers_data = []
        summary = WorkerStatusSummary()

        for worker_id, worker_stats in sorted(self.worker_stats.items()):
            worker_data = self._process_single_worker_data(worker_id, worker_stats)
            workers_data.append(worker_data)

            # Update summary
            if worker_data.status == WorkerStatus.HEALTHY:
                summary.healthy_count += 1
            elif worker_data.status == WorkerStatus.HIGH_LOAD:
                summary.warning_count += 1
            elif worker_data.status == WorkerStatus.ERROR:
                summary.error_count += 1
            elif worker_data.status == WorkerStatus.IDLE:
                summary.idle_count += 1
            elif worker_data.status == WorkerStatus.STALE:
                summary.stale_count += 1

        return workers_data, summary

    def _get_worker_status(
        self,
        worker_stats: WorkerStats,
        last_seen: int,
        current_time_ns: int,
    ) -> WorkerStatus:
        # Convert stale_threshold from seconds to nanoseconds for comparison
        stale_threshold_ns = self.stale_threshold * 1_000_000_000

        if current_time_ns - last_seen > stale_threshold_ns:
            return WorkerStatus.STALE

        error_rate = (
            worker_stats.tasks.failed / worker_stats.tasks.total
            if worker_stats.tasks.total > 0
            else 0
        )
        if error_rate > self.error_rate_threshold:
            return WorkerStatus.ERROR

        if (
            worker_stats.health
            and worker_stats.health.cpu_usage
            and worker_stats.health.cpu_usage > self.high_cpu_threshold
        ):
            return WorkerStatus.HIGH_LOAD

        if worker_stats.tasks.total == 0:
            return WorkerStatus.IDLE

        return WorkerStatus.HEALTHY

    def clear_workers(self) -> None:
        self.worker_stats.clear()
        self._refresh_display()

    def get_worker_count(self) -> int:
        return len(self.worker_stats)

    def get_summary(self) -> WorkerStatusSummary:
        if not self.worker_stats:
            return WorkerStatusSummary()
        _, summary = self._process_worker_data()
        return summary
