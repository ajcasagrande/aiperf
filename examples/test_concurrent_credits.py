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
Test script to verify concurrent credit processing.
This tests that credits are processed concurrently, not sequentially.
"""

import asyncio
import logging
import time

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceRunType
from aiperf.common.models import CreditDropMessage, CreditDropPayload
from aiperf.services.worker_manager.dask_worker_manager import (
    DaskWorkerConfig,
    DaskWorkerManager,
    ScalingStrategy,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_concurrent_credit_processing():
    """Test that credits are processed concurrently."""
    logger.info("=== Testing Concurrent Credit Processing ===")

    # Configure for fast processing
    config = DaskWorkerConfig(
        min_workers=3,
        max_workers=3,
        initial_workers=3,
        scaling_strategy=ScalingStrategy.MANUAL,
        heartbeat_interval=1,
        dashboard_port=8788,  # Different port to avoid conflicts
    )

    service_config = ServiceConfig(service_run_type=ServiceRunType.MULTIPROCESSING)
    manager = DaskWorkerManager(service_config=service_config, config=config)

    try:
        await manager.initialize()
        await manager.start()

        # Wait for cluster to be ready
        await asyncio.sleep(2)

        logger.info("Submitting 5 credits rapidly...")

        # Record start time
        start_time = time.time()

        # Submit 5 credits very quickly
        for i in range(5):
            credit_payload = CreditDropPayload(amount=i + 1, timestamp=time.time_ns())
            credit_message = CreditDropMessage(payload=credit_payload)
            await manager._on_credit_drop(credit_message)
            logger.info(f"Queued credit {i + 1}")

        submission_time = time.time() - start_time
        logger.info(f"All credits queued in {submission_time:.3f}s")

        # Monitor processing
        processing_start = time.time()
        processed_count = 0

        while True:
            status = await manager.get_cluster_status()
            metrics = status["cluster_metrics"]

            current_processed = metrics.completed_tasks + metrics.failed_tasks

            if current_processed > processed_count:
                processing_time = time.time() - processing_start
                logger.info(
                    f"Credit {current_processed} completed at {processing_time:.3f}s"
                )
                processed_count = current_processed

            # Check if all are done
            if (
                metrics.pending_tasks == 0
                and metrics.queue_length == 0
                and processed_count >= 5
            ):
                break

            await asyncio.sleep(0.1)

        total_time = time.time() - processing_start

        logger.info("=== Results ===")
        logger.info(f"Total processing time: {total_time:.3f}s")
        logger.info(f"Completed: {metrics.completed_tasks}")
        logger.info(f"Failed: {metrics.failed_tasks}")

        # Analysis
        if total_time < 1.0:  # If processed in under 1 second, it's concurrent
            logger.info("✓ CONCURRENT: Credits processed in parallel!")
        elif total_time > 4.0:  # If took more than 4 seconds, likely sequential
            logger.info("✗ SEQUENTIAL: Credits appear to be processed one by one")
        else:
            logger.info("? UNCLEAR: Processing time suggests mixed behavior")

        return total_time < 1.0

    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False

    finally:
        await manager.stop()


if __name__ == "__main__":
    success = asyncio.run(test_concurrent_credit_processing())
    if success:
        print("\n🎉 Concurrent processing test PASSED!")
    else:
        print("\n❌ Concurrent processing test FAILED!")
        print("Credits may be processing sequentially instead of concurrently.")
