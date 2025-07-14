#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Example script demonstrating the RichWorkerStatusContainer.

This script shows how to use the new Textual container that encapsulates
the Rich workers dashboard functionality.
"""

import asyncio
import time

from textual.app import App, ComposeResult
from textual.containers import Vertical

from aiperf.common.enums import CreditPhase
from aiperf.common.health_models import CPUTimes, CtxSwitches, IOCounters, ProcessHealth
from aiperf.common.messages import WorkerHealthMessage
from aiperf.common.worker_models import WorkerPhaseTaskStats
from aiperf.ui.textual.rich_worker_status_container import RichWorkerStatusContainer


class WorkerStatusExampleApp(App):
    """Example application showcasing the RichWorkerStatusContainer."""

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        height: 100%;
        padding: 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.worker_container: RichWorkerStatusContainer | None = None
        self.title = "Rich Worker Status Container Example"

    def compose(self) -> ComposeResult:
        """Compose the application layout."""
        with Vertical(id="main-container"):
            self.worker_container = RichWorkerStatusContainer()
            yield self.worker_container

    async def on_mount(self) -> None:
        """Initialize the application with sample data."""
        if self.worker_container:
            # Create sample worker health data
            sample_data = self._create_sample_worker_data()

            # Update the container with sample data
            self.worker_container.update_worker_health(sample_data)

            # Set up a timer to update the data periodically
            self.set_interval(2.0, self._update_sample_data)

    def _create_sample_worker_data(self) -> dict[str, WorkerHealthMessage]:
        """Create sample worker health data for demonstration."""
        current_time = time.time()

        # Worker 1: Healthy worker
        worker1_health = WorkerHealthMessage(
            service_id="worker-001",
            process=ProcessHealth(
                pid=12345,
                create_time=current_time - 3600,
                uptime=3600.0,
                cpu_usage=25.5,
                memory_usage=512.0,
                io_counters=IOCounters(
                    read_count=1000,
                    write_count=500,
                    read_bytes=1024000,
                    write_bytes=512000,
                    read_chars=2048000,
                    write_chars=1024000,
                ),
                cpu_times=CPUTimes(
                    user=10.5,
                    system=5.2,
                    iowait=0.3,
                ),
                num_ctx_switches=CtxSwitches(
                    voluntary=1000,
                    involuntary=50,
                ),
                num_threads=4,
            ),
            task_stats={
                CreditPhase.PROFILING: WorkerPhaseTaskStats(
                    total=100,
                    completed=90,
                    failed=2,
                ),
            },
        )

        # Worker 2: High CPU usage
        worker2_health = WorkerHealthMessage(
            service_id="worker-002",
            process=ProcessHealth(
                pid=12346,
                create_time=current_time - 3600,
                uptime=3600.0,
                cpu_usage=85.2,  # High CPU
                memory_usage=1024.0,
                io_counters=IOCounters(
                    read_count=2000,
                    write_count=1500,
                    read_bytes=2048000,
                    write_bytes=1024000,
                    read_chars=4096000,
                    write_chars=2048000,
                ),
                cpu_times=CPUTimes(
                    user=20.5,
                    system=10.2,
                    iowait=1.3,
                ),
                num_ctx_switches=CtxSwitches(
                    voluntary=2000,
                    involuntary=100,
                ),
                num_threads=8,
            ),
            task_stats={
                CreditPhase.PROFILING: WorkerPhaseTaskStats(
                    total=120,
                    completed=110,
                    failed=1,
                ),
            },
        )

        # Worker 3: High error rate
        worker3_health = WorkerHealthMessage(
            service_id="worker-003",
            process=ProcessHealth(
                pid=12347,
                create_time=current_time - 3600,
                uptime=3600.0,
                cpu_usage=45.0,
                memory_usage=256.0,
                io_counters=IOCounters(
                    read_count=500,
                    write_count=200,
                    read_bytes=512000,
                    write_bytes=256000,
                    read_chars=1024000,
                    write_chars=512000,
                ),
                cpu_times=CPUTimes(
                    user=5.5,
                    system=3.2,
                    iowait=0.1,
                ),
                num_ctx_switches=CtxSwitches(
                    voluntary=500,
                    involuntary=25,
                ),
                num_threads=2,
            ),
            task_stats={
                CreditPhase.PROFILING: WorkerPhaseTaskStats(
                    total=80,
                    completed=60,
                    failed=15,  # High error rate
                ),
            },
        )

        # Worker 4: Idle worker
        worker4_health = WorkerHealthMessage(
            service_id="worker-004",
            process=ProcessHealth(
                pid=12348,
                create_time=current_time - 1800,
                uptime=1800.0,
                cpu_usage=5.0,
                memory_usage=128.0,
                io_counters=IOCounters(
                    read_count=100,
                    write_count=50,
                    read_bytes=102400,
                    write_bytes=51200,
                    read_chars=204800,
                    write_chars=102400,
                ),
                cpu_times=CPUTimes(
                    user=1.5,
                    system=0.8,
                    iowait=0.0,
                ),
                num_ctx_switches=CtxSwitches(
                    voluntary=100,
                    involuntary=5,
                ),
                num_threads=1,
            ),
            task_stats={
                CreditPhase.PROFILING: WorkerPhaseTaskStats(
                    total=0,  # Idle
                    completed=0,
                    failed=0,
                ),
            },
        )

        return {
            "worker-001": worker1_health,
            "worker-002": worker2_health,
            "worker-003": worker3_health,
            "worker-004": worker4_health,
        }

    def _update_sample_data(self) -> None:
        """Update sample data to simulate changing worker conditions."""
        if not self.worker_container:
            return

        # Get current data and modify it
        current_data = self.worker_container.worker_health.copy()

        # Simulate changing conditions
        for worker_id, health in current_data.items():
            if worker_id == "worker-001":
                # Simulate changing CPU usage
                health.process.cpu_usage = 20.0 + (time.time() % 30)
                # Simulate task progress
                if CreditPhase.PROFILING in health.task_stats:
                    stats = health.task_stats[CreditPhase.PROFILING]
                    stats.completed = min(stats.completed + 1, stats.total)

            elif worker_id == "worker-002":
                # Simulate fluctuating high CPU
                health.process.cpu_usage = 75.0 + (time.time() % 20)

            elif worker_id == "worker-003":
                # Simulate more failures
                if CreditPhase.PROFILING in health.task_stats:
                    stats = health.task_stats[CreditPhase.PROFILING]
                    if stats.failed < 20:
                        stats.failed += 1
                        stats.total += 1

            elif worker_id == "worker-004":
                # Simulate idle worker occasionally getting tasks
                if time.time() % 10 < 2:  # 20% of the time
                    if CreditPhase.PROFILING in health.task_stats:
                        stats = health.task_stats[CreditPhase.PROFILING]
                        stats.total = 5
                        stats.completed = 3
                        stats.failed = 0
                else:
                    # Reset to idle
                    if CreditPhase.PROFILING in health.task_stats:
                        stats = health.task_stats[CreditPhase.PROFILING]
                        stats.total = 0
                        stats.completed = 0
                        stats.failed = 0

        # Update the container
        self.worker_container.update_worker_health(current_data)

    def on_key(self, event) -> None:
        """Handle key events."""
        if event.key == "q":
            self.exit()
        elif event.key == "c":
            # Clear all workers
            if self.worker_container:
                self.worker_container.clear_workers()
        elif event.key == "r" and self.worker_container:
            sample_data = self._create_sample_worker_data()
            self.worker_container.update_worker_health(sample_data)


async def main():
    """Main function to run the example application."""
    app = WorkerStatusExampleApp()
    await app.run_async()


if __name__ == "__main__":
    print("Rich Worker Status Container Example")
    print("====================================")
    print()
    print("This example demonstrates the RichWorkerStatusContainer,")
    print("a Textual container that encapsulates the Rich workers dashboard.")
    print()
    print("Controls:")
    print("  q - Quit")
    print("  c - Clear all workers")
    print("  r - Reset to initial data")
    print()
    print("The display updates automatically every 2 seconds.")
    print()

    asyncio.run(main())
