#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Test script to demonstrate the cleaned up AIPerf Textual UI.
"""

import asyncio
import logging
import time
from threading import Thread

from aiperf.common.enums import CreditPhase
from aiperf.common.worker_models import (
    ProcessInfo,
    ProcessIOCounters,
    TaskStatsRequest,
    WorkerHealthMessage,
)
from aiperf.progress.progress_models import CreditPhaseStartMessage
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.textual_ui import AIPerfTextualUI


def create_sample_data(progress_tracker: ProgressTracker, ui: AIPerfTextualUI):
    """Create sample data for testing the UI."""

    async def simulate_profile_run():
        """Simulate a profile run with sample data."""

        # Start a credit phase
        phase_start_message = CreditPhaseStartMessage(
            profile_id="test-profile",
            phase=CreditPhase.WARMUP,
            total_requests=1000,
            timestamp=time.time(),
        )

        # Add some sample log entries
        ui.add_log_entry(
            time.time(), "INFO", "TestSystem", "Starting profile simulation"
        )
        ui.add_log_entry(time.time(), "INFO", "WorkerManager", "Initializing 3 workers")

        # Create some sample worker health data
        for i in range(3):
            worker_id = f"worker-{i + 1}"
            health_message = WorkerHealthMessage(
                service_id=worker_id,
                process=ProcessInfo(
                    pid=1000 + i,
                    memory_usage=512.0 + i * 128,  # MB
                    cpu_usage=25.0 + i * 15,  # Percentage
                    io_counters=ProcessIOCounters(
                        read_bytes=1024 * 1024 * (i + 1),  # 1MB per worker
                        write_bytes=512 * 1024 * (i + 1),  # 512KB per worker
                        read_chars=2048 * (i + 1),
                        write_chars=1024 * (i + 1),
                    ),
                ),
                task_stats={
                    CreditPhase.WARMUP: TaskStatsRequest(
                        total=100 + i * 50,
                        completed=50 + i * 20,
                        failed=2 + i,
                        in_progress=10 + i * 5,
                    )
                },
                timestamp=time.time(),
            )

            await ui.on_worker_health_update(health_message)

        # Add various log messages
        await asyncio.sleep(1)
        ui.add_log_entry(time.time(), "INFO", "PhaseManager", "Warmup phase started")

        await asyncio.sleep(1)
        ui.add_log_entry(time.time(), "WARNING", "Worker-2", "High CPU usage detected")

        await asyncio.sleep(1)
        ui.add_log_entry(
            time.time(), "INFO", "RequestProcessor", "Processing batch 1/10"
        )

        await asyncio.sleep(1)
        ui.add_log_entry(
            time.time(), "ERROR", "Worker-3", "Connection timeout to model server"
        )

        await asyncio.sleep(1)
        ui.add_log_entry(time.time(), "INFO", "SystemMonitor", "Memory usage: 65%")

        # Continue adding sample data...
        for i in range(10):
            await asyncio.sleep(2)
            ui.add_log_entry(
                time.time(),
                "INFO",
                "BatchProcessor",
                f"Completed batch {i + 2}/10 - {(i + 2) * 100} requests processed",
            )

            # Update some worker stats
            if i % 3 == 0:
                ui.add_log_entry(
                    time.time(),
                    "DEBUG",
                    "SystemMonitor",
                    f"Worker status check {i + 1}",
                )

        ui.add_log_entry(
            time.time(), "INFO", "TestSystem", "Profile simulation completed"
        )

    # Run the simulation in a separate thread
    def run_simulation():
        asyncio.run(simulate_profile_run())

    thread = Thread(target=run_simulation, daemon=True)
    thread.start()


async def main():
    """Main function to run the test."""

    # Set up logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create progress tracker
    progress_tracker = ProgressTracker()

    # Create the cleaned up textual UI
    ui = AIPerfTextualUI(progress_tracker)

    try:
        logger.info("Starting AIPerf Textual UI demo...")

        # Create sample data in the background
        create_sample_data(progress_tracker, ui)

        # Start the UI
        await ui.start()

    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Error running UI: {e}")
    finally:
        # Stop the UI
        await ui.stop()


if __name__ == "__main__":
    print("=== AIPerf Textual UI Demo ===")
    print("This demo shows the cleaned up, emoji-free textual UI.")
    print("Features:")
    print("- Clean, minimal styling")
    print("- No excessive emojis or visual clutter")
    print("- Simple, functional layout")
    print("- Responsive widgets")
    print("- Keyboard shortcuts (F1 for help, F5 to refresh, Ctrl+C to quit)")
    print("=" * 50)

    asyncio.run(main())
