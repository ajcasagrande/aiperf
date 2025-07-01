#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import logging
import multiprocessing
import queue
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

    def __init__(self) -> None:
        super().__init__()
        self.log_queue: multiprocessing.Queue | None = None
        self.log_records: deque[dict] = deque(maxlen=100)  # Keep last 100 logs

    @on_init
    def setup_multiprocess_logging(self) -> None:
        """Set up multiprocessing logging infrastructure.

        Returns:
            The multiprocessing queue that child processes should use for logging.
        """
        # Set up global log queue
        self.log_queue = get_global_log_queue()
        logger.info(
            f"LogsDashboardMixin initialized with log_queue: {self.log_queue is not None}"
        )

    @aiperf_auto_task(interval=0.1)
    async def _consume_logs(self) -> None:
        """Consume log records from the queue in a background task."""
        if self.log_queue is None:
            return

        # Use get_nowait to avoid blocking
        while True:
            try:
                log_data = self.log_queue.get_nowait()
                self.log_records.append(log_data)
            except queue.Empty:
                break

    def _create_logs_table(self) -> Table:
        """Create the logs panel."""
        logs_table = Table.grid(expand=False, padding=(0, 1, 0, 0))
        logs_table.add_column("Time", style="dim", width=16, justify="left")
        # logs_table.add_column("Process", style="cyan", width=18)
        logs_table.add_column("Logger", style="blue", width=25, justify="left")
        logs_table.add_column("Level", style="bold", width=8, justify="left")
        logs_table.add_column("Message", style="white", justify="left")

        # Show recent logs (most recent first)
        recent_logs = list(self.log_records)[-10:]  # Show last 10 logs

        for log_data in recent_logs:
            # Format timestamp
            timestamp = datetime.fromtimestamp(log_data["created"]).strftime(
                "%H:%M:%S.%f"
            )

            # Get process info
            # process_name = log_data.get("process_name", "main")
            # process_id = log_data.get("process_id", 0)
            # process_info = f"{process_name}"

            # Color code log levels
            level_style = {
                "DEBUG": "dim",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold red",
            }.get(log_data["levelname"], "white")

            logs_table.add_row(
                timestamp,
                log_data["name"][:24],  # Truncate long logger names
                # process_info[:17],  # Truncate long process names
                Text(log_data["levelname"], style=level_style),
                log_data["msg"][:400],  # Truncate long messages
            )

        return logs_table
