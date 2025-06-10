#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

"""
AIPerf Console UI Module

This module provides a Rich-based console UI system for AIPerf with split-screen functionality
that displays both the progress dashboard and real-time logs from multiple processes.

## Split-Screen Layout Design

The UI splits the console screen into two sections:
- Top 75%: Progress Dashboard (request progress, statistics, timing info)
- Bottom 25%: System Logs (real-time logs from all processes with color coding)

## Multiprocess Logging Architecture

The logging system captures logs from:
1. Main process (SystemController, UI)
2. Child service processes (DatasetManager, TimingManager, etc.)
3. Worker processes (spawned by WorkerManager)

### How it works:

1. **Setup Phase:**
   - SystemController initializes AIPerfUI
   - AIPerfUI calls setup_global_log_queue() to create shared multiprocessing.Queue
   - Log consumer task starts to read from queue

2. **Child Process Integration:**
   - Each child process calls setup_child_process_logging() in bootstrap
   - MultiProcessLogHandler is added to root logger
   - All logs are forwarded to the shared queue with process info

3. **Display:**
   - Log consumer task reads from queue asynchronously
   - Recent logs are displayed in scrollable panel with:
     * Timestamp (HH:MM:SS)
     * Process name and PID
     * Log level (color coded)
     * Logger name
     * Message content

### Usage:

To integrate with child processes, call setup_child_process_logging() early:

```python
from aiperf.common.ui import setup_child_process_logging

# In child process initialization
setup_child_process_logging()  # Uses global log queue automatically
```

Or pass explicit log queue:

```python
# In multiprocessing.Process args
args=(service_class, config, log_queue)
```

### Features:

- **Non-blocking**: Logs are queued to prevent blocking application flow
- **Process identification**: Each log shows which process/worker it came from
- **Color coding**: Different log levels use different colors (ERROR=red, WARNING=yellow, etc.)
- **Real-time updates**: Logs appear immediately in the UI
- **Bounded memory**: Only keeps last 100 log records to prevent memory issues
- **Graceful degradation**: System continues working even if logging fails
"""

import asyncio
import contextlib
import logging
import multiprocessing
import queue
import threading
import time
from collections import deque
from typing import Union

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    ProgressColumn,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from aiperf.common.config.endpoint_config import EndPointConfig
from aiperf.common.constants import NANOS_PER_SECOND
from aiperf.common.data_exporter.console_exporter import ConsoleExporter
from aiperf.common.hooks import (
    AIPerfHook,
    HooksMixin,
    on_start,
    on_stop,
    supports_hooks,
)
from aiperf.common.logging import MultiProcessLogHandler, setup_global_log_queue
from aiperf.common.messages import (
    ProfileProgressMessage,
    ProfileResultsMessage,
    ProfileStatsMessage,
)

logger = logging.getLogger(__name__)


class RequestsPerSecondColumn(ProgressColumn):
    """Custom column to display requests per second."""

    def render(self, task) -> Text:
        """Render the requests per second for a task."""

        if task.finished:
            # If the task is completed, use the req_per_second field (covers the whole profile)
            text = (
                f"{task.fields['req_per_second']:.1f} req/s"
                if "req_per_second" in task.fields
                else "-- req/s"
            )
        else:
            # Otherwise, use the speed field (dynamic window over time)
            text = "-- req/s" if task.speed is None else f"{task.speed:,.1f} req/s"

        return Text(text, style="progress.data.speed")


@supports_hooks(AIPerfHook.ON_INIT, AIPerfHook.ON_START, AIPerfHook.ON_STOP)
class ConsoleUIMixin(HooksMixin):
    """Mixin for updating the console UI."""

    def __init__(self) -> None:
        super().__init__()
        self.console = Console()
        self.live: Live = Live(console=self.console)

    async def initialize(self) -> None:
        """Initialize the console UI."""
        await self.run_hooks_async(AIPerfHook.ON_INIT)

    async def start(self) -> None:
        """Start the console UI."""
        self.live.start()
        await self.run_hooks_async(AIPerfHook.ON_START)

    async def stop(self) -> None:
        """Stop the console UI."""
        await self.run_hooks_async(AIPerfHook.ON_STOP)
        self.live.stop()


