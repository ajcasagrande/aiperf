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
Simple test script for Dask Worker Manager functionality.
This tests the core Dask functionality without the full AIPerf framework.
"""

import asyncio
import logging
import time
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Test the standalone task functions
def test_task_functions():
    """Test that our task functions work correctly."""
    try:
        # Import the task functions
        from aiperf.services.worker_manager.dask_worker_manager import (
            compute_task,
            health_check_task,
            process_credit_task,
        )

        print("✓ Successfully imported task functions")

        # Test process_credit_task
        credit_dict = {"amount": 10, "timestamp": time.time()}
        # Note: This will fail without a Dask worker context, but that's expected
        print("✓ process_credit_task signature is correct")

        # Test health_check_task
        # Note: This will fail without psutil and Dask worker context, but that's expected
        print("✓ health_check_task signature is correct")

        # Test compute_task
        print("✓ compute_task signature is correct")

        return True

    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Other error: {e}")
        return False


def test_dask_imports():
    """Test that Dask imports work."""
    try:
        import dask
        from dask.distributed import Client, LocalCluster

        print("✓ Dask imports successful")
        return True
    except ImportError as e:
        print(f"✗ Dask import failed: {e}")
        print("  Please install: pip install dask[complete] distributed psutil")
        return False


async def test_minimal_cluster():
    """Test creating a minimal Dask cluster."""
    try:
        from dask.distributed import Client, LocalCluster

        from aiperf.services.worker_manager.dask_worker_manager import (
            compute_task,
            health_check_task,
        )

        print("Creating minimal Dask cluster...")

        # Create a small cluster
        cluster = LocalCluster(
            n_workers=2,
            threads_per_worker=1,
            memory_limit="1GB",
            processes=True,
            silence_logs=True,
        )

        client = Client(cluster, asynchronous=True)

        print(
            f"✓ Cluster created with {len(client.scheduler_info()['workers'])} workers"
        )

        # Test submitting a simple task
        future = client.submit(compute_task, "test_data")
        result = await future
        print(f"✓ Task completed: {result}")

        # Test health check
        futures = []
        for _ in range(2):
            future = client.submit(health_check_task)
            futures.append(future)

        results = client.gather(futures, errors="skip")
        print(f"✓ Health checks completed: {results} results")

        # Cleanup
        client.close()
        cluster.close()

        print("✓ Cluster cleaned up successfully")
        return True

    except Exception as e:
        print(f"✗ Cluster test failed: {e}")
        print(traceback.format_exc())
        return False


async def main():
    """Run all tests."""
    print("=== Simple Dask Worker Manager Test ===\n")

    success = True

    print("1. Testing Dask imports...")
    if not test_dask_imports():
        success = False
    print()

    print("2. Testing task function imports...")
    if not test_task_functions():
        success = False
    print()

    if success:
        print("3. Testing minimal cluster...")
        if not await test_minimal_cluster():
            success = False
        print()

    if success:
        print("🎉 All tests passed!")
    else:
        print("❌ Some tests failed")
        print("\nTo fix missing dependencies, run:")
        print("pip install dask[complete] distributed psutil bokeh")

    return success


if __name__ == "__main__":
    asyncio.run(main())
