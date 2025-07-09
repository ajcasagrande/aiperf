# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time
from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Label, Static

from aiperf.common.enums import CreditPhase
from aiperf.ui.base_widgets import InteractiveAIPerfWidget

if TYPE_CHECKING:
    from aiperf.common.worker_models import WorkerHealthMessage
    from aiperf.progress.progress_tracker import ProgressTracker


class WorkerCard(Static):
    """A simple card widget representing a single worker."""

    DEFAULT_CSS = """
    WorkerCard {
        border: solid #444444;
        background: #2a2a2a;
        margin: 1 0;
        padding: 1;
        height: 7;
    }

    WorkerCard.healthy {
        border: solid #00ff00;
    }

    WorkerCard.warning {
        border: solid #ffaa00;
    }

    WorkerCard.error {
        border: solid #ff0000;
    }

    WorkerCard.stale {
        border: solid #666666;
        background: #222222;
    }

    WorkerCard .header {
        height: 1;
        text-style: bold;
        color: #ffffff;
    }

    WorkerCard .status {
        height: 1;
        color: #888888;
    }

    WorkerCard .status.healthy {
        color: #00ff00;
    }

    WorkerCard .status.warning {
        color: #ffaa00;
    }

    WorkerCard .status.error {
        color: #ff0000;
    }

    WorkerCard .status.stale {
        color: #666666;
    }

    WorkerCard .metrics {
        layout: grid;
        grid-size: 3 2;
        grid-gutter: 1;
        height: 4;
    }

    WorkerCard .metric-value {
        color: #00d4aa;
        text-style: bold;
    }

    WorkerCard .metric-label {
        color: #888888;
    }
    """

    def __init__(self, worker_id: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.worker_id = worker_id
        self.health_data = None
        self.last_seen = time.time()
        self.status = "unknown"

    def compose(self) -> ComposeResult:
        """Compose the worker card."""
        with Vertical():
            # Header
            yield Label(f"Worker {self.worker_id}", classes="header")
            yield Label("Unknown", id=f"status-{self.worker_id}", classes="status")

            # Metrics
            with Horizontal(classes="metrics"):
                yield Label("0", id=f"active-{self.worker_id}", classes="metric-value")
                yield Label(
                    "0", id=f"completed-{self.worker_id}", classes="metric-value"
                )
                yield Label("0", id=f"failed-{self.worker_id}", classes="metric-value")
                yield Label("Active", classes="metric-label")
                yield Label("Completed", classes="metric-label")
                yield Label("Failed", classes="metric-label")
                yield Label("0%", id=f"cpu-{self.worker_id}", classes="metric-value")
                yield Label(
                    "0 MB", id=f"memory-{self.worker_id}", classes="metric-value"
                )
                yield Label("0 B/s", id=f"io-{self.worker_id}", classes="metric-value")
                yield Label("CPU", classes="metric-label")
                yield Label("Memory", classes="metric-label")
                yield Label("I/O", classes="metric-label")

    def on_mount(self) -> None:
        """Called when the widget is mounted."""
        if self.health_data:
            self._update_status()
            self._update_metrics()

    def update_worker_data(
        self, health_data: "WorkerHealthMessage", last_seen: float
    ) -> None:
        """Update the worker card with health data."""
        self.health_data = health_data
        self.last_seen = last_seen

        # Determine status
        current_time = time.time()
        if current_time - last_seen > 30:  # 30 seconds
            self.status = "stale"
        else:
            # Get task stats for current phase
            task_stats = health_data.task_stats.get(CreditPhase.STEADY_STATE)
            if task_stats:
                error_rate = (
                    task_stats.failed / task_stats.total if task_stats.total > 0 else 0
                )
                if error_rate > 0.1:  # More than 10% error rate
                    self.status = "error"
                elif health_data.process.cpu_usage > 75:  # High CPU
                    self.status = "warning"
                elif task_stats.total == 0:  # No tasks
                    self.status = "idle"
                else:
                    self.status = "healthy"
            else:
                self.status = "idle"

        # Update styling
        self.remove_class("healthy", "warning", "error", "stale")
        self.add_class(self.status)

        # Update content
        self._update_status()
        self._update_metrics()

    def _update_status(self) -> None:
        """Update the status display."""
        if not self.is_mounted:
            return

        try:
            status_label = self.query_one(f"#status-{self.worker_id}", Label)
        except Exception:
            return

        status_map = {
            "healthy": ("Healthy", "healthy"),
            "warning": ("High Load", "warning"),
            "error": ("Error", "error"),
            "idle": ("Idle", "idle"),
            "stale": ("Stale", "stale"),
            "unknown": ("Unknown", "unknown"),
        }

        text, css_class = status_map.get(self.status, ("Unknown", "unknown"))
        status_label.update(text)
        status_label.remove_class(
            "healthy", "warning", "error", "idle", "stale", "unknown"
        )
        status_label.add_class(css_class)

    def _update_metrics(self) -> None:
        """Update the metrics display."""
        if not self.health_data or not self.is_mounted:
            return

        try:
            # Task stats
            task_stats = self.health_data.task_stats.get(CreditPhase.STEADY_STATE)
            if task_stats:
                self.query_one(f"#active-{self.worker_id}", Label).update(
                    f"{task_stats.in_progress:,}"
                )
                self.query_one(f"#completed-{self.worker_id}", Label).update(
                    f"{task_stats.completed:,}"
                )
                self.query_one(f"#failed-{self.worker_id}", Label).update(
                    f"{task_stats.failed:,}"
                )
            else:
                self.query_one(f"#active-{self.worker_id}", Label).update("0")
                self.query_one(f"#completed-{self.worker_id}", Label).update("0")
                self.query_one(f"#failed-{self.worker_id}", Label).update("0")

            # Process stats
            process = self.health_data.process
            self.query_one(f"#cpu-{self.worker_id}", Label).update(
                f"{process.cpu_usage:.1f}%"
            )

            # Memory in MB or GB
            memory_mb = process.memory_usage
            if memory_mb >= 1024:
                memory_display = f"{memory_mb / 1024:.1f} GB"
            else:
                memory_display = f"{memory_mb:.0f} MB"
            self.query_one(f"#memory-{self.worker_id}", Label).update(memory_display)

            # I/O rate (simplified)
            io_rate = (
                (process.io_counters.read_bytes + process.io_counters.write_bytes)
                / 1024
                / 1024
            )  # MB/s approximation
            self.query_one(f"#io-{self.worker_id}", Label).update(f"{io_rate:.1f} MB/s")

        except Exception:
            # Some data might not be available
            pass

    def on_click(self, event) -> None:
        """Handle click events on the worker card."""
        self.post_message(WorkerStatusWidget.WorkerSelected(self.worker_id))


class WorkerStatusWidget(InteractiveAIPerfWidget):
    """Clean widget showing worker status and health information."""

    DEFAULT_CSS = """
    WorkerStatusWidget {
        border: solid #76b900;
        background: #1a1a1a;
        height: 100%;
    }

    WorkerStatusWidget .header {
        background: #76b900;
        color: #000000;
        text-style: bold;
        padding: 0 1;
        dock: top;
        height: 3;
    }

    WorkerStatusWidget .summary {
        background: #333333;
        border: solid #444444;
        padding: 1;
        margin: 1;
        height: 3;
    }

    WorkerStatusWidget .worker-list {
        padding: 1;
        height: 100%;
    }

    WorkerStatusWidget .controls {
        dock: bottom;
        height: 2;
        padding: 1;
    }

    WorkerStatusWidget .empty-state {
        padding: 2;
        text-align: center;
        color: #888888;
    }
    """

    class WorkerSelected(Message):
        """Message sent when a worker is selected."""

        def __init__(self, worker_id: str) -> None:
            super().__init__()
            self.worker_id = worker_id

    widget_title = "Worker Status"

    def __init__(self, progress_tracker: "ProgressTracker", **kwargs) -> None:
        super().__init__(progress_tracker, **kwargs)
        self.worker_cards = {}
        self.sort_by = "name"  # name, status, activity

    def compose(self) -> ComposeResult:
        """Compose the worker status widget."""
        with Vertical():
            # Header
            with Vertical(classes="header"):
                yield Label("Worker Status", classes="title")
                yield Label("No workers", id="worker-count")

            # Summary
            with Vertical(classes="summary"):
                yield Label("No active workers", id="worker-summary")

            # Worker list
            with Vertical(classes="worker-list", id="worker-container"):
                yield Label("No workers available", classes="empty-state")

            # Controls
            with Horizontal(classes="controls"):
                yield Button("Sort by Status", id="sort-status", variant="outline")
                yield Button("Export Data", id="export-data", variant="outline")

    def update_content(self) -> None:
        """Update the worker status display."""
        if not self.progress_tracker or not self.progress_tracker.current_profile_run:
            self._update_empty_state()
            return

        profile_run = self.progress_tracker.current_profile_run
        self._update_worker_cards(profile_run)
        self._update_summary_stats()

    def _update_empty_state(self) -> None:
        """Update when no workers are available."""
        self.query_one("#worker-count", Label).update("No workers")
        self.query_one("#worker-summary", Label).update("No active workers")

        # Clear worker cards
        container = self.query_one("#worker-container", Vertical)
        container.remove_children()
        container.mount(Label("No workers available", classes="empty-state"))

    def _update_worker_cards(self, profile_run) -> None:
        """Update worker cards with current health data."""
        container = self.query_one("#worker-container", Vertical)
        current_workers = set(profile_run.worker_health.keys())

        # Remove stale workers
        for worker_id in list(self.worker_cards.keys()):
            if worker_id not in current_workers:
                if worker_id in self.worker_cards:
                    self.worker_cards[worker_id].remove()
                    del self.worker_cards[worker_id]

        # Add or update workers
        for worker_id, health_data in profile_run.worker_health.items():
            last_seen = profile_run.worker_last_seen.get(worker_id, time.time())

            if worker_id not in self.worker_cards:
                # Create new worker card
                worker_card = WorkerCard(worker_id, id=f"worker-{worker_id}")
                self.worker_cards[worker_id] = worker_card

                # Remove empty state if it exists
                try:
                    container.query_one(".empty-state").remove()
                except Exception:
                    pass

                container.mount(worker_card)

            # Update existing worker card
            if worker_id in self.worker_cards:
                self.worker_cards[worker_id].update_worker_data(health_data, last_seen)

    def _update_summary_stats(self) -> None:
        """Update the summary statistics."""
        if not self.worker_cards:
            return

        # Count workers by status
        status_counts = {"healthy": 0, "warning": 0, "error": 0, "idle": 0, "stale": 0}

        for worker_card in self.worker_cards.values():
            status = worker_card.status
            if status in status_counts:
                status_counts[status] += 1

        total_workers = len(self.worker_cards)

        # Update header
        self.query_one("#worker-count", Label).update(f"{total_workers} workers")

        # Update summary
        healthy = status_counts["healthy"]
        warning = status_counts["warning"]
        error = status_counts["error"]
        idle = status_counts["idle"]
        stale = status_counts["stale"]

        summary_text = f"Healthy: {healthy}, Warning: {warning}, Error: {error}, Idle: {idle}, Stale: {stale}"
        self.query_one("#worker-summary", Label).update(summary_text)

    def update_worker_health(
        self, worker_id: str, health_data: "WorkerHealthMessage"
    ) -> None:
        """Update a specific worker's health data."""
        if worker_id in self.worker_cards:
            self.worker_cards[worker_id].update_worker_data(health_data, time.time())

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "sort-status":
            self.action_sort_by_status()
        elif event.button.id == "export-data":
            self.action_export_data()

    def on_worker_selected(self, message: WorkerSelected) -> None:
        """Handle worker selection."""
        self.notify(f"Selected worker: {message.worker_id}")

    def action_sort_by_status(self) -> None:
        """Sort workers by their status."""
        if not self.worker_cards:
            return

        # Sort worker cards by status priority
        status_priority = {
            "error": 0,
            "warning": 1,
            "stale": 2,
            "idle": 3,
            "healthy": 4,
        }

        sorted_cards = sorted(
            self.worker_cards.values(),
            key=lambda card: (status_priority.get(card.status, 5), card.worker_id),
        )

        # Re-mount cards in sorted order
        container = self.query_one("#worker-container", Vertical)
        container.remove_children()

        for card in sorted_cards:
            container.mount(card)

    def action_export_data(self) -> None:
        """Export worker data (placeholder)."""
        self.notify("Export functionality not implemented yet")

    def get_worker_summary(self) -> dict:
        """Get a summary of all workers."""
        if not self.worker_cards:
            return {}

        summary = {}
        for worker_id, card in self.worker_cards.items():
            summary[worker_id] = {
                "status": card.status,
                "last_seen": card.last_seen,
                "health_data": card.health_data,
            }

        return summary
