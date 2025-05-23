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
Simple ZMQ Dealer-Router test script.
This script demonstrates the basic pattern without using any of the AIPerf infrastructure.
"""

import asyncio
import json
import logging
import multiprocessing
import random
import sys
import time
import uuid
from typing import Any

import zmq
import zmq.asyncio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class SimpleDealer:
    """Simple dealer client that processes tasks."""

    def __init__(self, dealer_address: str, worker_id: str | None = None):
        """Initialize the dealer client.

        Args:
            dealer_address: The dealer address to connect to
            worker_id: Optional worker ID
        """
        self.dealer_address = dealer_address
        self.worker_id = worker_id or f"worker-{uuid.uuid4()}"
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.setsockopt(zmq.IDENTITY, self.worker_id.encode())
        self.running = False
        logger.info(f"Created dealer {self.worker_id}")

    async def connect(self):
        """Connect to the dealer socket."""
        self.socket.connect(self.dealer_address)
        logger.info(f"Dealer {self.worker_id} connected to {self.dealer_address}")

    async def run(self):
        """Run the dealer client."""
        self.running = True
        logger.info(f"Starting dealer {self.worker_id}")

        while self.running:
            try:
                # Receive task
                logger.info(f"Dealer {self.worker_id} waiting for task...")
                frames = await self.socket.recv_multipart()

                # Process frames
                if len(frames) >= 2:
                    # Last frame is the actual data
                    data = frames[-1]
                    task_data = json.loads(data.decode("utf-8"))
                    logger.info(f"Dealer {self.worker_id} received task: {task_data}")

                    # Simulate processing
                    process_time = random.uniform(0.5, 2.0)
                    logger.info(
                        f"Dealer {self.worker_id} processing for {process_time:.2f}s"
                    )
                    await asyncio.sleep(process_time)

                    # Send response back
                    response = {
                        "task_id": task_data.get("task_id", "unknown"),
                        "worker_id": self.worker_id,
                        "result": f"Processed by {self.worker_id}",
                        "process_time": process_time,
                        "timestamp": time.time(),
                    }

                    # Maintain the same envelope structure
                    response_frames = frames[:-1]
                    response_frames.append(json.dumps(response).encode("utf-8"))
                    await self.socket.send_multipart(response_frames)
                    logger.info(f"Dealer {self.worker_id} sent response")
                else:
                    logger.warning(
                        f"Dealer {self.worker_id} received malformed message"
                    )

            except Exception as e:
                logger.error(f"Dealer {self.worker_id} error: {e}")
                await asyncio.sleep(1)

    async def close(self):
        """Close the dealer client."""
        self.running = False
        if self.socket:
            self.socket.close()
        self.context.term()
        logger.info(f"Dealer {self.worker_id} closed")


class SimpleBroker:
    """Simple broker that connects router to dealer."""

    def __init__(self, router_address: str, dealer_address: str):
        """Initialize the broker.

        Args:
            router_address: The router address to bind to
            dealer_address: The dealer address to bind to
        """
        self.router_address = router_address
        self.dealer_address = dealer_address
        self.context = zmq.asyncio.Context()
        self.router = self.context.socket(zmq.ROUTER)
        self.dealer = self.context.socket(zmq.DEALER)
        self.running = False
        logger.info(
            f"Created broker with router={router_address}, dealer={dealer_address}"
        )

    async def start(self):
        """Start the broker."""
        self.router.bind(self.router_address)
        self.dealer.bind(self.dealer_address)
        logger.info(
            f"Broker bound to router={self.router_address}, dealer={self.dealer_address}"
        )

        self.running = True

        # Create proxy between router and dealer
        async def proxy_frontend_to_backend():
            while self.running:
                try:
                    message = await self.router.recv_multipart()
                    logger.info(f"Broker received from router: {len(message)} frames")
                    await self.dealer.send_multipart(message)
                except Exception as e:
                    logger.error(f"Broker frontend-to-backend error: {e}")
                    if not self.running:
                        break
                    await asyncio.sleep(0.1)

        async def proxy_backend_to_frontend():
            while self.running:
                try:
                    message = await self.dealer.recv_multipart()
                    logger.info(f"Broker received from dealer: {len(message)} frames")
                    await self.router.send_multipart(message)
                except Exception as e:
                    logger.error(f"Broker backend-to-frontend error: {e}")
                    if not self.running:
                        break
                    await asyncio.sleep(0.1)

        # Start proxy tasks
        asyncio.create_task(proxy_frontend_to_backend())
        asyncio.create_task(proxy_backend_to_frontend())

        logger.info("Broker started")

    async def stop(self):
        """Stop the broker."""
        self.running = False

        # Close sockets
        if self.router:
            self.router.close()
        if self.dealer:
            self.dealer.close()

        # Term context
        self.context.term()
        logger.info("Broker stopped")


class SimpleClient:
    """Simple client that sends requests to the router."""

    def __init__(self, router_address: str, client_id: str = None):
        """Initialize the client.

        Args:
            router_address: The router address to connect to
            client_id: Optional client ID
        """
        self.router_address = router_address
        self.client_id = client_id or f"client-{uuid.uuid4()}"
        self.context = zmq.asyncio.Context()
        self.socket = self.context.socket(zmq.REQ)
        logger.info(f"Created client {self.client_id}")

    async def connect(self):
        """Connect to the router socket."""
        self.socket.connect(self.router_address)
        logger.info(f"Client {self.client_id} connected to {self.router_address}")

    async def send_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Send a task to a worker and await response.

        Args:
            task_data: The task data to send

        Returns:
            The response from the worker
        """
        task_id = str(uuid.uuid4())
        task_data["task_id"] = task_id
        task_data["client_id"] = self.client_id

        # Convert to JSON and send
        message = json.dumps(task_data).encode("utf-8")
        logger.info(f"Client {self.client_id} sending task: {task_data}")
        await self.socket.send(message)

        # Wait for response
        response = await self.socket.recv()
        response_data = json.loads(response.decode("utf-8"))
        logger.info(f"Client {self.client_id} received response: {response_data}")

        return response_data

    async def close(self):
        """Close the client."""
        if self.socket:
            self.socket.close()
        self.context.term()
        logger.info(f"Client {self.client_id} closed")


