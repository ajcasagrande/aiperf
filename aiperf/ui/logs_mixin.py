#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import logging
import multiprocessing
import queue
import time
from collections import deque

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.text import Text

from aiperf.common.hooks import (
    AIPerfLifecycleMixin,
    aiperf_auto_task,
    on_cleanup,
    on_init,
    on_start,
)
from aiperf.common.logging import MultiProcessLogHandler, setup_global_log_queue

logger = logging.getLogger(__name__)


class ConsoleUIMixin(AIPerfLifecycleMixin):
    """Mixin for updating the console UI."""

    def __init__(self) -> None:
        super().__init__()
        self.console = Console()
        self.live: Live = Live(console=self.console)

    @on_start
    async def _start_live(self) -> None:
        """Start the live console UI."""
        self.live.start()

    @on_cleanup
    async def _cleanup_live(self) -> None:
        """Cleanup the live console UI."""
        self.live.stop()


class LogsDashboardMixin(ConsoleUIMixin):
    """Mixin for capturing and displaying logs from multiple processes."""

    def __init__(self) -> None:
        super().__init__()
        self.log_queue: multiprocessing.Queue | None = None
        self.log_records: deque[dict] = deque(maxlen=100)  # Keep last 100 logs
        self.log_handler: MultiProcessLogHandler | None = None

    @on_init
    def setup_multiprocess_logging(self) -> multiprocessing.Queue:
        """Set up multiprocessing logging infrastructure.

        Returns:
            The multiprocessing queue that child processes should use for logging.
        """
        # Set up global log queue
        self.log_queue = setup_global_log_queue()

        # Set up handler for current process
        self.log_handler = MultiProcessLogHandler(self.log_queue)
        self.log_handler.setLevel(logging.DEBUG)

        # Add to root logger to capture all logs
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)

        return self.log_queue

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

    def _create_logs_panel(self) -> Table:
        """Create the logs panel."""
        logs_table = Table.grid(expand=True)
        logs_table.add_column("Time", style="dim", width=12)
        logs_table.add_column("Process", style="cyan", width=15)
        logs_table.add_column("Level", style="bold", width=8)
        logs_table.add_column("Logger", style="blue", width=20)
        logs_table.add_column("Message", style="white")

        # Show recent logs (most recent first)
        recent_logs = list(self.log_records)[-10:]  # Show last 10 logs

        for log_data in recent_logs:
            # Format timestamp
            timestamp = time.strftime("%H:%M:%S", time.localtime(log_data["created"]))

            # Get process info
            process_name = log_data.get("process_name", "main")
            process_id = log_data.get("process_id", 0)
            process_info = f"{process_name}:{process_id}"

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
                process_info[:15],  # Truncate long process names
                Text(log_data["levelname"], style=level_style),
                log_data["name"][:20],  # Truncate long logger names
                log_data["msg"][:80],  # Truncate long messages
            )

        return logs_table
