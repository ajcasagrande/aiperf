# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import multiprocessing
from collections import deque
from datetime import datetime

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import RichLog

from aiperf.common.hooks import aiperf_auto_task
from aiperf.common.logging import get_global_log_queue
from aiperf.common.mixins import AIPerfLifecycleMixin


class LogViewer(Container, AIPerfLifecycleMixin):
    """Clean log viewer widget that displays application logs using global log queue."""

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

    border_title = "System Logs"

    # Configuration constants (same as logs_mixin)
    MAX_LOG_RECORDS = 100
    MAX_LOG_MESSAGE_LENGTH = 400
    LOG_REFRESH_INTERVAL_SEC = 0.1
    MAX_LOG_LOGGER_NAME_LENGTH = 25

    # Color styles for log levels (matching logs_mixin)
    LOG_LEVEL_STYLES = {
        "TRACE": "dim",
        "DEBUG": "dim",
        "INFO": "green",
        "NOTICE": "blue",
        "WARNING": "yellow",
        "SUCCESS": "bold green",
        "ERROR": "red",
        "CRITICAL": "bold red",
    }

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.log_queue: multiprocessing.Queue = get_global_log_queue()
        self.log_records: deque[dict] = deque(maxlen=self.MAX_LOG_RECORDS)
        self.log_widget: RichLog | None = None

    def compose(self) -> ComposeResult:
        """Compose the clean log viewer layout."""
        self.log_widget = RichLog(
            highlight=True, markup=True, wrap=True, auto_scroll=True, id="log-content"
        )
        yield self.log_widget

    @aiperf_auto_task(interval_sec=LOG_REFRESH_INTERVAL_SEC)
    async def _consume_logs(self) -> None:
        """Consume log records from the queue and display them.

        This is a background task that runs every LOG_REFRESH_INTERVAL_SEC seconds
        to consume log records from the queue and display them in the log widget.
        """
        if self.log_widget is None:
            return

        # Process all pending log records
        while not self.log_queue.empty():
            try:
                log_data = self.log_queue.get_nowait()
                self.log_records.append(log_data)
                self._display_log_record(log_data)
            except Exception:
                # Silently ignore queue errors to avoid recursion
                break

    def _display_log_record(self, log_data: dict) -> None:
        """Display a single log record in the log widget."""
        if not self.log_widget:
            return

        timestamp = datetime.fromtimestamp(log_data["created"]).strftime("%H:%M:%S.%f")[
            :-3
        ]
        level_style = self.LOG_LEVEL_STYLES.get(log_data["levelname"], "white")

        formatted_log = (
            f"[dim]{timestamp}[/dim] "
            f"[blue]{log_data['name']}[/blue] "
            f"[{level_style}]{log_data['levelname']}[/{level_style}] "
            f"{log_data['msg']}"
        )

        self.log_widget.write(formatted_log)
