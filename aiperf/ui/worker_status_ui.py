# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time

from rich.align import Align
from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

from aiperf.common.enums import CreditPhase
from aiperf.common.utils import format_bytes
from aiperf.common.worker_models import WorkerHealthMessage
from aiperf.ui.rich_dashboard import DashboardElement


class WorkerStatusElement(DashboardElement):
    """Worker status element for the dashboard.

    This element displays the status of the workers along with detailed information
    about each worker.
    """

    key = "worker_status"
    title = Text("Worker Status", style="bold")
    border_style = "blue"

    def __init__(
        self,
        worker_health: dict[str, WorkerHealthMessage],
        worker_last_seen: dict[str, float],
    ) -> None:
        super().__init__()
        self.worker_health = worker_health
        self.worker_last_seen = worker_last_seen

    def get_content(self) -> RenderableType:
        """Get the content for the worker status element."""
        if not self.worker_health:
            return Align.center(
                Text("No worker data available", style="dim yellow"), vertical="middle"
            )

        workers_table = Table.grid(padding=(0, 2, 0, 0))
        workers_table.add_column("Worker ID", style="cyan", width=15)
        workers_table.add_column("Status", width=9)
        workers_table.add_column("Active", min_width=6, justify="right")
        workers_table.add_column("Completed", min_width=6, justify="right")
        workers_table.add_column("Failed", min_width=6, justify="right")
        workers_table.add_column("CPU", min_width=5, justify="right")
        workers_table.add_column("Memory", min_width=6, justify="right")
        workers_table.add_column("Read", min_width=8, justify="right")
        workers_table.add_column("Write", min_width=8, justify="right")

        workers_table.add_row(
            *[column.header for column in workers_table.columns], style="bold"
        )

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

            process = health.process
            task_stats = health.task_stats[CreditPhase.STEADY_STATE]
            # Determine status
            if current_time - last_seen > 30:  # 30 seconds
                status = Text("Stale", style="dim white")
                stale_count += 1
            else:
                error_rate = (
                    task_stats.failed_tasks / task_stats.total_tasks
                    if task_stats.total_tasks > 0
                    else 0
                )

                if error_rate > 0.1:  # More than 10% error rate
                    status = Text("Error", style="bold red")
                    error_count += 1
                elif process.cpu_usage > 75:  # High CPU usage
                    status = Text("High Load", style="bold yellow")
                    warning_count += 1
                elif task_stats.total_tasks == 0:  # No tasks processed
                    status = Text("Idle", style="dim")
                    idle_count += 1
                else:
                    status = Text("Healthy", style="bold green")
                    healthy_count += 1

            memory_mb = process.memory_usage
            if memory_mb >= 1024:
                memory_display = f"{memory_mb / 1024:.1f} GB"
            else:
                memory_display = f"{memory_mb:.0f} MB"

            workers_table.add_row(
                worker_name,
                status,
                f"{task_stats.in_progress_tasks:,}",
                f"{task_stats.completed_tasks:,}",
                f"{task_stats.failed_tasks:,}",
                f"{process.cpu_usage:.1f}%",
                memory_display,
                f"{format_bytes(process.io_counters.read_chars)}",
                f"{format_bytes(process.io_counters.write_chars)}",
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

        return Group(summary_text, workers_table)
