# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time
from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer, Vertical
from textual.css.query import NoMatches
from textual.widget import Widget
from textual.widgets import Label

from aiperf.common.config import ServiceConfig
from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.enums import ServiceType
from aiperf.common.hooks import on_init
from aiperf.common.messages import WorkerHealthMessage
from aiperf.common.mixins import AIPerfLifecycleMixin, AIPerfLoggerMixin
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.ui.textual.widgets import StatusIndicator


class WorkerRow(Widget, AIPerfLoggerMixin):
    """A single row in the worker table showing worker name and metrics."""

    DEFAULT_CSS = """
    WorkerRow {
        height: 1;
        layout: grid;
        grid-size: 7;
        grid-columns: 3fr 2fr 1fr 1fr 1fr 1fr 1fr;
        margin: 0;
        padding: 0 1 0 0;
    }

    WorkerRow:hover {
        background: $surface-lighten-1;
    }

    WorkerRow > Label {
        margin: 0;
        padding: 0;
        text-align: left;
        overflow: hidden;
    }

    .worker-name {
        text-style: bold;
    }

    .status-healthy {
        color: $success;
        text-style: bold;
    }

    .status-warning {
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

    def __init__(self, worker_id: str) -> None:
        super().__init__()
        self.worker_id = worker_id
        self.health_message: WorkerHealthMessage | None = None
        self.last_update_time = time.time()

    def compose(self) -> ComposeResult:
        """Compose the worker row with name and metrics."""
        yield Label(self.worker_id, classes="worker-name", id="worker-name")
        yield Label("Unknown", id="status")
        yield Label("0", id="in-progress-tasks")
        yield Label("0", id="completed-tasks")
        yield Label("0", id="failed-tasks")
        yield Label("0.0%", id="cpu")
        yield Label("0.0 MB", id="memory")

    def update_health(self, health_message: WorkerHealthMessage) -> None:
        """Update the worker health display."""
        self.health_message = health_message
        self.last_update_time = time.time()

        if not self.is_mounted:
            return

        try:
            # Calculate worker status
            error_rate = (
                health_message.failed_tasks / health_message.total_tasks
                if health_message.total_tasks > 0
                else 0
            )

            # Determine overall status and styling
            if error_rate > 0.1:  # More than 10% error rate
                status_text = "Error"
                status_class = "status-error"
            elif health_message.process.cpu_usage > 75:  # High CPU usage
                status_text = "High Load"
                status_class = "status-warning"
            elif health_message.total_tasks == 0:  # No tasks processed
                status_text = "Idle"
                status_class = "status-idle"
            else:
                status_text = "Healthy"
                status_class = "status-healthy"

            # Update labels
            self.query_one("#status", Label).update(status_text)
            self.query_one("#status", Label).remove_class(
                "status-healthy",
                "status-warning",
                "status-error",
                "status-idle",
                "status-stale",
            )
            self.query_one("#status", Label).add_class(status_class)

            self.query_one("#in-progress-tasks", Label).update(
                f"{health_message.in_progress_tasks}"
            )
            self.query_one("#completed-tasks", Label).update(
                f"{health_message.completed_tasks}"
            )
            self.query_one("#failed-tasks", Label).update(
                f"{health_message.failed_tasks}"
            )

            self.query_one("#cpu", Label).update(
                f"{health_message.process.cpu_usage:.1f}%"
            )

            # Format memory in MB for cleaner display
            memory_mb = health_message.process.memory_usage
            if memory_mb >= 1024:
                memory_display = f"{memory_mb / 1024:.1f} GB"
            else:
                memory_display = f"{memory_mb:.0f} MB"

            self.query_one("#memory", Label).update(memory_display)

        except NoMatches:
            pass
        except Exception as e:
            self.error(f"Error updating worker {self.worker_id} health: {e}")

    def check_stale(self, current_time: float, stale_threshold: float = 30.0) -> None:
        """Check if worker data is stale and update styling accordingly."""
        if (
            current_time - self.last_update_time <= stale_threshold
            or not self.is_mounted
        ):
            return

        try:
            self.query_one("#status", Label).update("Stale")
            self.query_one("#status", Label).remove_class(
                "status-healthy", "status-warning", "status-error", "status-idle"
            )
            self.query_one("#status", Label).add_class("status-stale")
        except NoMatches:
            pass
        except Exception as e:
            self.error(f"Error updating stale status for worker {self.worker_id}: {e}")


class WorkerTable(Widget, AIPerfLoggerMixin):
    """Table widget for displaying worker information."""

    DEFAULT_CSS = """
    WorkerTable {
        height: auto;
        layout: vertical;
        margin: 0;
        min-height: 0;
    }

    #table-header {
        height: 1;

        background: $surface-lighten-1;
        border-bottom: round $primary;
        padding: 0 0;
        margin: 0 0 0 0;
    }

    #table-header Label {
        text-style: bold;
        text-align: left;
        margin: 0;
        padding: 0;
    }

    #table-body {
        height: auto;
        layout: vertical;
        margin: 0;
        min-height: 0;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.worker_rows: dict[str, WorkerRow] = {}
        self.pending_workers: list[str] = []

    def compose(self) -> ComposeResult:
        """Compose the table with header and body."""
        yield Container(
            Label("Worker ID"),
            Label("Status"),
            Label("In Progress"),
            Label("Completed"),
            Label("Failed"),
            Label("CPU"),
            Label("Memory"),
            id="table-header",
        )
        yield Vertical(id="table-body")

    def on_mount(self) -> None:
        """Handle mounting and add any pending workers."""
        # Add any workers that were queued before mounting
        for worker_id in self.pending_workers:
            self._mount_worker(worker_id)
        self.pending_workers.clear()

    def add_worker(self, worker_id: str) -> None:
        """Add a new worker row to the table."""
        if worker_id not in self.worker_rows:
            worker_row = WorkerRow(worker_id)
            self.worker_rows[worker_id] = worker_row

            if self.is_mounted:
                self._mount_worker(worker_id)
            else:
                # Queue for later mounting
                self.pending_workers.append(worker_id)

    def _mount_worker(self, worker_id: str) -> None:
        """Mount a worker row to the table body."""
        if worker_id in self.worker_rows:
            try:
                table_body = self.query_one("#table-body")
                table_body.mount(self.worker_rows[worker_id])
            except Exception as e:
                self.error(f"Error mounting worker {worker_id}: {e}")

    def update_worker(
        self, worker_id: str, health_message: WorkerHealthMessage
    ) -> None:
        """Update a worker's information."""
        if worker_id not in self.worker_rows:
            self.add_worker(worker_id)

        self.worker_rows[worker_id].update_health(health_message)

    def check_stale_workers(self, current_time: float) -> None:
        """Check all workers for stale data."""
        for worker_row in self.worker_rows.values():
            worker_row.check_stale(current_time)