class ProfileProgressDashboardMixin(ConsoleUIMixin):
    """Mixin for updating the profile progress dashboard."""

    def __init__(self) -> None:
        super().__init__()
        self.progress: Progress | None = None
        self.task_id: TaskID | None = None
        self.start_perf_counter_ns: int | None = None
        self.error_count: int = 0
        self.error_rate: float = 0.0
        self.total_completed: int = 0
        self.total_requests: int = 0

    @on_start
    async def run_profile_progress_dashboard(self) -> None:
        """Run the profile progress dashboard."""
        # Create progress bar with custom columns
        self.progress = Progress(
            SpinnerColumn(),
            "[bold blue]{task.description}",
            BarColumn(),
            MofNCompleteColumn(),
            TaskProgressColumn(),
            RequestsPerSecondColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            expand=True,
        )

        # panel = Panel(
        #     Text("Waiting for profile data...", style="dim"),
        #     title="AIPerf Dashboard",
        #     border_style="blue",
        # )
        # self.live.update(panel, refresh=True)

    def _refresh_progress_dashboard(self) -> Panel:
        """Create the main dashboard layout."""
        # Create stats table
        stats_table = Table.grid(padding=1)
        stats_table.add_column(style="cyan", no_wrap=True)
        stats_table.add_column(style="white")

        if self.task_id is not None and self.progress is not None:
            task = self.progress.tasks[self.task_id]

            # Calculate additional metrics
            completion_pct = (
                (task.completed / task.total * 100)
                if task.total and task.total > 0 and task.completed is not None
                else 0
            )
            elapsed_time = task.elapsed or 0

            stats_table.add_row(
                "Status:", "Processing" if not task.finished else "Complete"
            )
            stats_table.add_row(
                "Progress:", f"{task.completed:,} / {task.total:,} requests"
            )
            stats_table.add_row("Completion:", f"{completion_pct:.1f}%")
            stats_table.add_row(
                "Errors:",
                f"{self.error_count:,} / {self.total_completed:,} ({self.error_rate:.1%})",
            )
            stats_table.add_row(
                "Rate:",
                f"{task.speed:.1f} req/s" if task.speed else "-- req/s",
            )
            stats_table.add_row("Elapsed:", f"{elapsed_time:.1f}s")

            if (
                task.speed
                and task.speed > 0
                and not task.finished
                and task.total is not None
                and task.completed is not None
            ):
                remaining_requests = task.total - task.completed
                eta_seconds = remaining_requests / task.speed
                stats_table.add_row("ETA:", f"{eta_seconds:,.1f}s")

        # Combine progress bar and stats
        dashboard_content = Table.grid()
        dashboard_content.add_column()
        dashboard_content.add_row(self.progress)
        dashboard_content.add_row("")  # Spacing
        dashboard_content.add_row(stats_table)

        return Panel(
            dashboard_content,
            title="[bold blue]AIPerf Profile Dashboard",
            border_style="blue",
            padding=(1, 2),
            width=self.console.width,
            height=self.console.height,
            expand=True,
            highlight=True,
        )

    @on_stop
    async def stop_profile_progress_dashboard(self) -> None:
        """Stop the profile progress dashboard."""
        self.progress = None
        self.task_id = None

    def update_profile_progress(self, message: ProfileProgressMessage) -> None:
        """
        Update the profile progress with rich dashboard display.
        """
        if not self.progress:
            return

        # Initialize start time and task on first update
        if self.start_perf_counter_ns is None or self.task_id is None:
            self.start_perf_counter_ns = message.sweep_start_ns
            self.total_requests = message.total
            self.task_id = self.progress.add_task(
                "Processing Requests",
                total=message.total,
                completed=message.completed,
            )

        # Calculate requests per second
        elapsed_seconds = (
            (message.request_ns or time.perf_counter_ns()) - self.start_perf_counter_ns
        ) / NANOS_PER_SECOND

        req_per_second = (
            message.completed / elapsed_seconds if (elapsed_seconds or 0) > 0 else 0.0
        )

        # Update the progress task
        self.progress.update(
            self.task_id,
            completed=message.completed,
            total=message.total,
            req_per_second=req_per_second,
        )

        # Update the live display
        self.live.update(self._refresh_progress_dashboard())

    def update_profile_stats(self, message: ProfileStatsMessage) -> None:
        """Update the profile stats."""
        if not self.progress:
            return

        self.error_count = message.error_count
        self.error_rate = self.error_count / message.completed
        self.total_completed = message.completed
        self.live.update(self._refresh_progress_dashboard())


class FinalResultsDashboardMixin(ConsoleUIMixin):
    """Mixin for updating the final results dashboard."""

    def __init__(self) -> None:
        super().__init__()

        # TODO: make this take in the endpoint config
        self.console_exporter: ConsoleExporter = ConsoleExporter(
            console=self.console,
            live=self.live,
            endpoint_config=EndPointConfig(
                type="console",
                streaming=True,
            ),
        )


