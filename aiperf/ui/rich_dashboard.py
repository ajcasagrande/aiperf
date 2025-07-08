# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import time
from abc import ABC, abstractmethod
from typing import ClassVar

from rich.align import Align, AlignMethod
from rich.console import Console, RenderableType
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.style import StyleType
from rich.text import Text

from aiperf.common.hooks import (
    AIPerfLifecycleMixin,
    aiperf_auto_task,
    on_start,
    on_stop,
)
from aiperf.common.messages import WorkerHealthMessage
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.logs_mixin import LogsDashboardMixin
from aiperf.ui.profile_progress_ui import ProfileProgressElement
from aiperf.ui.worker_status_ui import WorkerStatusElement

logger = logging.getLogger(__name__)


class DashboardElement(ABC):
    """Base class for dashboard elements."""

    key: ClassVar[str]
    title: ClassVar[Text | str | None] = None
    border_style: ClassVar[StyleType | None] = None
    title_align: ClassVar[AlignMethod] = "center"
    height: ClassVar[int | None] = None
    width: ClassVar[int | None] = None
    expand: ClassVar[bool] = True

    @abstractmethod
    def get_content(self) -> RenderableType:
        """Get the content for the dashboard element."""
        raise NotImplementedError("Subclasses must implement get_content")

    def get_panel(self) -> Panel:
        """Get the panel for the dashboard element."""
        return Panel(
            self.get_content(),
            title=self.title,
            border_style=self.border_style if self.border_style else "none",
            title_align=self.title_align,
            height=self.height,
            width=self.width,
            expand=self.expand,
        )


class HeaderElement(DashboardElement):
    """Header element for the dashboard."""

    key = "header"
    border_style = "bright_green"

    def get_content(self) -> RenderableType:
        """Get the content for the header element."""
        return Align.center(Text("NVIDIA AIPerf Dashboard", style="bold bright_green"))


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
            ProfileProgressElement.key: ProfileProgressElement(self.progress_tracker),
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

    def _get_logs_panel(self) -> Panel:
        """Create the logs panel with recent log entries."""
        return Panel(
            self._create_logs_table(),
            title="[bold]System Logs[/bold]",
            border_style="yellow",
            height=12,
            title_align="left",
        )

    @aiperf_auto_task(interval_sec=0.1)
    async def _update_logs(self) -> None:
        """Update the dashboard display."""
        if not self.running:
            return

        self.layout["logs"].update(self._get_logs_panel())

    def update_display(self) -> None:
        """Update the dashboard display."""
        if not self.running:
            return

        try:
            for element in self.elements.values():
                self.layout[element.key].update(element.get_panel())
        except Exception as e:
            logger.error(f"Error updating dashboard display: {e}")

    def refresh_element(self, element_key: str) -> None:
        """Refresh the specified element."""
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
