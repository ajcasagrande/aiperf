# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import contextlib
from typing import NamedTuple

from pydantic import BaseModel, Field
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Label
from textual.widgets._data_table import ColumnKey, RowKey

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums import WorkerStatus
from aiperf.common.models import WorkerStats
from aiperf.ui.utils import format_bytes

_logger = AIPerfLogger(__name__)


WORKER_STATUS_STYLES = {
    WorkerStatus.HEALTHY: "bold #6fbc76",
    WorkerStatus.HIGH_LOAD: "bold yellow",
    WorkerStatus.ERROR: "bold red",
    WorkerStatus.IDLE: "dim",
    WorkerStatus.STALE: "dim white",
}


class WorkerStatusSummary(BaseModel):
    status_counts: dict[WorkerStatus, int] = Field(
        default_factory=lambda: {status: 0 for status in WorkerStatus},
        description="The number of workers in each status",
    )


class WorkerData(NamedTuple):
    worker_id: str
    status: WorkerStatus
    stats: WorkerStats


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
    }
    """

    COLUMNS = ["Worker ID", "Status", "In-flight", "Completed", "Failed", "CPU", "Memory", "Read", "Write"]  # fmt: skip
    REVERSE_SORT_COLUMNS = {2, 3, 4, 5}  # In-flight, Completed, Failed, CPU

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
        self.data_table.fixed_columns = 0

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

    def _format_worker_row(self, worker_stats: WorkerStats) -> list[Text]:
        """Format worker data into table row cells."""
        row_data = [
            Text(worker_stats.worker_id, style="bold cyan", justify="right"),
            Text(
                worker_stats.status.replace("_", " ").title(),
                style=WORKER_STATUS_STYLES[worker_stats.status],
                justify="right",
            ),
            Text(f"{worker_stats.task_stats.in_progress:,}", justify="right"),
            Text(f"{worker_stats.task_stats.completed:,}", justify="right"),
            Text(f"{worker_stats.task_stats.failed:,}", justify="right"),
        ]

        health = worker_stats.health

        if health:
            row_data.extend([
                Text(self._format_cpu(health.cpu_usage), justify="right"),
                Text(self._format_memory(health.memory_usage), justify="right"),
            ])  # fmt: skip
        else:
            row_data.extend([
                Text("N/A", justify="right"),
                Text("N/A", justify="right"),
            ])  # fmt: skip

        if health and health.io_counters:
            row_data.extend([
                Text(format_bytes(health.io_counters.read_chars), justify="right"),
                Text(format_bytes(health.io_counters.write_chars), justify="right"),
            ])  # fmt: skip
        else:
            row_data.extend([
                Text("N/A", justify="right"),
                Text("N/A", justify="right"),
            ])  # fmt: skip
        return row_data

    def _update_single_row(self, worker_stats: WorkerStats, row_key: RowKey) -> bool:
        """Update a single row's cells."""
        if not self.data_table:
            return False

        row_cells = self._format_worker_row(worker_stats)
        cells_updated = 0

        for col_name, cell_value in zip(self.COLUMNS, row_cells, strict=True):
            try:
                self.data_table.update_cell(
                    row_key, self._column_keys[col_name], cell_value, update_width=True
                )
                cells_updated += 1
            except Exception as e:
                _logger.warning(
                    f"Error updating cell {col_name} for worker {worker_stats.worker_id}: {e!r}"
                )

        return cells_updated > 0

    def update_single_worker(self, worker_stats: WorkerStats) -> None:
        """Update a single worker's row."""
        if not self.data_table or not self.data_table.is_mounted:
            return

        if not self._columns_initialized:
            self._initialize_columns()

        worker_id = worker_stats.worker_id
        row_cells = self._format_worker_row(worker_stats)

        if worker_id in self._worker_row_keys:
            row_key = self._worker_row_keys[worker_id]
            try:
                self.data_table.get_row(row_key)
                if self._update_single_row(worker_stats, row_key):
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

    def update_workers(self, workers_stats: list[WorkerStats]) -> None:
        """Update workers with full rebuild."""
        if not self.data_table:
            return

        if not self._columns_initialized:
            self._initialize_columns()

        self._last_data = workers_stats
        self.data_table.clear()
        self._worker_row_keys.clear()

        if workers_stats:
            workers_stats = sorted(
                workers_stats,
                key=self._get_sort_key(self._sort_column),
                reverse=self._sort_reverse,
            )

        for worker_stats in workers_stats:
            row_cells = self._format_worker_row(worker_stats)
            row_key = self.data_table.add_row(*row_cells)
            self._worker_row_keys[worker_stats.worker_id] = row_key


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
    .summary-high-load { color: $warning; text-style: bold; }
    .summary-error { color: $error; text-style: bold; }
    .summary-idle { color: $text-muted; }
    .summary-stale { color: $surface-darken-1; }

    #worker-dashboard-content.no-workers {
        height: 1fr;
        content-align: center middle;
        color: $warning;
        text-style: italic;
    }

    #table-section {
        height: 1fr;
        margin: 0 0 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.worker_stats: dict[str, WorkerStats] = {}
        self.table_widget: WorkerStatusTable | None = None
        self.border_title = "Worker Status"
        self.received_worker_stats = False

    def compose(self) -> ComposeResult:
        with Vertical(id="worker-dashboard-content", classes="no-workers"):
            with Horizontal(id="summary-content"):
                yield Label("Summary: ", classes="summary-item summary-title")
                for status in WorkerStatus:
                    yield Label(
                        f"0 {status.replace('_', ' ')}",
                        id=f"{status.replace('_', '-').lower()}-count",
                        classes=f"summary-item summary-{status.replace('_', '-').lower()}",
                    )
                    yield Label("•", classes="summary-item")

            with Container(id="table-section"):
                self.table_widget = WorkerStatusTable()
                yield self.table_widget

    def on_worker_stats_update(self, worker_id: str, worker_stats: WorkerStats) -> None:
        """Handle individual worker updates."""
        if not self.received_worker_stats:
            self.received_worker_stats = True
            self.query_one("#worker-dashboard-content").remove_class("no-workers")

        self.worker_stats[worker_id] = worker_stats

        if self.table_widget:
            self.table_widget.update_single_worker(worker_stats)

    def on_worker_status_summary(
        self, worker_status_summary: dict[str, WorkerStatus]
    ) -> None:
        """Handle worker status summary updates."""
        summary = WorkerStatusSummary()
        for _, worker_status in worker_status_summary.items():
            summary.status_counts[worker_status] += 1

        for status in WorkerStatus:
            with contextlib.suppress(Exception):
                self.query_one(
                    f"#{status.replace('_', '-').lower()}-count", Label
                ).update(f"{summary.status_counts[status]} {status.replace('_', ' ')}")
