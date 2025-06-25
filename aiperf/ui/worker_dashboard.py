# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import time
from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import Label

from aiperf.common.config import ServiceConfig
from aiperf.common.enums import ServiceType, Topic
from aiperf.common.hooks import AIPerfLifecycleMixin, aiperf_task, on_init
from aiperf.common.models.messages import WorkerHealthMessage
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.ui.widgets import DashboardFormatter, StatusIndicator

logger = logging.getLogger(__name__)


class WorkerStatusCard(Container):
    """Individual worker status card displaying health metrics."""

    DEFAULT_CSS = """
    WorkerStatusCard {
        border: solid $accent;
        border-title-color: $accent;
        border-title-background: $surface;
        height: 2;
        margin: 0 1 1 0;
        min-width: 50;
        max-width: 100;
        layout: horizontal;
    }

    WorkerStatusCard StatusIndicator {
        height: 1;
        margin: 0;
        padding: 0 1;
    }

    WorkerStatusCard ProgressBar {
        height: 1;
        margin: 0 1;
    }

    .worker-healthy {
        border: solid green;
        border-title-color: green;
    }

    .worker-warning {
        border: solid yellow;
        border-title-color: yellow;
    }

    .worker-error {
        border: solid red;
        border-title-color: red;
    }

    .worker-stale {
        border: solid dim;
        border-title-color: dim;
    }
    """

    def __init__(self, worker_id: str) -> None:
        super().__init__()
        self.worker_id = worker_id
        self.border_title = f"Worker: {worker_id}"
        self.health_message: WorkerHealthMessage | None = None
        self.last_update_time = time.time()

    def compose(self) -> ComposeResult:
        """Compose the worker status card layout."""
        yield StatusIndicator("Status", "Unknown", show_dot=True, id="status")
        yield StatusIndicator("Tasks", "0 / 0", show_dot=False, id="tasks")
        yield StatusIndicator("CPU", "0.0%", show_dot=False, id="cpu")
        yield StatusIndicator("Memory", "0.0 MiB", show_dot=False, id="memory")
        yield StatusIndicator("Uptime", "--", show_dot=False, id="uptime")
        yield StatusIndicator("PID", "--", show_dot=False, id="pid")
        yield StatusIndicator("Errors", "0", show_dot=False, id="errors")

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
                status_class = "error"
                card_class = "worker-error"
            elif health_message.cpu_usage > 90:  # High CPU usage
                status_text = "High Load"
                status_class = "status-processing"
                card_class = "worker-warning"
            elif health_message.total_tasks == 0:  # No tasks processed
                status_text = "Idle"
                status_class = "status-idle"
                card_class = "worker-healthy"
            else:
                status_text = "Healthy"
                status_class = "status-complete"
                card_class = "worker-healthy"

            # Update CSS class
            self.remove_class(
                "worker-healthy", "worker-warning", "worker-error", "worker-stale"
            )
            self.add_class(card_class)

            # Update status indicators
            self.query_one("#status", StatusIndicator).update_value(
                status_text, status_class
            )

            self.query_one("#tasks", StatusIndicator).update_value(
                f"{health_message.completed_tasks} / {health_message.total_tasks}"
            )

            self.query_one("#cpu", StatusIndicator).update_value(
                f"{health_message.cpu_usage:.1f}%"
            )

            self.query_one("#memory", StatusIndicator).update_value(
                f"{health_message.memory_usage:.1f} MiB"
            )

            self.query_one("#uptime", StatusIndicator).update_value(
                DashboardFormatter.format_duration(health_message.uptime)
            )

            self.query_one("#pid", StatusIndicator).update_value(
                str(health_message.pid) if health_message.pid else "--"
            )

            self.query_one("#errors", StatusIndicator).update_value(
                str(health_message.failed_tasks)
            )

        except Exception as e:
            logger.error(f"Error updating worker {self.worker_id} health: {e}")

    def check_stale(self, current_time: float, stale_threshold: float = 30.0) -> None:
        """Check if worker data is stale and update styling accordingly."""
        if (
            current_time - self.last_update_time <= stale_threshold
            or not self.is_mounted
        ):
            return

        self.remove_class("worker-healthy", "worker-warning", "worker-error")
        self.add_class("worker-stale")
        try:
            self.query_one("#status", StatusIndicator).update_value(
                "Stale", "status-idle"
            )
        except Exception as e:
            logger.error(
                f"Error updating stale status for worker {self.worker_id}: {e}"
            )


