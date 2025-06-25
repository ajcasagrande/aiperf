# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import contextlib
import logging
from collections.abc import Callable
from typing import Any

from rich.text import Text
from textual.dom import NoScreen
from textual.events import Mount
from textual.widget import Widget
from textual.widgets._header import (
    HeaderTitle,
)

from aiperf.common.models.progress import ProfileProgress
from aiperf.common.progress_tracker import ProgressTracker

logger = logging.getLogger(__name__)


class DashboardFormatter:
    """Utility class for formatting dashboard fields."""

    @staticmethod
    def format_duration(seconds: float | None) -> str:
        """Format duration in seconds to human-readable format."""
        if seconds is None:
            return "--"

        if seconds < 60:
            return f"{seconds:.1f}s"

        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60

        if minutes < 60:
            if remaining_seconds < 1:
                return f"{minutes}m"
            return f"{minutes}m {remaining_seconds:.0f}s"

        hours = minutes // 60
        minutes = minutes % 60

        if hours < 24:
            if minutes == 0:
                return f"{hours}h"
            return f"{hours}h {minutes}m"

        days = hours // 24
        hours = hours % 24

        if hours == 0:
            return f"{days}d"
        return f"{days}d {hours}h"

    @staticmethod
    def format_count_with_total(count: int | None, total: int | None) -> str:
        """Format count with total (e.g., '150 / 1,000')."""
        if count is None or total is None:
            return "--"
        return f"{count:,} / {total:,}"

    @staticmethod
    def format_percentage(value: float | None) -> str:
        """Format percentage (e.g., '15.2%')."""
        if value is None:
            return "--"
        return f"{value:.1f}%"

    @staticmethod
    def format_rate(rate: float | None) -> str:
        """Format request rate (e.g., '25.4 req/s')."""
        return f"{rate:,.1f} req/s" if rate is not None and rate > 0 else "-- req/s"

    @staticmethod
    def format_error_stats(
        error_count: int, total: int, error_rate: float | None
    ) -> str:
        """Format error statistics (e.g., '2 / 152 (1.3%)')."""
        if None in (error_count, total, error_rate):
            return "--"
        return f"{error_count:,} / {total:,} ({error_rate:.1%})"


class StatusClassifier:
    """Utility class for determining status classes based on values."""

    @staticmethod
    def get_error_status(error_rate: float | None) -> str:
        """Get error status class based on error rate."""
        if error_rate is None:
            return "status-idle"
        if error_rate == 0.0:
            return "error-none"
        return "error"

    @staticmethod
    def get_completion_status(is_complete: bool) -> str:
        """Get completion status class."""
        if is_complete:
            return "status-complete"
        else:
            return "status-processing"


class DashboardField:
    """Represents a dashboard field with its formatting and update logic."""

    def __init__(
        self,
        field_id: str,
        label: str,
        value_getter: Callable[[ProgressTracker, ProfileProgress], Any],
        formatter: Callable[[Any], str],
        status_classifier: Callable[[Any], str] | None = None,
        show_dot: bool = True,
    ):
        self.field_id = field_id
        self.label = label
        self.value_getter = value_getter
        self.formatter = formatter
        self.status_classifier = status_classifier
        self.show_dot = show_dot

    def update(
        self, container: Widget, progress: ProgressTracker, profile: ProfileProgress
    ) -> None:
        """Update this field in the container."""
        try:
            widget = container.query_one(f"#{self.field_id}", StatusIndicator)
            raw_value = self.value_getter(progress, profile)
            formatted_value = self.formatter(raw_value)
            status_class = (
                self.status_classifier(raw_value) if self.status_classifier else ""
            )
            widget.update_value(formatted_value, status_class)
        except Exception as e:
            logger.error(f"Error updating {self.field_id}: {e}")


class StatusIndicator(Widget):
    """A custom widget to display status with colored indicators and rich formatting."""

    DEFAULT_CSS = """
    StatusIndicator {
        height: 1;
        margin: 0 1;
        padding: 0 1;
    }
    """

    def __init__(
        self,
        label: str,
        value: str = "",
        status_class: str = "",
        show_dot: bool = True,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.label = label
        self.value = value
        self.status_class = status_class
        self.show_dot = show_dot

    def render(self) -> Text:
        """Render the status indicator with rich formatting."""
        text = Text()

        # Add colored dot based on status
        if self.show_dot and self.status_class:
            if "processing" in self.status_class:
                text.append("● ", style="bold yellow")
            elif self.status_class in ("complete", "error-none"):
                text.append("● ", style="bold green")
            elif "error" in self.status_class:
                text.append("● ", style="bold red")
            else:
                text.append("● ", style="bold blue")

        # Add bold label
        text.append(f"{self.label}: ", style="bold")

        # Add value with appropriate styling
        if self.status_class:
            if "complete" in self.status_class:
                text.append(self.value, style="bold green")
            elif "processing" in self.status_class:
                text.append(self.value, style="bold yellow")
            elif "error" in self.status_class:
                text.append(self.value, style="bold red")
            elif "error-none" in self.status_class:
                text.append(self.value, style="bold green")
            else:
                text.append(self.value, style="bold cyan")
        else:
            text.append(self.value, style="bold cyan")

        return text

    def update_value(self, value: str, status_class: str = "") -> None:
        """Update the value and status class."""
        self.value = value
        if status_class:
            self.status_class = status_class
        self.refresh()


class Header(Widget):
    """Custom header alternative to the default Textual header."""

    DEFAULT_CSS = """
    Header {
        dock: top;
        width: 100%;
        background: $panel;
        color: $foreground;
        height: 1;
    }
    """

    DEFAULT_CLASSES = ""

    def __init__(
        self,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ):
        """Initialise the header widget.

        Args:
            name: The name of the header widget.
            id: The ID of the header widget in the DOM.
            classes: The CSS classes of the header widget.
        """
        super().__init__(name=name, id=id, classes=classes)

    def compose(self):
        yield HeaderTitle()

    @property
    def screen_title(self) -> str:
        """The title that this header will display.

        This depends on [`Screen.title`][textual.screen.Screen.title] and [`App.title`][textual.app.App.title].
        """
        screen_title = self.screen.title
        title = screen_title if screen_title is not None else self.app.title
        return title

    @property
    def screen_sub_title(self) -> str:
        """The sub-title that this header will display.

        This depends on [`Screen.sub_title`][textual.screen.Screen.sub_title] and [`App.sub_title`][textual.app.App.sub_title].
        """
        screen_sub_title = self.screen.sub_title
        sub_title = (
            screen_sub_title if screen_sub_title is not None else self.app.sub_title
        )
        return sub_title

    def _on_mount(self, _: Mount) -> None:
        async def set_title() -> None:
            with contextlib.suppress(NoScreen):
                self.query_one(HeaderTitle).text = self.screen_title

        async def set_sub_title() -> None:
            with contextlib.suppress(NoScreen):
                self.query_one(HeaderTitle).sub_text = self.screen_sub_title

        self.watch(self.app, "title", set_title)
        self.watch(self.app, "sub_title", set_sub_title)
        self.watch(self.screen, "title", set_title)
        self.watch(self.screen, "sub_title", set_sub_title)
