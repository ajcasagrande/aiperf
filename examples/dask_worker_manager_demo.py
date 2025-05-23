#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
# 
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
# 
#  http://www.apache.org/licenses/LICENSE-2.0
# 
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""
Demonstration script for the AIPerf Dask Worker Manager.

This script shows how to:
1. Initialize and configure the DaskWorkerManager
2. Submit tasks for processing
3. Monitor cluster metrics
4. Dynamically scale workers up and down
5. Handle different scaling strategies

Run with: python examples/dask_worker_manager_demo.py
"""

import asyncio
import logging
import time

from distributed.comm.core import CommClosedError

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceRunType
from aiperf.common.models import CreditDropMessage, CreditDropPayload
from aiperf.services.worker_manager.dask_worker_manager import (
    DaskWorkerConfig,
    DaskWorkerManager,
    ScalingStrategy,
    WorkerResourceProfile,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def demo_basic_usage():
    """Demonstrate basic DaskWorkerManager usage."""
    logger.info("=== Basic Usage Demo ===")

    # Create configuration
    config = DaskWorkerConfig(
        min_workers=2,
        max_workers=8,
        initial_workers=3,
        scaling_strategy=ScalingStrategy.MANUAL,
        worker_profile=WorkerResourceProfile.SMALL,
        threads_per_worker=2,
        memory_limit="2GB",
    )

    # Create service config (simplified)
    service_config = ServiceConfig(
        service_run_type=ServiceRunType.MULTIPROCESSING,
        # Add other required fields as needed
    )

    # Initialize worker manager
    manager = DaskWorkerManager(
        service_config=service_config,
        config=config,
    )

    try:
        # Initialize and start using proper service lifecycle
        await manager.initialize()
        await manager.start()

        # Get initial status
        status = await manager.get_cluster_status()
        logger.info(f"Initial cluster status: {status['cluster_metrics']}")

        # Submit some test tasks
        logger.info("Submitting test tasks...")
        task_keys = []
        for i in range(5):
            key = await manager.submit_task("compute", f"test_data_{i}")
            task_keys.append(key)
            logger.info(f"Submitted task {i + 1}/5: {key}")

        # Wait a bit for processing
        await asyncio.sleep(3)

        # Check final status
        final_status = await manager.get_cluster_status()
        logger.info(f"Final cluster status: {final_status['cluster_metrics']}")

    finally:
        # Clean shutdown
        await manager.stop()


async def demo_auto_scaling():
    """Demonstrate automatic scaling functionality."""
    logger.info("=== Auto Scaling Demo ===")

    config = DaskWorkerConfig(
        min_workers=1,
        max_workers=6,
        initial_workers=2,
        scaling_strategy=ScalingStrategy.AUTO_ADAPTIVE,
        scale_up_threshold=0.7,
        scale_down_threshold=0.3,
        scaling_interval=10,  # Scale every 10 seconds
        heartbeat_interval=5,  # Check metrics every 5 seconds
    )

    service_config = ServiceConfig(service_run_type=ServiceRunType.MULTIPROCESSING)

    manager = DaskWorkerManager(
        service_config=service_config,
        config=config,
    )

    try:
        await manager.initialize()
        await manager.start()

        logger.info("Starting with adaptive scaling...")
        await asyncio.sleep(2)

        # Simulate high load
        logger.info("Simulating high load with many tasks...")
        for i in range(15):
            await manager.submit_task("compute", f"load_test_{i}")

        # Monitor for 30 seconds
        start_time = time.time()
        while time.time() - start_time < 30:
            status = await manager.get_cluster_status()
            metrics = status["cluster_metrics"]

            logger.info(
                f"Workers: {metrics.active_workers}, "
                f"Pending: {metrics.pending_tasks}, "
                f"Queue: {metrics.queue_length}, "
                f"CPU: {metrics.cpu_utilization:.1f}%"
            )

            await asyncio.sleep(5)

    finally:
        await manager.stop()


async def demo_credit_processing():
    """Demonstrate credit drop processing."""
    logger.info("=== Credit Processing Demo ===")

    config = DaskWorkerConfig(
        # min_workers=1,
        # max_workers=250,
        # initial_workers=10,
        scaling_strategy=ScalingStrategy.AUTO_QUEUE,
        heartbeat_interval=1,  # More frequent monitoring
    )

    service_config = ServiceConfig(service_run_type=ServiceRunType.MULTIPROCESSING)

    manager = DaskWorkerManager(
        service_config=service_config,
        config=config,
    )

    try:
        await manager.initialize()
        await manager.start()

        # Wait for cluster to be ready
        await asyncio.sleep(1)

        # Simulate credit drops rapidly to test concurrency
        logger.info("Simulating rapid credit drops...")

        # Submit all credits quickly to test concurrent processing
        for i in range(10):
            credit_payload = CreditDropPayload(
                amount=i + 1,  # Different amounts to track processing
                timestamp=time.time_ns(),
            )

            # Create a proper CreditDropMessage
            credit_message = CreditDropMessage(payload=credit_payload)

            await manager._on_credit_drop(credit_message)
            logger.info(f"Queued credit drop {i + 1}/10 (amount: {i + 1})")

            # Very short sleep to queue them rapidly
            await asyncio.sleep(0.01)

        # Monitor processing in real-time
        logger.info("Monitoring concurrent processing...")

        check = 0
        while True:  # Monitor for 12 seconds
            status = await manager.get_cluster_status()
            metrics = status["cluster_metrics"]

            logger.info(
                f"[{check + 1:2d}s] Completed: {metrics.completed_tasks:2d}, "
                f"Failed: {metrics.failed_tasks:2d}, "
                f"Pending: {metrics.pending_tasks:2d}, "
                f"Queue: {metrics.queue_length:2d}"
            )

            # Stop monitoring if all tasks are done
            if (
                metrics.pending_tasks == 0
                and metrics.queue_length == 0
                and metrics.completed_tasks >= 10
            ):
                logger.info("✓ All credits processed!")
                break

            check += 1
            if metrics.pending_tasks == 0 and metrics.queue_length == 0:
                break
            await asyncio.sleep(0.1)

        # Final status
        final_status = await manager.get_cluster_status()
        final_metrics = final_status["cluster_metrics"]

        logger.info("=== Final Results ===")
        logger.info(f"Total Completed: {final_metrics.completed_tasks}")
        logger.info(f"Total Failed: {final_metrics.failed_tasks}")
        logger.info(f"Remaining Pending: {final_metrics.pending_tasks}")
        logger.info(f"Queue Length: {final_metrics.queue_length}")

    finally:
        await manager.stop()


async def demo_manual_scaling():
    """Demonstrate manual scaling operations."""
    logger.info("=== Manual Scaling Demo ===")

    config = DaskWorkerConfig(
        min_workers=1,
        max_workers=10,
        initial_workers=2,
        scaling_strategy=ScalingStrategy.MANUAL,
    )

    service_config = ServiceConfig(service_run_type=ServiceRunType.MULTIPROCESSING)

    manager = DaskWorkerManager(
        service_config=service_config,
        config=config,
    )

    try:
        await manager.initialize()
        await manager.start()

        # Initial status
        status = await manager.get_cluster_status()
        logger.info(f"Starting workers: {status['cluster_metrics'].active_workers}")

        # Scale up manually
        logger.info("Scaling up to 5 workers...")
        await manager._scale_up(3)
        await asyncio.sleep(3)

        status = await manager.get_cluster_status()
        logger.info(f"After scale up: {status['cluster_metrics'].active_workers}")

        # Scale down manually
        logger.info("Scaling down to 2 workers...")
        await manager._scale_down(3)
        await asyncio.sleep(3)

        status = await manager.get_cluster_status()
        logger.info(f"After scale down: {status['cluster_metrics'].active_workers}")

    finally:
        await manager.stop()


async def main():
    """Run all demonstrations."""
    logger.info("Starting Dask Worker Manager Demonstrations")

    try:
        # await demo_basic_usage()
        # await asyncio.sleep(2)

        # await demo_manual_scaling()
        # await asyncio.sleep(2)

        await demo_credit_processing()
        # await asyncio.sleep(2)

        # # Note: Auto scaling demo last as it takes longer
        # await demo_auto_scaling()

    except CommClosedError:
        logger.error("CommClosedError")
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise

    logger.info("All demonstrations completed successfully!")


if __name__ == "__main__":
    # Install dependencies note
    try:
        import dask
        import psutil
    except ImportError:
        print("Missing dependencies. Please install:")
        print("pip install -r requirements-dask.txt")
        exit(1)

    # Run the demo
    asyncio.run(main())
