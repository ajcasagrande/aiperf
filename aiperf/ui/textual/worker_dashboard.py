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
from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import CaseInsensitiveStrEnum
from aiperf.common.models import AIPerfBaseModel, IOCounters, ProcessHealth, WorkerStats
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
    memory_bytes: int | None
    io_read_bytes: int
    io_write_bytes: int


class WorkerDataProcessor:
    """Processes worker statistics and health data."""

    def __init__(
        self,
        stale_threshold: float = 30.0,
        error_rate_threshold: float = 0.1,
        high_cpu_threshold: float = 75.0,
    ):
        self.stale_threshold = stale_threshold
        self.error_rate_threshold = error_rate_threshold
        self.high_cpu_threshold = high_cpu_threshold

    def extract_io_data(self, health: ProcessHealth | None) -> tuple[int, int]:
        """Extract I/O read and write bytes from health data."""
        if not health or not health.io_counters:
            return 0, 0

        io_counters = health.io_counters
        if isinstance(io_counters, IOCounters):
            return io_counters.read_chars or 0, io_counters.write_chars or 0
        elif isinstance(io_counters, tuple | list) and len(io_counters) >= 6:
            return io_counters[4] or 0, io_counters[5] or 0
        return 0, 0

    def get_worker_status(
        self, worker_stats: WorkerStats, current_time_ns: int
    ) -> WorkerStatus:
        """Determine worker status based on stats and thresholds."""
        last_seen = worker_stats.update_ns or current_time_ns
        stale_threshold_ns = self.stale_threshold * NANOS_PER_SECOND

        if current_time_ns - last_seen > stale_threshold_ns:
            return WorkerStatus.STALE

        if worker_stats.tasks.total == 0:
            return WorkerStatus.IDLE

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

        return WorkerStatus.HEALTHY

    def process_worker_data(
        self, worker_id: str, worker_stats: WorkerStats
    ) -> WorkerData:
        """Process a single worker's data into display format."""
        current_time = time.time_ns()
        status = self.get_worker_status(worker_stats, current_time)
        io_read, io_write = self.extract_io_data(worker_stats.health)

        return WorkerData(
            worker_id=worker_id,
            status=status,
            in_progress=worker_stats.tasks.in_progress,
            completed=worker_stats.tasks.completed,
            failed=worker_stats.tasks.failed,
            cpu_usage=worker_stats.health.cpu_usage if worker_stats.health else None,
            memory_bytes=worker_stats.health.memory_usage
            if worker_stats.health
            else None,
            io_read_bytes=io_read,
            io_write_bytes=io_write,
        )


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

    COLUMNS = ["Worker ID", "Status", "Active", "Completed", "Failed", "CPU", "Memory", "Read", "Write"]  # fmt: skip
    REVERSE_SORT_COLUMNS = {2, 3, 4, 5}  # Active, Completed, Failed, CPU

    def __init__(self) -> None:
        super().__init__()
        self.data_table: DataTable | None = None
        self._sort_column = 0
        self._sort_reverse = False
        self._worker_row_keys: dict[str, RowKey] = {}
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

        for col in self.COLUMNS:
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
            self._sort_reverse = event.column_index in self.REVERSE_SORT_COLUMNS

        current_data = getattr(self, "_last_data", [])
        if current_data:
            self.update_workers(current_data)

    @staticmethod
    def _format_memory(memory_bytes: int | None) -> str:
        """Format memory usage."""
        return format_bytes(memory_bytes) if memory_bytes is not None else "N/A"

    @staticmethod
    def _format_cpu(cpu_usage: float | None) -> str:
        """Format CPU usage percentage."""
        return f"{cpu_usage:.1f}%" if cpu_usage is not None else "N/A"

    def _format_worker_row(self, worker: WorkerData) -> list[Text]:
        """Format worker data into table row cells."""
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
            Text(self._format_cpu(worker.cpu_usage), justify="right"),
            Text(self._format_memory(worker.memory_bytes), justify="right"),
            Text(format_bytes(worker.io_read_bytes), justify="right"),
            Text(format_bytes(worker.io_write_bytes), justify="right"),
        ]

    def _update_single_row(self, worker_data: WorkerData, row_key: RowKey) -> bool:
        """Update a single row's cells."""
        if not self.data_table:
            return False

        row_cells = self._format_worker_row(worker_data)
        cells_updated = 0

        for col_name, cell_value in zip(self.COLUMNS, row_cells, strict=True):
            try:
                self.data_table.update_cell(
                    row_key, self._column_keys[col_name], cell_value, update_width=True
                )
                cells_updated += 1
            except Exception as e:
                _logger.error(
                    "Error updating cell %s for worker %s: %r",
                    col_name,
                    worker_data.worker_id,
                    e,
                )

        return cells_updated > 0

    def update_single_worker(self, worker_data: WorkerData) -> None:
        """Update a single worker's row."""
        if not self.data_table or not self.data_table.is_mounted:
            return

        if not self._columns_initialized:
            self._initialize_columns()

        worker_id = worker_data.worker_id
        row_cells = self._format_worker_row(worker_data)

        if worker_id in self._worker_row_keys:
            row_key = self._worker_row_keys[worker_id]
            try:
                self.data_table.get_row(row_key)
                if self._update_single_row(worker_data, row_key):
                    self.data_table.refresh()
            except Exception:
                # Row doesn't exist, add as new
                row_key = self.data_table.add_row(*row_cells)
                self._worker_row_keys[worker_id] = row_key
                self.data_table.refresh()
        else:
            # Add new worker row
            row_key = self.data_table.add_row(*row_cells)
            self._worker_row_keys[worker_id] = row_key
            self.data_table.refresh()

    def remove_worker(self, worker_id: str) -> None:
        """Remove a worker row from the table."""
        if not self.data_table or worker_id not in self._worker_row_keys:
            return

        row_key = self._worker_row_keys[worker_id]
        with contextlib.suppress(Exception):
            self.data_table.remove_row(row_key)
        del self._worker_row_keys[worker_id]

    def _get_sort_key(self, column_index: int):
        """Get sort key function for a column."""
        sort_functions = [
            lambda w: w.worker_id,
            lambda w: w.status.value,
            lambda w: w.in_progress,
            lambda w: w.completed,
            lambda w: w.failed,
            lambda w: w.cpu_usage or 0,
            lambda w: w.memory_bytes or 0,
            lambda w: w.io_read_bytes,
            lambda w: w.io_write_bytes,
        ]
        return sort_functions[column_index]

    def update_workers(self, workers_data: list[WorkerData]) -> None:
        """Update workers with full rebuild."""
        if not self.data_table:
            return

        if not self._columns_initialized:
            self._initialize_columns()

        self._last_data = workers_data
        self.data_table.clear()
        self._worker_row_keys.clear()

        if workers_data:
            workers_data = sorted(
                workers_data,
                key=self._get_sort_key(self._sort_column),
                reverse=self._sort_reverse,
            )

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
        self.table_widget: WorkerStatusTable | None = None
        self.border_title = "Worker Status"
        self._processor = WorkerDataProcessor(
            stale_threshold, error_rate_threshold, high_cpu_threshold
        )

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
                self.table_widget = WorkerStatusTable()
                yield self.table_widget

    def on_worker_stats_update(self, worker_id: str, worker_stats: WorkerStats) -> None:
        """Handle individual worker updates."""
        self.worker_stats[worker_id] = worker_stats
        worker_data = self._processor.process_worker_data(worker_id, worker_stats)

        if self.table_widget:
            self.table_widget.update_single_worker(worker_data)

        self._update_summary()

    def _process_all_workers(self) -> tuple[list[WorkerData], WorkerStatusSummary]:
        """Process all workers and generate summary."""
        workers_data = []
        summary = WorkerStatusSummary()

        for worker_id, worker_stats in sorted(self.worker_stats.items()):
            worker_data = self._processor.process_worker_data(worker_id, worker_stats)
            workers_data.append(worker_data)

            # Update summary counts
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

    def _update_summary(self) -> None:
        """Update summary from all current workers."""
        if not self.worker_stats:
            summary = WorkerStatusSummary()
        else:
            _, summary = self._process_all_workers()

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

    def _refresh_display(self) -> None:
        """Full refresh display."""
        if not self.worker_stats:
            self._update_summary()
            if self.table_widget:
                self.table_widget.clear_workers()
            return

        workers_data, _ = self._process_all_workers()
        self._update_summary()

        if self.table_widget:
            self.table_widget.update_workers(workers_data)

    def clear_workers(self) -> None:
        """Clear all worker data."""
        self.worker_stats.clear()
        self._refresh_display()

    def get_worker_count(self) -> int:
        """Get the current number of workers."""
        return len(self.worker_stats)

    def get_summary(self) -> WorkerStatusSummary:
        """Get the current worker status summary."""
        if not self.worker_stats:
            return WorkerStatusSummary()
        _, summary = self._process_all_workers()
        return summary
