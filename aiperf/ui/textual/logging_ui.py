# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import contextlib
import logging

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import RichLog


class TextualLogHandler(logging.Handler):
    """Custom logging handler that sends log messages to a Textual log widget."""

    DEFAULT_CSS = """
    TextualLogHandler {
        border: solid $accent;
        border-title-color: $accent;
        border-title-background: $surface;
        height: 100%;
    }
    """

    # Map log levels to Rich formatting
    LOG_LEVEL_STYLES = {
        logging.ERROR: "bold red",
        logging.WARNING: "bold yellow",
        logging.INFO: "bold cyan",
        logging.DEBUG: "dim",
    }

    def __init__(self, log_widget: RichLog) -> None:
        super().__init__()
        self.log_widget = log_widget
        # Set a more visually appealing format for the logs
        formatter = logging.Formatter(
            "[dim][%(asctime)s][/dim] [bold][%(levelname)s][/bold] [%(name)s]: %(message)s",
            datefmt="%H:%M:%S.%s",
        )
        self.setFormatter(formatter)
        self.log_widget.border_title = "System Logs"

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the Textual log widget with color coding."""

        # Silently ignore errors in log handling to avoid recursion
        with contextlib.suppress(Exception):
            if not self.log_widget.display:
                return

            # style = self.LOG_LEVEL_STYLES.get(record.levelno, "dim")
            self.log_widget.write(f"{self.format(record)}")


class LogViewer(Container):
    """Clean log viewer widget that displays application logs."""

    DEFAULT_CSS = """
    #log-content {
        border: round rgb(100,205,145);
        height: 100%;
        padding: 0;
        margin: 0;
        scrollbar-size-vertical: 1;
        scrollbar-gutter: stable;
        scrollbar-color: rgb(100,205,145);
    }
    """

    border_title = "Application Logs"

    def __init__(self) -> None:
        super().__init__()
        self.log_widget: RichLog | None = None
        self.log_handler: TextualLogHandler | None = None

    def compose(self) -> ComposeResult:
        """Compose the clean log viewer layout."""
        self.log_widget = RichLog(
            highlight=True, markup=True, wrap=True, auto_scroll=True, id="log-content"
        )
        yield self.log_widget

    def on_mount(self) -> None:
        """Set up logging when the widget is mounted."""
        if self.log_widget:
            # Create and configure the log handler
            self.log_handler = TextualLogHandler(self.log_widget)
            self.log_handler.setLevel(logging.DEBUG)

            # Add handler to the root logger to capture all logs
            root_logger = logging.getLogger()
            root_logger.addHandler(self.log_handler)

    def on_unmount(self) -> None:
        """Clean up logging when the widget is unmounted."""
        if self.log_handler:
            # Remove handler from loggers
            root_logger = logging.getLogger()
            root_logger.removeHandler(self.log_handler)

            aiperf_logger = logging.getLogger("aiperf")
            aiperf_logger.removeHandler(self.log_handler)

            self.log_handler = None
