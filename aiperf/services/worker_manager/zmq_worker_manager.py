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
import json
import logging
import multiprocessing
import resource
import signal
from typing import Any

import httpx
import uvloop
import zmq
import zmq.asyncio
from pydantic import BaseModel, Field

from aiperf.common.comms.zmq.clients.dealer import DealerClient
from aiperf.common.comms.zmq.clients.dealer_router import DealerRouterBroker
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.decorators import on_run, on_stop
from aiperf.common.enums import Topic
from aiperf.common.enums.base import StrEnum
from aiperf.common.enums.comm_clients import ClientType
from aiperf.common.enums.service import ServiceType
from aiperf.common.exceptions.comms import CommunicationError
from aiperf.common.metrics.performance_monitor import get_monitor
from aiperf.common.models.comms import ZMQCommunicationConfig, ZMQTCPTransportConfig
from aiperf.common.models.message import Message
from aiperf.common.models.payload import CreditDropPayload, CreditReturnPayload
from aiperf.common.service.base_component_service import BaseComponentService


class WorkerConfig(BaseModel):
    """Configuration for worker deployment."""

    num_processes: int = Field(
        default=multiprocessing.cpu_count() - 1,
        description="Number of worker processes to spawn. Defaults to CPU count minus 1 for broker.",
    )
    tasks_per_process: int = Field(
        default=10, description="Number of worker tasks per process."
    )
    zmq_config: ZMQCommunicationConfig = Field(
        default_factory=ZMQCommunicationConfig,
        description="Configuration for ZMQ communication.",
    )
    fd_limit: int = Field(default=65535, description="File descriptor limit to set.")


class TaskMode(StrEnum):
    """Deployment modes for workers."""

    PROCESS_ONLY = "process_only"  # One worker per process
    HYBRID = "hybrid"  # Multiple worker tasks per process
    TASK_ONLY = "task_only"  # All workers as tasks in a single process


