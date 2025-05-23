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
import asyncio
import logging
import multiprocessing
import os
import sys
import uuid
from typing import Any

import zmq
import zmq.asyncio
from pydantic import BaseModel, Field

from aiperf.common.bootstrap import bootstrap_and_run_service
from aiperf.common.comms.zmq.clients.dealer_router import DealerRouterBroker
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.decorators import (
    on_cleanup,
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.enums import ServiceRunType, ServiceType
from aiperf.common.exceptions.comms import CommunicationError
from aiperf.common.exceptions.config import ConfigError
from aiperf.common.models.payload import BasePayload
from aiperf.common.service.base_component_service import BaseComponentService


class WorkerProcess(BaseModel):
    """Information about a worker process."""

    worker_id: str = Field(..., description="ID of the worker process")
    process: Any = Field(None, description="Process object or task")


class DealerRouterWorkerManager(BaseComponentService):
    """
    The DealerRouterWorkerManager service uses ZMQ's Dealer-Router pattern to manage worker processes.
    It acts as a broker between clients and workers, distributing work efficiently across multiple processes.

    This implementation uses:
    - DealerRouterBroker for ZMQ communication
    - Multiprocessing for worker process management
    - Asyncio for asynchronous coordination
    """

    def __init__(
        self, service_config: ServiceConfig, service_id: str | None = None
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing DealerRouterWorkerManager")
        self.workers: dict[str, WorkerProcess] = {}

        # Default to CPU count minus 1 for worker count, can be overridden in config
        self.cpu_count = multiprocessing.cpu_count()
        self.worker_count = getattr(
            self.service_config, "worker_count", self.cpu_count - 1
        )
        self.logger.debug(
            f"Detected {self.cpu_count} CPU threads. Will spawn {self.worker_count} workers"
        )

        # ZMQ Context
        self.context = zmq.asyncio.Context()

        # Generate unique IDs for broker addresses
        self._broker_id = str(uuid.uuid4())

        # Dealer-Router broker configuration
        self.router_address = getattr(
            self.service_config, "router_address", "tcp://127.0.0.1:5555"
        )
        self.dealer_address = getattr(
            self.service_config, "dealer_address", "tcp://127.0.0.1:5556"
        )
        self.control_address = getattr(
            self.service_config, "control_address", "tcp://127.0.0.1:5557"
        )
        self.capture_address = getattr(
            self.service_config, "capture_address", "tcp://127.0.0.1:5558"
        )

        self.broker: DealerRouterBroker | None = None
        self.broker_task: asyncio.Task | None = None

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER_MANAGER

    @on_init
    async def _initialize(self) -> None:
        """Initialize worker manager-specific components."""
        self.logger.debug("Initializing DealerRouterWorkerManager")

        # Create the broker
        self.broker = DealerRouterBroker(
            context=self.context,
            router_address=self.router_address,
            dealer_address=self.dealer_address,
            control_address=self.control_address,
            capture_address=self.capture_address,
        )

    @on_start
    async def _start(self) -> None:
        """Start the worker manager and broker."""
        self.logger.debug("Starting DealerRouterWorkerManager")

        # Start the broker in a separate task
        self.broker_task = asyncio.create_task(self._run_broker())

        # Wait for broker to initialize
        await asyncio.sleep(1)

        # Spawn workers based on run type
        if self.service_config.service_run_type == ServiceRunType.MULTIPROCESSING:
            await self._spawn_multiprocessing_workers()
        elif self.service_config.service_run_type == ServiceRunType.KUBERNETES:
            await self._spawn_kubernetes_workers()
        else:
            self.logger.warning(
                f"Unsupported run type: {self.service_config.service_run_type}"
            )
            raise ConfigError(
                f"Unsupported run type: {self.service_config.service_run_type}"
            )

    async def _run_broker(self) -> None:
        """Run the DealerRouterBroker."""
        self.logger.info(
            f"Starting ZMQ broker with router: {self.router_address}, dealer: {self.dealer_address}"
        )
        try:
            if self.broker:
                await self.broker.run()
            else:
                self.logger.error("Broker is not initialized")
        except Exception as e:
            self.logger.error(f"Error in broker: {e}")
            raise CommunicationError(f"Broker failed: {e}") from e

    @on_stop
    async def _stop(self) -> None:
        """Stop the worker manager."""
        self.logger.debug("Stopping DealerRouterWorkerManager")

        # Stop all workers
        if self.service_config.service_run_type == ServiceRunType.MULTIPROCESSING:
            await self._stop_multiprocessing_workers()
        elif self.service_config.service_run_type == ServiceRunType.KUBERNETES:
            await self._stop_kubernetes_workers()

        # Cancel broker task
        if self.broker_task:
            self.broker_task.cancel()
            try:
                await self.broker_task
            except asyncio.CancelledError:
                self.logger.debug("Broker task cancelled")

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up worker manager-specific components."""
        self.logger.debug("Cleaning up DealerRouterWorkerManager")
        self.workers.clear()

        # Clean up ZMQ context
        self.context.term()

    async def _spawn_kubernetes_workers(self) -> None:
        """Spawn worker processes using Kubernetes."""
        self.logger.debug(
            f"Spawning {self.worker_count} worker processes in Kubernetes"
        )

        # TODO: Implement Kubernetes start
        raise NotImplementedError("Kubernetes start not implemented")

    async def _stop_kubernetes_workers(self) -> None:
        """Stop worker processes using Kubernetes."""
        self.logger.debug("Stopping all worker processes in Kubernetes")

        # TODO: Implement Kubernetes stop
        raise NotImplementedError("Kubernetes stop not implemented")

    async def _spawn_multiprocessing_workers(self) -> None:
        """Spawn worker processes using multiprocessing with dealer clients."""
        self.logger.debug(f"Spawning {self.worker_count} worker processes")

        for i in range(self.worker_count):
            worker_id = f"worker_{i}"

            # Pass ZMQ configuration to the worker
            worker_config = self.service_config

            # Create a dictionary with dealer address and worker ID
            dealer_config = {
                "dealer_address": self.dealer_address,
                "worker_id": worker_id,
            }

            # Start the worker process
            process = multiprocessing.Process(
                target=self._run_worker_process,
                name=f"worker_{i}_process",
                args=(worker_config, dealer_config),
                daemon=True,
            )
            process.start()

            self.workers[worker_id] = WorkerProcess(
                worker_id=worker_id, process=process
            )
            self.logger.debug(
                f"Started worker process {worker_id} (pid: {process.pid})"
            )

    def _run_worker_process(
        self, worker_config: ServiceConfig, dealer_config: dict
    ) -> None:
        """Run a worker process with ZMQ dealer client.

        Args:
            worker_config: The service configuration
            dealer_config: Dealer-specific configuration dictionary
        """
        try:
            # Configure process-specific logging
            worker_id = dealer_config.get("worker_id", f"worker_{os.getpid()}")
            dealer_address = dealer_config.get("dealer_address", "tcp://127.0.0.1:5556")

            # Configure process-specific logging
            logging.basicConfig(
                level=logging.INFO,
                format=f"%(asctime)s - {worker_id} - %(levelname)s - %(message)s",
            )

            # Set dealer address in the process
            worker_config.dealer_address = dealer_address

            # Import and run the worker with the dealer client
            import uvloop

            from aiperf.services.worker.dealer_worker import DealerWorker

            # Create a worker with dealer connection
            worker_instance = DealerWorker(worker_config, service_id=worker_id)

            # Run with uvloop for better performance
            uvloop.install()
            asyncio.run(worker_instance.run_forever())
        except Exception as e:
            print(f"Worker process error: {e}")
            sys.exit(1)

    async def _stop_multiprocessing_workers(self) -> None:
        """Stop all multiprocessing worker processes."""
        self.logger.debug("Stopping all worker processes")

        # First terminate all processes
        for worker_id, worker_info in self.workers.items():
            self.logger.debug(f"Stopping worker process {worker_id}")
            process = worker_info.process
            if process and process.is_alive():
                self.logger.debug(
                    f"Terminating worker process {worker_id} (pid: {process.pid})"
                )
                process.terminate()

        # Then wait for all to finish
        await asyncio.gather(
            *[
                self._wait_for_process(worker_id, worker_info.process)
                for worker_id, worker_info in self.workers.items()
                if worker_info.process
            ]
        )

        self.logger.debug("All worker processes stopped")

    async def _wait_for_process(
        self, worker_id: str, process: multiprocessing.Process
    ) -> None:
        """Wait for a process to terminate with timeout handling."""
        try:
            await asyncio.wait_for(
                asyncio.to_thread(process.join, timeout=1.0),  # Add timeout to join
                timeout=5.0,  # Overall timeout
            )
            self.logger.debug(
                f"Worker process {worker_id} (pid: {process.pid}) stopped"
            )
        except asyncio.TimeoutError:
            self.logger.warning(
                f"Worker process {worker_id} (pid: {process.pid}) did not "
                f"terminate gracefully, killing"
            )
            process.kill()

    @on_configure
    async def _configure(self, payload: BasePayload) -> None:
        """Configure the worker manager."""
        self.logger.debug(
            f"Configuring DealerRouterWorkerManager with payload: {payload}"
        )
        # Process configuration payload
        # This could include dynamic adjustment of worker count or other parameters


def main() -> None:
    """Main entry point for the DealerRouterWorkerManager."""
    bootstrap_and_run_service(DealerRouterWorkerManager)


if __name__ == "__main__":
    sys.exit(main())
