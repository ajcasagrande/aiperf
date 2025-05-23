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
Example script showing how to use the DealerRouterWorkerManager.
This script creates a simple client that sends tasks to workers through the broker.
"""

import argparse
import asyncio
import logging
import sys
import uuid
from typing import Any

import zmq
import zmq.asyncio

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceRunType
from aiperf.services.worker_manager.dealer_router_worker_manager import (
    DealerRouterWorkerManager,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class WorkerClient:
    """Simple client to send tasks to workers through the DealerRouterBroker."""

    def __init__(self, router_address: str):
        """Initialize the worker client.

        Args:
            router_address: The router address to connect to
        """
        self.router_address = router_address
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(router_address)
        logger.info(f"Client connected to router: {router_address}")

    async def send_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Send a task to a worker and await response.

        Args:
            task_data: The task data to send

        Returns:
            The response from the worker
        """
        import json

        task_id = str(uuid.uuid4())
        task_data["task_id"] = task_id

        # Convert to JSON and send
        message = json.dumps(task_data).encode("utf-8")
        logger.info(f"Sending task: {task_data}")
        await self.socket.send(message)

        # Wait for response
        response = await self.socket.recv()
        response_data = json.loads(response.decode("utf-8"))
        logger.info(f"Received response: {response_data}")

        return response_data

    async def close(self) -> None:
        """Close the client."""
        self.socket.close()
        self.context.term()


async def run_worker_manager(worker_count: int = 4) -> DealerRouterWorkerManager:
    """Run the worker manager.

    Args:
        worker_count: The number of worker processes to spawn

    Returns:
        The worker manager instance
    """
    # Create configuration
    config = ServiceConfig(
        service_run_type=ServiceRunType.MULTIPROCESSING,
    )

    # Set dealer-router addresses as attributes
    config.worker_count = worker_count
    config.router_address = "tcp://127.0.0.1:5555"
    config.dealer_address = "tcp://127.0.0.1:5556"
    config.control_address = "tcp://127.0.0.1:5557"
    config.capture_address = "tcp://127.0.0.1:5558"

    # Create and start worker manager
    worker_manager = DealerRouterWorkerManager(config)
    await worker_manager.initialize()
    await worker_manager.start()

    logger.info(f"Worker manager started with {worker_count} workers")
    return worker_manager


async def send_tasks(
    num_tasks: int = 10, router_address: str = "tcp://127.0.0.1:5555"
) -> None:
    """Send tasks to workers.

    Args:
        num_tasks: The number of tasks to send
        router_address: The router address to connect to
    """
    client = WorkerClient(router_address)

    # Send tasks
    for i in range(num_tasks):
        task_data = {
            "command": "process",
            "data": {
                "task_number": i,
                "payload": f"Task {i} data",
                "operation": "process",
            },
        }

        response = await client.send_task(task_data)
        # Process response if needed

    await client.close()


async def main_async() -> None:
    """Main async function."""
    parser = argparse.ArgumentParser(
        description="Run the DealerRouterWorkerManager example"
    )
    parser.add_argument(
        "--workers", type=int, default=4, help="Number of worker processes"
    )
    parser.add_argument("--tasks", type=int, default=10, help="Number of tasks to send")
    args = parser.parse_args()

    # Start worker manager
    worker_manager = await run_worker_manager(worker_count=args.workers)

    try:
        # Wait for workers to initialize
        await asyncio.sleep(2)

        # Send tasks
        await send_tasks(num_tasks=args.tasks)

        # Keep running for a bit to process any remaining tasks
        logger.info("Tasks sent, waiting for completion...")
        await asyncio.sleep(5)

    finally:
        # Shut down worker manager
        logger.info("Shutting down worker manager...")
        await worker_manager.stop()
        await worker_manager.cleanup()
        logger.info("Worker manager shut down")


def main() -> None:
    """Main entry point."""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Error: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