class WorkerDashboard(Container, AIPerfLoggerMixin):
    """Dashboard displaying the status of all workers in a table format."""

    DEFAULT_CSS = """
    WorkerDashboard {
        border: round $primary;
        border-title-color: $primary;
        border-title-background: $surface;
        height: 1fr;
        layout: vertical;
    }

    #worker-summary {
        height: 3;
        margin: 0;
        layout: horizontal;
    }

    #workers-scroll {
        height: 1fr;
        margin: 0;
        scrollbar-gutter: stable;
        overflow-y: auto;
        max-height: 1fr;
    }

    #workers-container {
        height: auto;
        layout: vertical;
        min-height: 0;
    }
    """

    border_title = "Worker Monitor"

    def __init__(self) -> None:
        super().__init__()
        self.worker_table: WorkerTable | None = None
        self.worker_health_data: dict[str, WorkerHealthMessage] = {}
        self.total_workers = 0
        self.healthy_workers = 0
        self.warning_workers = 0
        self.error_workers = 0
        self.stale_workers = 0

    def compose(self) -> ComposeResult:
        """Compose the simplified worker dashboard layout."""
        yield Container(
            StatusIndicator("Total", "0", show_dot=False, id="total-workers"),
            StatusIndicator("Healthy", "0", show_dot=False, id="healthy-workers"),
            StatusIndicator("Issues", "0", show_dot=False, id="issue-workers"),
            id="worker-summary",
        )

        yield ScrollableContainer(
            Vertical(
                Label("No workers detected", id="no-workers-label"),
                id="workers-container",
            ),
            id="workers-scroll",
        )

    def update_worker_health(self, health_message: WorkerHealthMessage) -> None:
        """Update a specific worker's health status."""
        worker_id = health_message.service_id
        self.worker_health_data[worker_id] = health_message

        if not self.worker_table:
            self._initialize_table()

        if self.worker_table:
            self.worker_table.update_worker(worker_id, health_message)

        # Update summary statistics
        self._update_summary()

    def _initialize_table(self) -> None:
        """Initialize the worker table."""
        if not self.is_mounted:
            return

        try:
            # Remove "no workers" label if it exists
            try:
                no_workers_label = self.query_one("#no-workers-label")
                no_workers_label.remove()
            except Exception:
                pass  # Label might not exist

            # Create and add worker table
            self.worker_table = WorkerTable()
            workers_container = self.query_one("#workers-container")
            workers_container.mount(self.worker_table)

        except Exception as e:
            self.exception(
                f"Error initializing worker table: {e.__class__.__name__}: {e}"
            )

    def _update_summary(self) -> None:
        """Update the summary statistics."""
        if not self.is_mounted:
            return

        try:
            current_time = time.time()
            self.total_workers = len(self.worker_health_data)
            self.healthy_workers = 0
            self.warning_workers = 0
            self.error_workers = 0
            self.stale_workers = 0

            # Check each worker and update stale status
            if self.worker_table:
                self.worker_table.check_stale_workers(current_time)

            for worker_id, health_message in self.worker_health_data.items():
                if self.worker_table and worker_id in self.worker_table.worker_rows:
                    worker_row = self.worker_table.worker_rows[worker_id]
                    time_since_update = current_time - worker_row.last_update_time

                    if time_since_update > 30:  # Stale data
                        self.stale_workers += 1
                    elif (
                        health_message.failed_tasks / max(health_message.total_tasks, 1)
                        > 0.1
                    ):  # High error rate
                        self.error_workers += 1
                    elif health_message.process.cpu_usage > 75:  # High CPU
                        self.warning_workers += 1
                    else:
                        self.healthy_workers += 1

            # Update summary indicators
            self.query_one("#total-workers", StatusIndicator).update_value(
                str(self.total_workers)
            )
            self.query_one("#healthy-workers", StatusIndicator).update_value(
                str(self.healthy_workers)
            )

            issue_count = self.warning_workers + self.error_workers + self.stale_workers
            self.query_one("#issue-workers", StatusIndicator).update_value(
                str(issue_count)
            )
        except NoMatches:
            pass
        except Exception as e:
            self.error(f"Error updating summary: {e.__class__.__name__}: {e}")

    async def _periodic_update_task(self) -> None:
        """Periodic task to update stale worker status."""
        import asyncio

        while True:
            try:
                self._update_summary()
                await asyncio.sleep(1)  # Update every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.error(f"Error in periodic update task: {e}")
                await asyncio.sleep(10)


