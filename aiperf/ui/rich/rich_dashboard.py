# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import time

from rich.console import Console
from rich.layout import Layout
from rich.live import Live

from aiperf.common.hooks import background_task, on_start, on_stop
from aiperf.common.messages import WorkerHealthMessage
from aiperf.common.mixins import AIPerfLifecycleMixin
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.rich.dashboard_element import DashboardElement, HeaderElement
from aiperf.ui.rich.logs_mixin import LogsDashboardMixin
from aiperf.ui.rich.profile_progress_ui import ProfileProgressElement
from aiperf.ui.rich.worker_status_ui import WorkerStatusElement

logger = logging.getLogger(__name__)


class AIPerfRichDashboard(LogsDashboardMixin, AIPerfLifecycleMixin):
    """Main AIPerf Rich Dashboard with live updates."""

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
        self.console = Console()
        self.progress_tracker = progress_tracker
        self.worker_health: dict[str, WorkerHealthMessage] = {}
        self.worker_last_seen: dict[str, float] = {}

        self.elements: dict[str, DashboardElement] = {
            HeaderElement.key: HeaderElement(),
            ProfileProgressElement.key: ProfileProgressElement(progress_tracker),
            WorkerStatusElement.key: WorkerStatusElement(
                self.worker_health, self.worker_last_seen
            ),
        }

        self.layout = self._create_layout()
        self.live: Live | None = None
        self.running = False

    def _create_layout(self) -> Layout:
        """Create the main layout for the dashboard."""

        layout = Layout()

        layout.split_column(
            Layout(name=HeaderElement.key, size=3),
            Layout(name="body", ratio=2),
            Layout(name="logs", size=12),
        )

        layout["body"].split_row(Layout(name="left"), Layout(name="right", ratio=1))

        layout["left"].split_column(
            Layout(name=ProfileProgressElement.key),
        )

        layout["right"].split_row(Layout(name=WorkerStatusElement.key, ratio=1))

        return layout

    @background_task(interval=0.1)
    async def _update_logs(self) -> None:
        """Update the dashboard display."""
        if not self.running:
            return

        self.layout["logs"].update(self.get_logs_panel())

    def update_display(self) -> None:
        """Update the dashboard display."""
        if not self.running:
            return

        try:
            for element in self.elements.values():
                self.layout[element.key].update(element.get_panel())
        except Exception as e:
            self.error("Error updating dashboard display: %s", e)

    def refresh_element(self, element_key: str) -> None:
        """Refresh the specified element."""
        self.debug("Refreshing ui element: %s", element_key)
        self.layout[element_key].update(self.elements[element_key].get_panel())

    def update_worker_health(self, health_message: WorkerHealthMessage) -> None:
        """Update worker health information."""
        self.worker_health[health_message.service_id] = health_message
        self.worker_last_seen[health_message.service_id] = time.time()

    @on_start
    async def _start(self) -> None:
        """Start the live dashboard."""
        self.running = True
        self.live = Live(
            self.layout,
            console=self.console,
            refresh_per_second=4,
            screen=True,
        )
        self.live.start()
        self.update_display()

    @on_stop
    async def _stop(self) -> None:
        """Stop the live dashboard."""
        self.running = False

        if self.live:
            # TODO: Do we still want to do this?
            # Store final state before stopping, then print it to persist it.
            self.final_renderable = self.live.renderable
            self.live.stop()
            if self.final_renderable:
                self.console.print(self.final_renderable)
