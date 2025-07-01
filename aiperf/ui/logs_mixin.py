#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import logging
import multiprocessing
from collections import deque
from datetime import datetime

from rich.table import Table
from rich.text import Text

from aiperf.common.hooks import (
    AIPerfLifecycleMixin,
    aiperf_auto_task,
    on_init,
)
from aiperf.common.logging import get_global_log_queue

logger = logging.getLogger(__name__)


class LogsDashboardMixin(AIPerfLifecycleMixin):
    """Mixin for capturing and displaying logs from multiple processes."""

    MAX_LOG_RECORDS = 100
    MAX_LOG_MESSAGE_LENGTH = 400
    LOG_REFRESH_INTERVAL = 0.1
    MAX_LOG_LOGGER_NAME_LENGTH = 25

    LOG_LEVEL_STYLES = {
        "DEBUG": "dim",
        "INFO": "green",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold red",
    }

    LOG_MSG_STYLES = {
        "DEBUG": "dim",
        "INFO": "white",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "bold red",
    }

    def __init__(self) -> None:
        super().__init__()
        self.log_queue: multiprocessing.Queue | None = None
        self.log_records: deque[dict] = deque(maxlen=self.MAX_LOG_RECORDS)

    @on_init
    def _init_log_queue(self) -> None:
        """Retrieve the global log queue."""
        self.log_queue = get_global_log_queue()

    @aiperf_auto_task(interval=LOG_REFRESH_INTERVAL)
    async def _consume_logs(self) -> None:
        """Consume log records from the queue in a background task."""
        if self.log_queue is None:
            return

        while not self.log_queue.empty():
            log_data = self.log_queue.get_nowait()
            self.log_records.append(log_data)

    def _create_logs_table(self) -> Table:
        """Create the logs panel."""
        logs_table = Table.grid(expand=False, padding=(0, 1, 0, 0))
        logs_table.add_column("Time", style="dim", width=15, justify="left")
        logs_table.add_column(
            "Logger",
            style="blue",
            width=self.MAX_LOG_LOGGER_NAME_LENGTH,
            justify="left",
        )
        logs_table.add_column("Level", style="bold", width=8, justify="left")
        logs_table.add_column("Message", style="white", justify="left")

        # Show recent logs (most recent first)
        recent_logs = list(self.log_records)[-10:]  # Show last 10 logs

        for log_data in recent_logs:
            # Format timestamp
            timestamp = datetime.fromtimestamp(log_data["created"]).strftime(
                "%H:%M:%S.%f"
            )

            # Color code log levels and messages
            level_style = self.LOG_LEVEL_STYLES.get(log_data["levelname"], "white")
            msg_style = self.LOG_MSG_STYLES.get(log_data["levelname"], "white")

            logs_table.add_row(
                timestamp,
                log_data["name"][: self.MAX_LOG_LOGGER_NAME_LENGTH],
                Text(log_data["levelname"], style=level_style),
                Text(log_data["msg"][: self.MAX_LOG_MESSAGE_LENGTH], style=msg_style),
            )

        return logs_table
