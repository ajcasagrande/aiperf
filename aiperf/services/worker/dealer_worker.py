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
ZMQ Dealer Worker for use with the DealerRouterWorkerManager.
This worker connects to a Dealer socket and processes tasks.
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from typing import Any

import zmq
import zmq.asyncio

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.decorators import (
    on_cleanup,
    on_init,
    on_run,
    on_start,
    on_stop,
)
from aiperf.common.enums import ClientType, ServiceType
from aiperf.common.service.base_service import BaseService


class DealerWorker(BaseService):
    """Worker that connects to a Dealer socket to receive tasks from a Router-Dealer broker."""

    def __init__(
        self, service_config: ServiceConfig, service_id: str | None = None
    ) -> None:
        """Initialize the dealer worker.

        Args:
            service_config: The service configuration
            service_id: The service ID
        """
        super().__init__(service_config=service_config, service_id=service_id)

        # Worker ID
        self.worker_id = service_id or f"worker_{os.getpid()}_{str(uuid.uuid4())[:8]}"
        self.logger.info(f"Initializing dealer worker {self.worker_id}")

        # ZMQ setup
        self.context = zmq.asyncio.Context()
        self.socket = None
        self.dealer_address = getattr(
            self.service_config, "dealer_address", "tcp://127.0.0.1:5556"
        )

        # Worker state
        self.running = False
        self.task_count = 0

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER

    @property
    def required_clients(self) -> list[ClientType]:
        """The communication clients required by the service."""
        return []

    @on_init
    async def _initialize(self) -> None:
        """Initialize the worker."""
        self.logger.debug(f"Initializing dealer worker {self.worker_id}")

        # Create socket
        self.socket = self.context.socket(zmq.DEALER)
        self.socket.setsockopt(zmq.IDENTITY, self.worker_id.encode())
        self.socket.connect(self.dealer_address)
        self.logger.info(
            f"Worker {self.worker_id} connected to dealer: {self.dealer_address}"
        )

    @on_start
    async def _start(self) -> None:
        """Start the worker."""
        self.logger.debug(f"Starting dealer worker {self.worker_id}")
        self.running = True

    @on_run
    async def _run(self) -> None:
        """Run the worker's main processing loop."""
        self.logger.info(f"Worker {self.worker_id} starting processing loop")

        while self.running:
            try:
                # Receive task (multipart message with empty delimiter frame)
                if self.socket:
                    frames = await self.socket.recv_multipart()

                    # Process frames (typically [identity, empty, data])
                    if len(frames) >= 3:
                        # Extract actual data (typically the last frame)
                        data = frames[-1]
                        task_data = json.loads(data.decode("utf-8"))

                        # Process the task
                        self.task_count += 1
                        self.logger.info(
                            f"Worker {self.worker_id} processing task {self.task_count}: {task_data}"
                        )
                        result = await self._process_task(task_data)

                        # Send response back (maintaining the same envelope structure)
                        if self.socket:
                            response_frames = frames[:-1]  # All except the last frame
                            response_frames.append(json.dumps(result).encode("utf-8"))
                            await self.socket.send_multipart(response_frames)
                    else:
                        self.logger.warning(
                            f"Received malformed message, frames: {len(frames)}"
                        )
                else:
                    self.logger.warning("Socket is None, cannot receive messages")
                    await asyncio.sleep(1)

            except zmq.ZMQError as e:
                self.logger.error(f"ZMQ error: {e}")
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.exception(f"Error processing task: {e}")
                await asyncio.sleep(1)

    async def _process_task(self, task_data: dict[str, Any]) -> dict[str, Any]:
        """Process a task.

        Args:
            task_data: The task data to process

        Returns:
            The processed result
        """
        # Simulate processing time
        await asyncio.sleep(0.5)

        # Process based on task command
        command = task_data.get("command", "unknown")

        if command == "process":
            # Example processing logic
            task_number = task_data.get("data", {}).get("task_number", 0)
            result = {
                "task_id": task_data.get("task_id", "unknown"),
                "worker_id": self.worker_id,
                "result": f"Processed task {task_number} by worker {self.worker_id}",
                "timestamp": time.time(),
                "status": "success",
            }
        else:
            # Unknown command
            result = {
                "task_id": task_data.get("task_id", "unknown"),
                "worker_id": self.worker_id,
                "error": f"Unknown command: {command}",
                "timestamp": time.time(),
                "status": "error",
            }

        return result

    @on_stop
    async def _stop(self) -> None:
        """Stop the worker."""
        self.logger.debug(f"Stopping dealer worker {self.worker_id}")
        self.running = False

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up worker resources."""
        self.logger.debug(f"Cleaning up dealer worker {self.worker_id}")
        if self.socket:
            self.socket.close()
        self.context.term()


def run_worker(config: ServiceConfig, worker_id: str | None = None) -> None:
    """Run a dealer worker with the given configuration.

    Args:
        config: The service configuration
        worker_id: Optional worker ID
    """
    try:
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

        # Create and run worker
        worker = DealerWorker(config, service_id=worker_id)
        asyncio.run(worker.run_forever())
    except KeyboardInterrupt:
        print("Worker interrupted by user")
    except Exception as e:
        print(f"Worker error: {e}")
        sys.exit(1)


def main() -> None:
    """Main entry point for running a dealer worker."""
    from aiperf.common.config.loader import load_service_config

    # Load configuration
    config = load_service_config()

    # Run worker
    run_worker(config)


if __name__ == "__main__":
    sys.exit(main())
