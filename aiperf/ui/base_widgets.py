# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import abstractmethod
from typing import TYPE_CHECKING, ClassVar

from textual.app import ComposeResult
from textual.containers import Container
from textual.widget import Widget

if TYPE_CHECKING:
    from aiperf.progress.progress_tracker import ProgressTracker


class BaseAIPerfWidget(Widget):
    """Base class for all AIPerf widgets with common functionality."""

    DEFAULT_CSS = """
    BaseAIPerfWidget {
        border: solid #76b900;
        background: #1a1a1a;
        margin: 1;
        padding: 1;
    }

    BaseAIPerfWidget:focus {
        border: solid #00d4aa;
    }

    BaseAIPerfWidget > .widget-title {
        color: #ffffff;
        text-style: bold;
        padding: 0 1;
    }
    """

    widget_title: ClassVar[str] = "AIPerf Widget"
    can_focus: bool = True

    def __init__(
        self, progress_tracker: "ProgressTracker | None" = None, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.progress_tracker = progress_tracker
        self.update_timer = None

    @abstractmethod
    def compose(self) -> ComposeResult:
        """Compose the widget content."""
        pass

    @abstractmethod
    def update_content(self) -> None:
        """Update the widget content with fresh data."""
        pass

    def on_mount(self) -> None:
        """Called when widget is mounted."""
        self.set_interval(1.0, self.update_content)

    def on_unmount(self) -> None:
        """Called when widget is unmounted."""
        if self.update_timer:
            self.update_timer.stop()


class BaseContainerWidget(Container):
    """Base container widget for grouping related widgets."""

    DEFAULT_CSS = """
    BaseContainerWidget {
        background: #1a1a1a;
        border: solid #76b900;
        margin: 1;
        padding: 1;
    }

    BaseContainerWidget > .container-title {
        color: #ffffff;
        text-style: bold;
        padding: 0 1;
        background: #76b900;
        color: #000000;
    }
    """

    container_title: ClassVar[str] = "Container"

    def __init__(
        self, progress_tracker: "ProgressTracker | None" = None, **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self.progress_tracker = progress_tracker

    @abstractmethod
    def compose(self) -> ComposeResult:
        """Compose the container content."""
        pass


class InteractiveAIPerfWidget(BaseAIPerfWidget):
    """Base class for interactive widgets that handle user input."""

    DEFAULT_CSS = """
    InteractiveAIPerfWidget {
        border: solid #2d5aa0;
    }

    InteractiveAIPerfWidget:focus {
        border: solid #00d4aa;
        background: #2a2a2a;
    }

    InteractiveAIPerfWidget:hover {
        background: #3a3a3a;
    }
    """

    def __init__(
        self, progress_tracker: "ProgressTracker | None" = None, **kwargs
    ) -> None:
        super().__init__(progress_tracker, **kwargs)
        self.can_focus = True

    def action_toggle_details(self) -> None:
        """Toggle detailed view for this widget."""
        self.toggle_class("detailed")

    def action_refresh(self) -> None:
        """Manually refresh the widget content."""
        self.update_content()


class DataDisplayWidget(BaseAIPerfWidget):
    """Base class for widgets that display data in tabular or structured format."""

    DEFAULT_CSS = """
    DataDisplayWidget {
        border: solid #76b900;
        background: #1a1a1a;
    }

    DataDisplayWidget .data-header {
        background: #76b900;
        color: #000000;
        text-style: bold;
        padding: 0 1;
    }

    DataDisplayWidget .data-row {
        padding: 0 1;
    }

    DataDisplayWidget .data-row:hover {
        background: #2a2a2a;
    }

    DataDisplayWidget .data-value {
        color: #ffffff;
    }

    DataDisplayWidget .data-label {
        color: #888888;
        text-style: bold;
    }

    DataDisplayWidget .status-healthy {
        color: #00ff00;
        text-style: bold;
    }

    DataDisplayWidget .status-warning {
        color: #ffaa00;
        text-style: bold;
    }

    DataDisplayWidget .status-error {
        color: #ff0000;
        text-style: bold;
    }

    DataDisplayWidget .status-info {
        color: #00d4aa;
        text-style: bold;
    }
    """

    def format_percentage(self, value: float) -> str:
        """Format a percentage value with appropriate styling."""
        return f"{value:.1f}%"

    def format_rate(self, value: float, unit: str = "req/s") -> str:
        """Format a rate value with appropriate styling."""
        if value >= 1000:
            return f"{value / 1000:.1f}k {unit}"
        return f"{value:.1f} {unit}"

    def format_duration(self, seconds: float) -> str:
        """Format a duration in seconds to human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            return f"{seconds / 60:.1f}m"
        else:
            return f"{seconds / 3600:.1f}h"

    def format_memory(self, memory_mb: float) -> str:
        """Format memory usage in MB to human-readable format."""
        if memory_mb >= 1024:
            return f"{memory_mb / 1024:.1f} GB"
        return f"{memory_mb:.0f} MB"

    def get_status_class(self, status: str) -> str:
        """Get CSS class for status styling."""
        status_map = {
            "healthy": "status-healthy",
            "warning": "status-warning",
            "error": "status-error",
            "info": "status-info",
        }
        return status_map.get(status.lower(), "status-info")