def run_dealer_worker(dealer_address: str, worker_id: str):
    """Run a dealer worker in a separate process.

    Args:
        dealer_address: The dealer address to connect to
        worker_id: The worker ID
    """

    async def run():
        dealer = SimpleDealer(dealer_address, worker_id)
        await dealer.connect()
        try:
            await dealer.run()
        except KeyboardInterrupt:
            logger.info(f"Worker {worker_id} interrupted")
        finally:
            await dealer.close()

    # Run the dealer worker
    asyncio.run(run())


async def run_test():
    """Run a test with a broker, multiple dealers, and a client."""
    router_address = "tcp://127.0.0.1:5555"
    dealer_address = "tcp://127.0.0.1:5556"
    num_workers = 3
    num_tasks = 5

    # Start the broker
    broker = SimpleBroker(router_address, dealer_address)
    await broker.start()

    # Start dealer workers in separate processes
    workers = []
    for i in range(num_workers):
        worker_id = f"worker-{i}"
        process = multiprocessing.Process(
            target=run_dealer_worker,
            args=(dealer_address, worker_id),
            daemon=True,
        )
        process.start()
        workers.append((worker_id, process))
        logger.info(f"Started worker process {worker_id} (pid: {process.pid})")

    # Wait for workers to initialize
    await asyncio.sleep(1)

    # Start a client and send tasks
    client = SimpleClient(router_address)
    await client.connect()

    try:
        # Send tasks
        for i in range(num_tasks):
            task = {
                "command": "process",
                "data": {
                    "task_number": i,
                    "content": f"Task {i} data",
                },
            }
            response = await client.send_task(task)
            logger.info(f"Task {i} completed by {response['worker_id']}")

        # Wait a bit to ensure all tasks are processed
        logger.info("All tasks sent, waiting for completion...")
        await asyncio.sleep(2)

    finally:
        # Close the client
        await client.close()

        # Stop the broker
        await broker.stop()

        # Terminate worker processes
        for worker_id, process in workers:
            logger.info(f"Terminating worker {worker_id}")
            process.terminate()

        # Wait for workers to terminate
        for worker_id, process in workers:
            process.join(timeout=1.0)
            if process.is_alive():
                logger.warning(f"Worker {worker_id} did not terminate, killing")
                process.kill()
            else:
                logger.info(f"Worker {worker_id} terminated")


def main():
    """Main entry point."""
    try:
        asyncio.run(run_test())
        return 0
    except KeyboardInterrupt:
        logger.info("Test interrupted")
        return 1
    except Exception as e:
        logger.exception(f"Test error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
