#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
AIPerf Split-Screen UI Demo

This demo shows how the split-screen UI captures and displays logs from multiple processes.
Run this to see the UI in action with simulated services.
"""

import asyncio
import logging
import multiprocessing
import random
import time
from multiprocessing import Process

from aiperf.common.ui import AIPerfUI, setup_child_process_logging


def worker_process(worker_id: int, log_queue: multiprocessing.Queue):
    """Simulate a worker process that generates logs."""
    # Set up logging to send to main process
    setup_child_process_logging(log_queue)

    logger = logging.getLogger(f"worker_{worker_id}")

    logger.info(f"Worker {worker_id} starting up")

    for i in range(10):
        time.sleep(random.uniform(0.5, 2.0))

        # Generate different types of logs
        log_type = random.choice(["info", "debug", "warning", "error"])

        if log_type == "info":
            logger.info(f"Worker {worker_id} processed request {i + 1}")
        elif log_type == "debug":
            logger.debug(f"Worker {worker_id} debug info for request {i + 1}")
        elif log_type == "warning":
            logger.warning(f"Worker {worker_id} slow response on request {i + 1}")
        elif log_type == "error":
            logger.error(f"Worker {worker_id} failed to process request {i + 1}")

    logger.info(f"Worker {worker_id} shutting down")


async def simulate_progress_updates(ui: AIPerfUI):
    """Simulate progress updates for the dashboard."""
    from aiperf.common.messages import ProfileProgressMessage, ProfileStatsMessage

    total_requests = 100

    for completed in range(total_requests + 1):
        # Simulate progress message
        progress_msg = ProfileProgressMessage(
            service_id="demo_service",
            total=total_requests,
            completed=completed,
            sweep_start_ns=time.perf_counter_ns()
            - (completed * 100_000_000),  # 100ms per request
            request_ns=time.perf_counter_ns(),
        )
        ui.update_profile_progress(progress_msg)

        # Simulate stats message every 10 requests
        if completed % 10 == 0:
            error_count = random.randint(0, max(1, completed // 10))
            stats_msg = ProfileStatsMessage(
                service_id="demo_service", error_count=error_count, completed=completed
            )
            ui.update_profile_stats(stats_msg)

        await asyncio.sleep(0.2)  # 200ms between updates


async def main():
    """Main demo function."""
    print("🚀 Starting AIPerf Split-Screen UI Demo")
    print("This will show progress dashboard + real-time logs from multiple processes")
    print("Press Ctrl+C to stop\n")

    # Initialize UI
    ui = AIPerfUI.get_instance()
    await ui.initialize()

    # Set up multiprocess logging
    log_queue = ui.setup_multiprocess_logging()

    await ui.start()

    # Spawn some worker processes that will generate logs
    workers = []
    for i in range(3):
        worker = Process(
            target=worker_process, args=(i + 1, log_queue), name=f"demo_worker_{i + 1}"
        )
        worker.start()
        workers.append(worker)

    # Generate some logs from the main process
    main_logger = logging.getLogger("demo_main")
    main_logger.info("Demo started - spawned 3 worker processes")

    try:
        # Simulate progress updates
        await simulate_progress_updates(ui)

        # Wait for workers to finish
        for worker in workers:
            worker.join()

        main_logger.info("All workers completed")

        # Show final results
        await asyncio.sleep(2)  # Let final logs appear

    except KeyboardInterrupt:
        main_logger.info("Demo interrupted by user")

        # Terminate workers
        for worker in workers:
            if worker.is_alive():
                worker.terminate()
                worker.join()

    finally:
        await ui.stop()
        print("\n✅ Demo completed!")


if __name__ == "__main__":
    # Set logging level
    logging.root.setLevel(logging.DEBUG)

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Demo stopped by user")
