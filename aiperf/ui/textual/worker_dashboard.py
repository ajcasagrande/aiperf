# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import contextlib
import time
from typing import NamedTuple

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import DataTable, Label, Static

from aiperf.common.enums import CaseInsensitiveStrEnum, CreditPhase
from aiperf.common.messages import WorkerHealthMessage
from aiperf.common.models import AIPerfBaseModel, IOCounters, WorkerPhaseTaskStats
from aiperf.common.utils import format_bytes


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
    cpu_usage: float
    memory_mb: float
    io_read_bytes: int
    io_write_bytes: int


class WorkerStatusTable(Widget):
    DEFAULT_CSS = """
    WorkerStatusTable {
        height: 1fr;
        &:focus {
            background-tint: $primary 100%;
        }
    }
    DataTable {
        height: 1fr;
        &:focus {
            background-tint: $primary 100%;
        }
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.data_table: DataTable | None = None
        self._sort_column = 5  # CPU column
        self._sort_reverse = True

    def compose(self) -> ComposeResult:
        self.data_table = DataTable(cursor_type="row", show_cursor=False)
        yield self.data_table

    def on_mount(self) -> None:
        if self.data_table:
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
                self.data_table.add_column(col)

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        if not self.data_table:
            return

        if event.column_index == self._sort_column:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_column = event.column_index
            # Active, Completed, Failed, CPU
            self._sort_reverse = event.column_index in [2, 3, 4, 5]

        # Simple rebuild on sort
        current_data = getattr(self, "_last_data", [])
        if current_data:
            self.update_workers(current_data)

    def update_workers(self, workers_data: list[WorkerData]) -> None:
        if not self.data_table:
            return

        self._last_data = workers_data
        self.data_table.clear()

        # Sort data
        if workers_data:
            sort_key_funcs = [
                lambda w: w.worker_id,
                lambda w: w.status.value,
                lambda w: w.in_progress,
                lambda w: w.completed,
                lambda w: w.failed,
                lambda w: w.cpu_usage,
                lambda w: w.memory_mb,
                lambda w: w.io_read_bytes,
                lambda w: w.io_write_bytes,
            ]
            workers_data = sorted(
                workers_data,
                key=sort_key_funcs[self._sort_column],
                reverse=self._sort_reverse,
            )

        # Add rows
        for worker in workers_data:
            memory_display = (
                f"{worker.memory_mb / 1024:.1f} GB"
                if worker.memory_mb >= 1024
                else f"{worker.memory_mb:.0f} MB"
            )

            row = [
                Text(worker.worker_id, style="bold cyan"),
                Text(
                    worker.status.value.replace("_", " ").title(),
                    style=worker.status.style,
                ),
                f"{worker.in_progress:,}",
                f"{worker.completed:,}",
                f"{worker.failed:,}",
                f"{worker.cpu_usage:.1f}%",
                memory_display,
                format_bytes(worker.io_read_bytes),
                format_bytes(worker.io_write_bytes),
            ]
            self.data_table.add_row(*row)


class WorkerDashboard(Container):
    DEFAULT_CSS = """
    WorkerDashboard {
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

    .summary-item { margin: 0 1; }
    .summary-title { text-style: bold; }
    .summary-healthy { color: $success; text-style: bold; }
    .summary-warning { color: $warning; text-style: bold; }
    .summary-error { color: $error; text-style: bold; }
    .summary-idle { color: $text-muted; }
    .summary-stale { color: $surface-darken-1; }

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
                if self.worker_health:
                    self.table_widget = WorkerStatusTable()
                    yield self.table_widget
                else:
                    yield Static("No worker data available", id="no-workers-message")

    def update_worker_health(self, message: WorkerHealthMessage) -> None:
        self.worker_health[message.service_id] = message
        self.worker_last_seen[message.service_id] = time.time()
        self._refresh_display()

    def update_worker_last_seen(
        self, worker_id: str, timestamp: float | None = None
    ) -> None:
        self.worker_last_seen[worker_id] = timestamp or time.time()
        self._refresh_display()

    def _refresh_display(self) -> None:
        if not self.worker_health:
            self._update_summary(WorkerStatusSummary())
            return

        workers_data, summary = self._process_worker_data()
        self._update_summary(summary)

        if self.table_widget:
            self.table_widget.update_workers(workers_data)
        elif workers_data:
            self._create_table()

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

    def _create_table(self) -> None:
        table_section = self.query_one("#table-section")

        # Remove no workers message
        with contextlib.suppress(Exception):
            table_section.query_one("#no-workers-message").remove()

        # Create table
        self.table_widget = WorkerStatusTable()
        table_section.mount(self.table_widget)

        # Update with data
        workers_data, _ = self._process_worker_data()
        self.table_widget.update_workers(workers_data)

    def _process_worker_data(self) -> tuple[list[WorkerData], WorkerStatusSummary]:
        current_time = time.time()
        workers_data = []
        summary = WorkerStatusSummary()

        for service_id, health in sorted(self.worker_health.items()):
            last_seen = self.worker_last_seen.get(service_id, current_time)

            # Get task stats
            task_stats = health.task_stats.get(
                CreditPhase.PROFILING, WorkerPhaseTaskStats()
            )

            # Determine status
            status = self._get_worker_status(
                health, task_stats, last_seen, current_time
            )

            # Update summary
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

            # Get I/O data
            io_read = io_write = 0
            if health.process.io_counters and isinstance(
                health.process.io_counters, IOCounters
            ):
                io_read = health.process.io_counters.read_chars or 0
                io_write = health.process.io_counters.write_chars or 0

            worker_data = WorkerData(
                worker_id=service_id,
                status=status,
                in_progress=task_stats.in_progress,
                completed=task_stats.completed,
                failed=task_stats.failed,
                cpu_usage=health.process.cpu_usage,
                memory_mb=health.process.memory_usage,
                io_read_bytes=io_read,
                io_write_bytes=io_write,
            )
            workers_data.append(worker_data)

        return workers_data, summary

    def _get_worker_status(
        self,
        health: WorkerHealthMessage,
        task_stats: WorkerPhaseTaskStats,
        last_seen: float,
        current_time: float,
    ) -> WorkerStatus:
        if current_time - last_seen > self.stale_threshold:
            return WorkerStatus.STALE

        error_rate = task_stats.failed / task_stats.total if task_stats.total > 0 else 0
        if error_rate > self.error_rate_threshold:
            return WorkerStatus.ERROR

        if health.process.cpu_usage > self.high_cpu_threshold:
            return WorkerStatus.HIGH_LOAD

        if task_stats.total == 0:
            return WorkerStatus.IDLE

        return WorkerStatus.HEALTHY

    def clear_workers(self) -> None:
        self.worker_health.clear()
        self.worker_last_seen.clear()
        self._refresh_display()

    def get_worker_count(self) -> int:
        return len(self.worker_health)

    def get_summary(self) -> WorkerStatusSummary:
        if not self.worker_health:
            return WorkerStatusSummary()
        _, summary = self._process_worker_data()
        return summary