class WorkerDashboard(Container):
    """Dashboard displaying the status of all workers."""

    DEFAULT_CSS = """
    WorkerDashboard {
        border: solid $primary;
        border-title-color: $primary;
        border-title-background: $surface;
        height: 100%;
        layout: vertical;
    }

    #worker-summary {
        height: 3;
        margin: 0 1 1 1;
        layout: horizontal;
    }

    #workers-scroll {
        height: 1fr;
        margin: 0 1;
    }

    #workers-grid {
        height: auto;
        layout: horizontal;
    }
    """

    border_title = "Worker Status Monitor"

    def __init__(self) -> None:
        super().__init__()
        self.worker_cards: dict[str, WorkerStatusCard] = {}
        self.worker_health_data: dict[str, WorkerHealthMessage] = {}
        self.total_workers = 0
        self.healthy_workers = 0
        self.warning_workers = 0
        self.error_workers = 0
        self.stale_workers = 0

    def compose(self) -> ComposeResult:
        """Compose the worker dashboard layout."""
        yield Container(
            StatusIndicator("Total Workers", "0", show_dot=False, id="total-workers"),
            StatusIndicator("Healthy", "0", show_dot=False, id="healthy-workers"),
            StatusIndicator("Issues", "0", show_dot=False, id="issue-workers"),
            id="worker-summary",
        )

        yield ScrollableContainer(
            Horizontal(
                Label("No workers detected", id="no-workers-label"), id="workers-grid"
            ),
            id="workers-scroll",
        )

    def update_worker_health(self, health_message: WorkerHealthMessage) -> None:
        """Update a specific worker's health status."""
        worker_id = health_message.service_id
        self.worker_health_data[worker_id] = health_message

        if worker_id not in self.worker_cards:
            self._add_worker_card(worker_id)

        # Update the specific worker card
        if worker_id in self.worker_cards:
            self.worker_cards[worker_id].update_health(health_message)

        # Update summary statistics
        self._update_summary()

    def _add_worker_card(self, worker_id: str) -> None:
        """Add a new worker card to the dashboard."""
        if not self.is_mounted:
            return

        try:
            # Remove "no workers" label if it exists
            try:
                no_workers_label = self.query_one("#no-workers-label")
                no_workers_label.remove()
            except Exception:
                pass  # Label might not exist

            # Create and add new worker card
            worker_card = WorkerStatusCard(worker_id)
            self.worker_cards[worker_id] = worker_card

            workers_grid = self.query_one("#workers-grid")
            workers_grid.mount(worker_card)

        except Exception as e:
            logger.error(f"Error adding worker card for {worker_id}: {e}")

    def _update_summary(self) -> None:
        """Update the summary statistics."""
        if not self.is_mounted:
            return

        try:
            current_time = time.time()
            self.total_workers = len(self.worker_cards)
            self.healthy_workers = 0
            self.warning_workers = 0
            self.error_workers = 0
            self.stale_workers = 0

            # Check each worker and update stale status
            for worker_card in self.worker_cards.values():
                worker_card.check_stale(current_time)

                if worker_card.health_message:
                    health = worker_card.health_message
                    time_since_update = current_time - worker_card.last_update_time

                    if time_since_update > 30:  # Stale data
                        self.stale_workers += 1
                    elif (
                        health.failed_tasks / max(health.total_tasks, 1) > 0.1
                    ):  # High error rate
                        self.error_workers += 1
                    elif health.cpu_usage > 90:  # High CPU
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

        except Exception as e:
            logger.error(f"Error updating summary: {e}")

    @aiperf_task
    async def _periodic_update_task(self) -> None:
        """Periodic task to update stale worker status."""
        import asyncio

        while True:
            try:
                self._update_summary()
                await asyncio.sleep(10)  # Update every 10 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic update task: {e}")
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
            logger.debug(f"Received worker health message from {message.service_id}")

            # Store the health data
            self.worker_health_data[message.service_id] = message

            # Update the dashboard if it exists
            if self.worker_dashboard:
                self.worker_dashboard.update_worker_health(message)

        except Exception as e:
            logger.error(f"Error handling worker health message: {e}")

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
            age = current_time - (health_msg.timestamp_ns / 1e9)

            if age > 30:  # Stale data (30 seconds)
                summary["stale"] += 1
            elif (
                health_msg.failed_tasks / max(health_msg.total_tasks, 1) > 0.1
            ):  # High error rate
                summary["error"] += 1
            elif health_msg.cpu_usage > 90:  # High CPU
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
        logger.debug("Initializing worker health service")

        # Subscribe to worker health messages
        try:
            await self.sub_client.subscribe(
                Topic.WORKER_HEALTH, self._on_worker_health_message
            )
            logger.debug("Subscribed to WORKER_HEALTH topic")
        except Exception as e:
            logger.error(f"Failed to subscribe to WORKER_HEALTH topic: {e}")

    async def _on_worker_health_message(self, message: WorkerHealthMessage) -> None:
        """Handle incoming worker health messages."""
        try:
            logger.debug(f"Received worker health message from {message.service_id}")

            # Store the health data
            self.worker_health_data[message.service_id] = message

            # Call the callback if provided
            if self.health_callback:
                self.health_callback(message)

        except Exception as e:
            logger.error(f"Error handling worker health message: {e}")

    def set_health_callback(
        self, callback: Callable[[WorkerHealthMessage], None]
    ) -> None:
        """Set the callback for worker health updates."""
        self.health_callback = callback