class WorkerDashboardMixin(AIPerfLifecycleMixin):
    """Mixin that provides worker health monitoring functionality to UI components."""

    def __init__(self) -> None:
        super().__init__()
        self.worker_dashboard: WorkerDashboard | None = None
        self.worker_health_data: dict[str, WorkerHealthMessage] = {}

    def get_worker_dashboard(self) -> WorkerDashboard:
        """Get or create the worker dashboard widget."""
        if not self.worker_dashboard:
            self.worker_dashboard = WorkerDashboard()
        return self.worker_dashboard

    def update_worker_health(self, message: WorkerHealthMessage) -> None:
        """Handle incoming worker health messages."""
        try:
            self.debug(f"Received worker health message from {message.service_id}")

            # Store the health data
            self.worker_health_data[message.service_id] = message

            # Update the dashboard if it exists
            if self.worker_dashboard:
                self.worker_dashboard.update_worker_health(message)

        except Exception as e:
            self.error(f"Error handling worker health message: {e}")

    def get_worker_health_summary(self) -> dict[str, int]:
        """Get a summary of worker health status."""
        current_time = time.time()
        summary = {
            "total": len(self.worker_health_data),
            "healthy": 0,
            "warning": 0,
            "error": 0,
            "stale": 0,
        }

        for _, health_msg in self.worker_health_data.items():
            age = current_time - (health_msg.request_ns / NANOS_PER_SECOND)

            if age > 30:  # Stale data (30 seconds)
                summary["stale"] += 1
            elif (
                health_msg.failed_tasks / max(health_msg.total_tasks, 1) > 0.1
            ):  # High error rate
                summary["error"] += 1
            elif health_msg.process.cpu_usage > 75:  # High CPU
                summary["warning"] += 1
            else:
                summary["healthy"] += 1

        return summary


class WorkerHealthService(BaseComponentService):
    """Service that subscribes to worker health messages and provides callbacks for UI updates."""

    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
        health_callback: Callable[[WorkerHealthMessage], None] | None = None,
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.health_callback = health_callback
        self.worker_health_data: dict[str, WorkerHealthMessage] = {}

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.SYSTEM_CONTROLLER  # Use existing service type

    @on_init
    async def _initialize(self) -> None:
        """Initialize worker health service."""
        self.debug("Initializing worker health service")

        # Subscribe to worker health messages
        try:
            await self.sub_client.subscribe(self._on_worker_health_message)
            self.debug("Subscribed to WORKER_HEALTH topic")
        except Exception as e:
            self.error(f"Failed to subscribe to WORKER_HEALTH topic: {e}")

    async def _on_worker_health_message(self, message: WorkerHealthMessage) -> None:
        """Handle incoming worker health messages."""
        try:
            self.debug(f"Received worker health message from {message.service_id}")

            # Store the health data
            self.worker_health_data[message.service_id] = message

            # Call the callback if provided
            if self.health_callback:
                self.health_callback(message)

        except Exception as e:
            self.error(f"Error handling worker health message: {e}")

    def set_health_callback(
        self, callback: Callable[[WorkerHealthMessage], None]
    ) -> None:
        """Set the callback for worker health updates."""
        self.health_callback = callback
