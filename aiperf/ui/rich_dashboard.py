# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
import time
from collections import deque

from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich.text import Text

from aiperf.common.hooks import (
    AIPerfLifecycleMixin,
    aiperf_auto_task,
    on_start,
    on_stop,
)
from aiperf.common.models.messages import WorkerHealthMessage
from aiperf.common.progress_tracker import ProgressTracker
from aiperf.ui.logs_mixin import LogsDashboardMixin

logger = logging.getLogger(__name__)


class RichLogHandler(logging.Handler):
    """Custom logging handler that captures logs for the Rich dashboard."""

    def __init__(self, max_logs: int = 500) -> None:
        super().__init__()
        self.logs: deque[str] = deque(maxlen=max_logs)
        self.formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)-8s %(name)s: %(message)s", datefmt="%H:%M:%S"
        )

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to the internal log storage."""
        try:
            msg = self.format(record)
            level_colors = {
                "ERROR": "bold red",
                "WARNING": "bold yellow",
                "INFO": "bold cyan",
                "DEBUG": "dim white",
            }
            level = record.levelname
            color = level_colors.get(level, "white")
            formatted_msg = f"[{color}]{msg}[/{color}]"
            self.logs.append(formatted_msg)
        except Exception:
            # Silently ignore errors in log handling to avoid recursion
            pass


class AIPerfRichDashboard(LogsDashboardMixin, AIPerfLifecycleMixin):
    """Main AIPerf Rich Dashboard with live updates and clean interface."""

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
        self.console = Console()
        self.progress_tracker = progress_tracker
        self.worker_health: dict[str, WorkerHealthMessage] = {}
        self.worker_last_seen: dict[str, float] = {}

        # Progress tracking
        self.main_progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            expand=True,
        )

        self.progress_task_id: TaskID | None = None
        self.layout = self._create_layout()
        self.live: Live | None = None
        self.running = False

    def _create_layout(self) -> Layout:
        """Create the main layout for the dashboard."""
        layout = Layout()

        # Split into header and body
        layout.split_column(Layout(name="header", size=3), Layout(name="body"))

        # Split body into main content and logs
        layout["body"].split_column(
            Layout(name="main", ratio=2), Layout(name="logs", size=12)
        )

        # Split main into progress and workers
        layout["main"].split_row(Layout(name="progress"), Layout(name="workers"))

        return layout

    def _get_header_panel(self) -> Panel:
        """Create the header panel with title and status."""
        # current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        title = Text("AIPerf Performance Dashboard", style="bold blue")
        # subtitle = Text(
        #     f"Real-time AI Performance Testing • {current_time}", style="dim"
        # )

        header_content = Align.center(Text.assemble(title))

        return Panel(header_content, style="blue", border_style="bright_blue")

    def _get_progress_panel(self) -> Panel:
        """Create the progress panel with performance metrics."""
        if not self.progress_tracker.current_profile:
            content = Align.center(
                Text("Waiting for performance data...", style="dim yellow"),
                vertical="middle",
            )
            return Panel(
                content, title="[bold]Profile Status[/bold]", border_style="green"
            )

        profile = self.progress_tracker.current_profile

        # Update progress task
        if self.progress_task_id is None and profile.total_expected_requests:
            self.progress_task_id = self.main_progress.add_task(
                "Processing requests...", total=profile.total_expected_requests
            )
        elif self.progress_task_id is not None:
            self.main_progress.update(
                self.progress_task_id, completed=profile.requests_completed or 0
            )

        # Create metrics table
        metrics_table = Table.grid(padding=(0, 1, 0, 0))
        metrics_table.add_column(style="bold cyan", justify="right")
        metrics_table.add_column(style="bold white")

        # Status
        if profile.is_complete:
            status = Text("Complete", style="bold green")
        elif profile.was_cancelled:
            status = Text("Cancelled", style="bold red")
        else:
            status = Text("Processing", style="bold yellow")

        # Error rate
        error_rate = 0.0
        if profile.requests_processed and profile.requests_processed > 0:
            error_rate = (
                (profile.request_errors or 0) / profile.requests_processed * 100
            )

        error_color = (
            "green" if error_rate == 0 else "red" if error_rate > 10 else "yellow"
        )

        # Add metrics rows
        metrics_table.add_row("Status:", str(status))
        metrics_table.add_row(
            "Progress:",
            f"{profile.requests_completed or 0:,} / {profile.total_expected_requests or 0:,} requests",
        )
        metrics_table.add_row(
            "Completion:",
            f"{(profile.requests_completed or 0) / (profile.total_expected_requests or 1) * 100:.1f}%",
        )
        metrics_table.add_row(
            "Errors:",
            f"[{error_color}]{profile.request_errors or 0:,} / {profile.requests_processed or 0:,} ({error_rate:.1f}%)[/{error_color}]",
        )
        metrics_table.add_row(
            "Request Rate:", f"{profile.requests_per_second or 0:.1f} req/s"
        )
        metrics_table.add_row(
            "Processing Rate:", f"{profile.processed_per_second or 0:.1f} req/s"
        )
        metrics_table.add_row("Elapsed:", self._format_duration(profile.elapsed_time))
        metrics_table.add_row(
            "ETA:", self._format_duration(profile.eta) if profile.eta else "--"
        )

        # Combine progress bar and metrics
        content = Group(self.main_progress, "", metrics_table)

        return Panel(content, title="[bold]Profile Status[/bold]", border_style="green")

    def _get_workers_panel(self) -> Panel:
        """Create the workers panel with worker health information."""
        if not self.worker_health:
            content = Align.center(
                Text("No worker data available", style="dim yellow"), vertical="middle"
            )
            return Panel(
                content, title="[bold]Worker Status[/bold]", border_style="blue"
            )

        # Create workers table
        workers_table = Table.grid(padding=(0, 1, 0, 0))
        workers_table.add_column("Worker", style="cyan", width=20)
        workers_table.add_column("Status", width=12)
        workers_table.add_column("Tasks", width=12, justify="right")
        workers_table.add_column("CPU", width=8, justify="right")
        workers_table.add_column("Memory", width=10, justify="right")
        workers_table.add_column("Connections", width=10, justify="right")

        current_time = time.time()

        # Summary counters
        healthy_count = 0
        warning_count = 0
        error_count = 0
        idle_count = 0
        stale_count = 0

        for service_id, health in sorted(self.worker_health.items()):
            worker_name = service_id
            last_seen = self.worker_last_seen.get(service_id, current_time)

            # Determine status
            if current_time - last_seen > 30:  # 30 seconds
                status = Text("Stale", style="dim white")
                stale_count += 1
            else:
                error_rate = (
                    health.failed_tasks / health.total_tasks
                    if health.total_tasks > 0
                    else 0
                )

                if error_rate > 0.1:  # More than 10% error rate
                    status = Text("Error", style="bold red")
                    error_count += 1
                elif health.cpu_usage > 75:  # High CPU usage
                    status = Text("High Load", style="bold yellow")
                    warning_count += 1
                elif health.total_tasks == 0:  # No tasks processed
                    status = Text("Idle", style="dim")
                    idle_count += 1
                else:
                    status = Text("Healthy", style="bold green")
                    healthy_count += 1

            # Format memory
            memory_mb = health.memory_usage
            if memory_mb >= 1024:
                memory_display = f"{memory_mb / 1024:.1f} GB"
            else:
                memory_display = f"{memory_mb:.0f} MB"

            workers_table.add_row(
                worker_name,
                status,
                f"{health.completed_tasks} / {health.total_tasks}",
                f"{health.cpu_usage:.1f}%",
                memory_display,
                str(health.net_connections),
            )

        # Create summary
        summary_text = Text.assemble(
            Text("Summary: ", style="bold"),
            Text(f"{healthy_count} healthy", style="green"),
            Text(" • "),
            Text(f"{warning_count} high load", style="yellow"),
            Text(" • "),
            Text(f"{error_count} errors", style="red"),
            Text(" • "),
            Text(f"{idle_count} idle", style="dim"),
            Text(" • "),
            Text(f"{stale_count} stale", style="dim white"),
        )

        content = Group(summary_text, "", workers_table)

        return Panel(content, title="[bold]Worker Status[/bold]", border_style="blue")

    def _get_logs_panel(self) -> Panel:
        """Create the logs panel with recent log entries."""
        return Panel(
            self._create_logs_panel(),
            title="[bold]System Logs[/bold]",
            border_style="yellow",
            height=12,
        )

    @aiperf_auto_task(interval=0.1)
    async def _update_logs(self) -> None:
        """Update the dashboard display."""
        if not self.running:
            return

        self.refresh_logs()

    def update_display(self) -> None:
        """Update the dashboard display."""
        if not self.running:
            return

        try:
            self.layout["header"].update(self._get_header_panel())
            self.refresh_progress()
            self.refresh_logs()
            self.refresh_workers()
        except Exception as e:
            logger.error(f"Error updating dashboard display: {e}")

    def refresh_progress(self) -> None:
        """Refresh the progress panel."""
        self.layout["progress"].update(self._get_progress_panel())

    def refresh_workers(self) -> None:
        """Refresh the workers panel."""
        self.layout["workers"].update(self._get_workers_panel())

    def refresh_logs(self) -> None:
        """Refresh the logs panel."""
        self.layout["logs"].update(self._get_logs_panel())

    def update_worker_health(self, health_message: WorkerHealthMessage) -> None:
        """Update worker health information."""
        # print(f"Updating worker health for {health_message}")
        self.worker_health[health_message.service_id] = health_message
        self.worker_last_seen[health_message.service_id] = time.time()

    @on_start
    async def _start(self) -> None:
        """Start the live dashboard."""
        self.running = True
        self.live = Live(
            self.layout,
            console=self.console,
            # refresh_per_second=4,
            screen=True,
        )
        self.live.start()

        # Initial update
        self.update_display()

    @on_stop
    async def _stop(self) -> None:
        """Stop the live dashboard."""
        self.running = False
        if self.live:
            self.live.stop()

        # Remove log handler
        root_logger = logging.getLogger()
        logging.basicConfig(level=root_logger.level)

    @staticmethod
    def _format_duration(seconds: float | None) -> str:
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