class LogsDashboardMixin(ConsoleUIMixin):
    """Mixin for capturing and displaying logs from multiple processes."""

    def __init__(self) -> None:
        super().__init__()
        self.log_queue: multiprocessing.Queue | None = None
        self.log_records: deque[dict] = deque(maxlen=100)  # Keep last 100 logs
        self.log_handler: MultiProcessLogHandler | None = None
        self._log_consumer_task: asyncio.Task | None = None
        self._stop_log_consumer = threading.Event()

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

    @on_start
    async def start_log_consumer(self) -> None:
        """Start the log consumer task."""
        if self.log_queue:
            self._log_consumer_task = asyncio.create_task(self._consume_logs())

    @on_stop
    async def stop_log_consumer(self) -> None:
        """Stop the log consumer task."""
        self._stop_log_consumer.set()
        if self._log_consumer_task:
            self._log_consumer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._log_consumer_task

    async def _consume_logs(self) -> None:
        """Consume log records from the queue in a background task."""
        while not self._stop_log_consumer.is_set():
            try:
                # Use get_nowait to avoid blocking
                if self.log_queue is not None:
                    while True:
                        try:
                            log_data = self.log_queue.get_nowait()
                            self.log_records.append(log_data)
                        except queue.Empty:
                            break

                # Sleep briefly to prevent busy waiting
                await asyncio.sleep(0.1)

            except Exception as e:
                logger.error(f"Error consuming logs: {e}")
                await asyncio.sleep(1.0)

    def _create_logs_panel(self) -> Panel:
        """Create the logs panel."""
        logs_table = Table.grid(expand=True)
        logs_table.add_column("Time", style="dim", width=12)
        logs_table.add_column("Process", style="cyan", width=15)
        logs_table.add_column("Level", style="bold", width=8)
        logs_table.add_column("Logger", style="blue", width=20)
        logs_table.add_column("Message", style="white")

        # Show recent logs (most recent first)
        recent_logs = list(self.log_records)[-20:]  # Show last 20 logs

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

        return Panel(
            logs_table,
            title="[bold yellow]System Logs",
            border_style="yellow",
            padding=(0, 1),
            height=20,  # Fixed height for logs section
        )


class SplitScreenDashboardMixin(ProfileProgressDashboardMixin, LogsDashboardMixin):
    """Mixin that combines progress dashboard and logs in a split screen layout."""

    def __init__(self) -> None:
        super().__init__()
        self.layout: Layout | None = None

    @on_start
    async def setup_split_screen_layout(self) -> None:
        """Set up the split screen layout."""
        # Create main layout
        self.layout = Layout()

        # Split into top (progress) and bottom (logs) sections
        self.layout.split_column(
            Layout(name="progress", ratio=3),  # 75% for progress
            Layout(name="logs", ratio=1),  # 25% for logs
        )

        # Initialize with empty panels
        self.layout["progress"].update(
            Panel(Text("Initializing...", style="dim"), title="AIPerf Dashboard")
        )
        self.layout["logs"].update(self._create_logs_panel())

    def _refresh_split_screen_dashboard(self) -> Layout:
        """Refresh the complete split screen dashboard."""
        if not self.layout:
            return Layout()

        # Update progress section
        if self.progress and self.task_id is not None:
            self.layout["progress"].update(self._refresh_progress_dashboard())

        # Update logs section
        self.layout["logs"].update(self._create_logs_panel())

        return self.layout

    def update_profile_progress(self, message: ProfileProgressMessage) -> None:
        """Update the profile progress with split screen display."""
        if not self.progress:
            return

        # Initialize start time and task on first update (same as before)
        if self.start_perf_counter_ns is None or self.task_id is None:
            self.start_perf_counter_ns = message.sweep_start_ns
            self.total_requests = message.total
            self.task_id = self.progress.add_task(
                "Processing Requests",
                total=message.total,
                completed=message.completed,
            )

        # Calculate requests per second (same as before)
        elapsed_seconds = (
            (message.request_ns or time.perf_counter_ns()) - self.start_perf_counter_ns
        ) / NANOS_PER_SECOND

        req_per_second = (
            message.completed / elapsed_seconds if (elapsed_seconds or 0) > 0 else 0.0
        )

        # Update the progress task (same as before)
        self.progress.update(
            self.task_id,
            completed=message.completed,
            total=message.total,
            req_per_second=req_per_second,
        )

        # Update the live display with split screen layout
        self.live.update(self._refresh_split_screen_dashboard())

    def update_profile_stats(self, message: ProfileStatsMessage) -> None:
        """Update the profile stats with split screen display."""
        if not self.progress:
            return

        self.error_count = message.error_count
        self.error_rate = (
            self.error_count / message.completed if message.completed > 0 else 0.0
        )
        self.total_completed = message.completed
        self.live.update(self._refresh_split_screen_dashboard())


class AIPerfUI(SplitScreenDashboardMixin, FinalResultsDashboardMixin):
    """
    AIPerfUI is a class that provides a UI for the AIPerf system.
    """

    _instance: Union["AIPerfUI", None] = None

    def __init__(self) -> None:
        super().__init__()

    @classmethod
    def get_instance(cls) -> "AIPerfUI":
        """Get the singleton instance of the AIPerfUI."""
        if cls._instance is None:
            cls._instance = AIPerfUI()
        return cls._instance  # type: ignore[reportUnboundVariable]

    def get_log_queue_for_child_processes(self) -> "multiprocessing.Queue | None":
        """Get the log queue that child processes should use for logging.

        Returns:
            The multiprocessing queue for child processes to send logs to, or None if not set up.
        """
        return self.log_queue

    async def process_final_results(self, message: ProfileResultsMessage) -> None:
        """Export the final results."""
        logger.info("Final results: %s", message.records)
        self.console_exporter.export(message.records)
        self.console.print("[bold green]Profile complete!")