class ZMQWorkerManager(BaseComponentService):
    """
    ZeroMQ-based worker manager that creates and manages multiple worker processes and tasks.

    This class handles the full lifecycle of workers including:
    - Running a broker process
    - Spawning worker processes
    - Creating worker tasks within each process
    - Monitoring worker health
    - Graceful shutdown

    The implementation follows best practices for Python multi-process and asyncio-based applications.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
        worker_args: dict[str, Any] | None = None,
    ):
        """
        Initialize the worker manager.

        Args:
            worker_handler: Callable worker function to handle messages
            config: Worker deployment configuration
            mode: Deployment mode (process_only, hybrid, or task_only)
            worker_args: Additional arguments to pass to worker handler
        """
        super().__init__(service_config=service_config, service_id=service_id)
        self.worker_handler = http_request_worker_handler
        self.config: WorkerConfig = WorkerConfig()
        self.mode = TaskMode.HYBRID
        self.worker_args = worker_args if worker_args is not None else {}
        self.processes: list[multiprocessing.Process] = []
        self.broker_process: multiprocessing.Process | None = None
        self.task_socket: zmq.asyncio.Socket | None = None
        self.context: zmq.asyncio.Context | None = None

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER_MANAGER

    @property
    def required_clients(self) -> list[ClientType]:
        """The communication clients required by the service."""
        return []

    def increase_limits(self):
        """Increase system resource limits for scaling."""
        try:
            resource.setrlimit(
                resource.RLIMIT_NOFILE, (self.config.fd_limit, self.config.fd_limit)
            )
            self.logger.info(
                f"File descriptor limit increased to {self.config.fd_limit}"
            )
        except (ValueError, resource.error) as e:
            self.logger.warning(f"Could not increase file descriptor limit: {e}")

    async def _worker_task(self, worker_id: str, context: zmq.asyncio.Context):
        """Individual worker task implementation."""
        dealer = DealerClient(
            context,
            self.config.zmq_config.credit_broker_dealer_address,
            self.worker_handler,
            id=worker_id,
        )
        await dealer.initialize()
        await dealer.run()

    async def _monitor_workers(self, process_id: int, num_workers: int):
        """Monitor worker health and performance."""
        try:
            while True:
                await asyncio.sleep(30)
                self.logger.info(
                    f"Process {process_id} monitoring: {num_workers} workers active"
                )
                # Here you could add metrics collection, health checks, etc.
        except asyncio.CancelledError:
            self.logger.info(f"Monitor for process {process_id} cancelled")

    async def run_process_workers(self, process_id: int):
        """Run multiple worker tasks within a single process."""
        # Create shared ZMQ context for this process
        shared_context = zmq.asyncio.Context.instance()

        self.logger.info(
            f"Worker process {process_id} starting with {self.config.tasks_per_process} tasks"
        )

        # Create worker tasks
        tasks = []
        for i in range(self.config.tasks_per_process):
            worker_id = f"{process_id}-{i}"
            tasks.append(
                asyncio.create_task(self._worker_task(worker_id, shared_context))
            )

        # Add monitoring task
        monitor_task = asyncio.create_task(
            self._monitor_workers(process_id, self.config.tasks_per_process)
        )
        tasks.append(monitor_task)

        def signal_handler():
            """Handle process signals for graceful shutdown."""
            for task in tasks:
                if not task.done():
                    task.cancel()

        # Setup signal handlers
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        try:
            # Run all tasks concurrently
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            self.logger.error(f"Error in process {process_id}: {e}")
        finally:
            # Clean shutdown
            for task in tasks:
                if not task.done():
                    task.cancel()

            # Wait for tasks to cancel
            await asyncio.gather(*tasks, return_exceptions=True)
            shared_context.term()
            self.logger.info(f"Process {process_id} shut down")

    def worker_process_main(self, process_id: int):
        """Entry point for each worker process."""
        # Set up process
        self.increase_limits()

        # Set process name for easier monitoring
        try:
            import setproctitle

            setproctitle.setproctitle(f"aiperf-worker-{process_id}")
        except ImportError:
            pass

        # Run the worker tasks
        asyncio.run(self.run_process_workers(process_id))

    async def run_broker(self):
        """Run the broker using DealerRouterBroker."""
        self.logger.info("Starting broker process")
        context = zmq.asyncio.Context.instance()

        broker = DealerRouterBroker(
            context=context,
            router_address=self.config.zmq_config.credit_broker_router_address,
            dealer_address=self.config.zmq_config.credit_broker_dealer_address,
            control_address=self.config.zmq_config.credit_broker_control_address,
            capture_address=self.config.zmq_config.credit_broker_capture_address,
        )

        try:
            await broker.run()
        except CommunicationError as e:
            self.logger.error(f"Broker error: {e}")
        except asyncio.CancelledError:
            self.logger.info("Broker cancelled")
        except Exception as e:
            self.logger.error(f"Unexpected broker error: {e}")

    def broker_process_main(self):
        """Entry point for the broker process."""
        # Set up process
        self.increase_limits()

        # Set process name
        try:
            import setproctitle

            setproctitle.setproctitle("aiperf-broker")
        except ImportError:
            pass

        # Run the broker
        asyncio.run(self.run_broker())

    @on_run
    async def _on_run2(self):
        """Start the broker and worker processes."""
        self.logger.info(f"Starting ZMQ Worker Manager in {self.mode} mode")
        self.logger.info(f"Service ID: {self.service_id}")
        self.logger.info(f"Communication config: {self.service_config}")
        self.increase_limits()

        # Start the broker process first
        self.broker_process = multiprocessing.Process(
            target=self.broker_process_main, name="broker"
        )
        self.broker_process.daemon = True
        self.broker_process.start()
        self.logger.info(f"Started broker process (PID: {self.broker_process.pid})")

        # Give broker time to initialize
        await asyncio.sleep(1)

        # Configure worker deployment based on mode
        if self.mode == TaskMode.PROCESS_ONLY:
            # One worker per process - more processes, one task each
            num_processes = self.config.num_processes * self.config.tasks_per_process
            tasks_per_process = 1
        elif self.mode == TaskMode.TASK_ONLY:
            # All workers in a single process
            num_processes = 1
            tasks_per_process = (
                self.config.num_processes * self.config.tasks_per_process
            )
        else:  # HYBRID mode - default
            num_processes = self.config.num_processes
            tasks_per_process = self.config.tasks_per_process

        # Update config to match selected mode
        self.config.num_processes = num_processes
        self.config.tasks_per_process = tasks_per_process

        # Start worker processes
        for i in range(num_processes):
            p = multiprocessing.Process(
                target=self.worker_process_main, args=(i,), name=f"worker-{i}"
            )
            p.daemon = True
            p.start()
            self.processes.append(p)
            self.logger.info(f"Started worker process {i} (PID: {p.pid})")

        self.logger.info(
            f"All processes started: 1 broker + {len(self.processes)} workers"
        )

        # Initialize task sender socket to send work to broker
        self.context = zmq.asyncio.Context.instance()
        self.task_socket = self.context.socket(zmq.DEALER)
        self.task_socket.connect(self.config.zmq_config.credit_broker_router_address)
        self.logger.debug("Connected to broker router for task distribution")

        self.logger.info("Setting up credit drop subscription...")
        self.logger.info(f"Subscribing to topic: {Topic.CREDIT_DROP}")
        self.logger.info(f"Callback function: {self._process_credit_drop}")

        await self.comms.pull(
            topic=Topic.CREDIT_DROP,
            callback=self._process_credit_drop,
        )

        self.logger.info("✅ Credit drop subscription setup complete!")
        self.logger.info("Worker manager is now ready to receive credit drops")

    @on_stop
    async def _on_stop2(self):
        """Stop all processes gracefully."""
        self.logger.info("Stopping all worker processes...")

        # Close task sender socket
        if self.task_socket:
            self.task_socket.close()

        # Terminate worker processes
        for p in self.processes:
            if p.is_alive():
                p.terminate()

        # Wait for worker processes to finish
        for p in self.processes:
            p.join(timeout=2)

        # Terminate broker process last
        if self.broker_process and self.broker_process.is_alive():
            self.logger.info("Stopping broker process...")
            self.broker_process.terminate()
            self.broker_process.join(timeout=2)

        self.logger.info("All processes stopped")

    async def join(self):
        """Wait for all processes to complete."""
        self.logger.info("Waiting for all processes to complete...")
        self.logger.info(f"Broker process: {self.broker_process}")
        self.logger.info(f"Worker processes: {self.processes}")

        await asyncio.gather(*[asyncio.to_thread(p.join) for p in self.processes])

        # Wait for broker process
        if self.broker_process:
            await asyncio.to_thread(self.broker_process.join)

    async def _test_pull_callback(self, message: Message) -> None:
        """Test callback to verify pull mechanism is working."""
        self.logger.warning(f"🔥 TEST: Received message via pull: {message}")
        self.logger.warning(f"🔥 TEST: Message type: {type(message)}")
        self.logger.warning(f"🔥 TEST: Payload type: {type(message.payload)}")

    async def _process_credit_drop(self, message: Message) -> None:
        """Process a credit drop response and send to workers.

        Args:
            message: The message received from the credit drop
        """
        # self.logger.debug(f"🚨 CREDIT DROP RECEIVED! Processing credit drop from new zmq worker manager: {message}")
        # self.logger.debug(f"🚨 Message payload type: {type(message.payload)}")
        # self.logger.debug(f"🚨 Message payload: {message.payload}")

        if self.task_socket and isinstance(message.payload, CreditDropPayload):
            try:
                # self.logger.debug("🚨 Sending credit drop task to workers via the broker")

                # Convert credit drop to HTTP request format
                http_request = {
                    "method": "POST",
                    "path": "/api/credit-drop",
                    "headers": {
                        "Content-Type": "application/json",
                        "X-Credit-Amount": str(message.payload.amount),
                        "X-Credit-Timestamp": str(message.payload.timestamp),
                    },
                    "json": {
                        "credit_drop": {
                            "amount": message.payload.amount,
                            "timestamp": message.payload.timestamp,
                            "request_id": message.request_id,
                            "service_id": message.service_id,
                        }
                    },
                }

                # Send the HTTP request data to workers via the broker
                task_data = json.dumps(http_request).encode()
                self.logger.debug(f"Sending HTTP request data: {http_request}")

                await self.task_socket.send(task_data)
                self.logger.debug("Credit drop task sent successfully")

                # Wait for response from worker
                response = await self.task_socket.recv()
                self.logger.debug(f"Received worker response: {response}")

                # Parse worker response
                try:
                    response_data = json.loads(response.decode())
                    if response_data.get("success"):
                        self.logger.info(
                            f"Worker processed credit drop successfully: {response_data}"
                        )
                    else:
                        self.logger.warning(
                            f"Worker failed to process credit drop: {response_data}"
                        )
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    self.logger.warning(
                        f"Could not parse worker response: {response}, error: {e}"
                    )

                # Return credit after processing
                await self.comms.push(
                    topic=Topic.CREDIT_RETURN,
                    message=self.create_message(
                        payload=CreditReturnPayload(
                            amount=message.payload.amount,  # Return the same amount
                        )
                    ),
                )
                self.logger.debug(f"Returned {message.payload.amount} credits")

            except Exception as e:
                self.logger.error(f"Failed to send credit drop to workers: {e}")
                # Still return credits even if processing failed
                await self.comms.push(
                    topic=Topic.CREDIT_RETURN,
                    message=self.create_message(
                        payload=CreditReturnPayload(
                            amount=message.payload.amount,
                        )
                    ),
                )
        else:
            self.logger.error(
                f"🚨 UNEXPECTED: task_socket={self.task_socket}, payload_type={type(message.payload)}"
            )
            self.logger.error(f"🚨 Expected CreditDropPayload, got: {message.payload}")


# Example worker handler implementation
async def http_request_worker_handler(message, worker_id, **kwargs):
    """High-performance HTTP worker that makes requests to FastAPI server."""

    # Get performance monitor
    monitor = get_monitor()

    # Record request start
    start_time = monitor.record_request_start(worker_id)

    # Create reusable HTTP client with connection pooling
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(10.0),
        limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
        http2=True,
    ) as client:
        try:
            # Extract request data from message
            if isinstance(message, bytes):
                try:
                    request_data = json.loads(message.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    request_data = {"path": "/", "method": "GET"}
            elif isinstance(message, str):
                try:
                    request_data = json.loads(message)
                except json.JSONDecodeError:
                    request_data = {"path": "/", "method": "GET"}
            else:
                # Default request for other types
                request_data = {"path": "/", "method": "GET"}

            # Extract request parameters
            method = request_data.get("method", "GET").upper()
            path = request_data.get("path", "/")
            headers_raw = request_data.get("headers", {})
            headers = dict(headers_raw) if isinstance(headers_raw, dict) else {}
            params = request_data.get("params", {})
            json_data = request_data.get("json", None)

            # Construct URL
            base_url = "http://localhost:9797"
            url = f"{base_url}{path}"

            # Add worker ID to headers for tracking
            headers["X-Worker-ID"] = worker_id

            # Make HTTP request
            response = await client.request(
                method=method, url=url, headers=headers, params=params, json=json_data
            )

            # Calculate response time
            response_time_ms = response.elapsed.total_seconds() * 1000

            # Record successful request
            monitor.record_request_end(worker_id, start_time, True, response_time_ms)

            # Return response data
            result = {
                "worker_id": worker_id,
                "status_code": response.status_code,
                "response_time_ms": response_time_ms,
                "headers": dict(response.headers),
                "content": response.text,
                "url": str(response.url),
                "method": method,
                "success": True,
            }

            return json.dumps(result).encode()

        except httpx.TimeoutException:
            # Record failed request
            monitor.record_request_end(worker_id, start_time, False)

            error_result = {
                "worker_id": worker_id,
                "error": "Request timeout",
                "status": "timeout",
                "success": False,
            }
            return json.dumps(error_result).encode()

        except httpx.ConnectError:
            # Record failed request
            monitor.record_request_end(worker_id, start_time, False)

            error_result = {
                "worker_id": worker_id,
                "error": "Connection failed - FastAPI server may not be running",
                "status": "connection_error",
                "success": False,
            }
            return json.dumps(error_result).encode()

        except Exception as e:
            # Record failed request
            monitor.record_request_end(worker_id, start_time, False)

            error_result = {
                "worker_id": worker_id,
                "error": str(e),
                "status": "error",
                "success": False,
            }
            return json.dumps(error_result).encode()


# Example worker handler implementation (legacy)
async def example_worker_handler(message, worker_id, **kwargs):
    """Example worker message handler."""
    await asyncio.sleep(1)  # Simulate work
    return f"Processed by {worker_id}"


async def main():
    """Main entry point for the worker manager."""
    # Create configuration
    config = WorkerConfig(
        num_processes=multiprocessing.cpu_count() - 1,  # Reserve one for broker
        tasks_per_process=10,  # 10 worker tasks per process
        zmq_config=ZMQCommunicationConfig(protocol_config=ZMQTCPTransportConfig()),
    )

    logging.basicConfig(level=logging.DEBUG)

    # Create and start worker manager
    manager = ZMQWorkerManager(
        service_config=ServiceConfig(),
        worker_args={},
    )

    # Start the manager
    await manager.run_forever()


def run_forever():
    uvloop.run(main())


if __name__ == "__main__":
    uvloop.run(main())
