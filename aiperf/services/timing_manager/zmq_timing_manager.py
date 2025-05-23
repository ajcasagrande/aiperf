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
import contextlib
import multiprocessing
import os
import resource
import sys
import time

import zmq
import zmq.asyncio
from pydantic import BaseModel, Field

from aiperf.common.comms.zmq.clients.dealer_router import DealerRouterBroker
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.decorators import (
    on_cleanup,
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.enums import (
    ClientType,
    ServiceState,
    ServiceType,
    Topic,
)
from aiperf.common.enums.base import StrEnum
from aiperf.common.exceptions.comms import CommunicationError
from aiperf.common.models.comms import ZMQCommunicationConfig
from aiperf.common.models.message import Message
from aiperf.common.models.payload import (
    BasePayload,
    CreditDropPayload,
    CreditReturnPayload,
)
from aiperf.common.service.base_component_service import BaseComponentService


class TimingMode(StrEnum):
    """Credit distribution modes for the timing manager."""

    RATE_LIMITED = "rate_limited"  # Credits distributed at a fixed rate
    BURST = "burst"  # Credits distributed in bursts
    ADAPTIVE = "adaptive"  # Credits distributed based on system load


class TimingManagerConfig(BaseModel):
    """Configuration for timing manager deployment."""

    initial_credits: int = Field(
        default=100, description="Initial number of credits available for distribution."
    )
    credit_rate: float = Field(
        default=10.0, description="Rate at which credits are issued (per second)."
    )
    zmq_config: ZMQCommunicationConfig = Field(
        default_factory=ZMQCommunicationConfig,
        description="Configuration for ZMQ communication.",
    )
    fd_limit: int = Field(default=65535, description="File descriptor limit to set.")
    num_processes: int = Field(
        default=1, description="Number of timing manager worker processes."
    )
    timing_mode: TimingMode = Field(
        default=TimingMode.RATE_LIMITED, description="Mode for credit distribution."
    )


class ZMQTimingManager(BaseComponentService):
    """
    ZeroMQ-based timing manager that uses the dealer-router pattern for credit distribution.

    This implementation improves upon the original TimingManager by:
    1. Using a high-performance ZMQ dealer-router broker for credit distribution
    2. Supporting multiple parallel timing manager worker processes
    3. Implementing various credit distribution strategies
    4. Providing extensive monitoring and metrics
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
    ) -> None:
        """Initialize the ZMQ timing manager."""
        super().__init__(service_config=service_config, service_id=service_id)
        self._credit_lock = asyncio.Lock()
        self.config = TimingManagerConfig()
        self._credits_available = self.config.initial_credits
        self._credit_drop_task: asyncio.Task | None = None
        self.broker_process: multiprocessing.Process | None = None
        self.processes: list[multiprocessing.Process] = []
        self.logger.info(
            f"Initializing ZMQ timing manager with {self._credits_available} credits"
        )

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.TIMING_MANAGER

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

    @on_init
    async def _initialize(self) -> None:
        """Initialize timing manager-specific components."""
        self.logger.info("Initializing ZMQ timing manager")
        self.increase_limits()

    @on_start
    async def _start(self) -> None:
        """Start the timing manager."""
        self.logger.info("Starting ZMQ timing manager")

        # Start the broker process first
        self.broker_process = multiprocessing.Process(
            target=self.broker_process_main, name="timing-broker"
        )
        self.broker_process.daemon = True
        self.broker_process.start()
        self.logger.info(
            f"Started timing broker process (PID: {self.broker_process.pid})"
        )

        # Give broker time to initialize
        await asyncio.sleep(1)

        # Start credit manager processes if using multiple processes
        if self.config.num_processes > 1:
            for i in range(self.config.num_processes):
                p = multiprocessing.Process(
                    target=self.credit_manager_process_main,
                    args=(i,),
                    name=f"timing-manager-{i}",
                )
                p.daemon = True
                p.start()
                self.processes.append(p)
                self.logger.info(f"Started timing manager process {i} (PID: {p.pid})")
        else:
            # If single process, run the credit manager in this process
            self._credit_drop_task = asyncio.create_task(self._issue_credit_drops())

        # Subscribe to credit returns from workers
        await self.comms.pull(
            topic=Topic.CREDIT_RETURN,
            callback=self._on_credit_return,
        )

        await self.set_state(ServiceState.RUNNING)

    @on_stop
    async def _stop(self) -> None:
        """Stop the timing manager."""
        self.logger.info("Stopping ZMQ timing manager")

        # Stop the credit drop task if running locally
        if self._credit_drop_task and not self._credit_drop_task.done():
            self._credit_drop_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._credit_drop_task
            self._credit_drop_task = None

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

        self.logger.info("All timing manager processes stopped")

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up timing manager-specific components."""
        self.logger.info("Cleaning up ZMQ timing manager")

    @on_configure
    async def _configure(self, payload: BasePayload) -> None:
        """Configure the timing manager."""
        self.logger.info(f"Configuring ZMQ timing manager with payload: {payload}")
        # Handle configuration updates for credit distribution parameters

    async def run_broker(self):
        """Run the broker using DealerRouterBroker."""
        self.logger.info("Starting timing broker process")
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

            setproctitle.setproctitle("aiperf-timing-broker")
        except ImportError:
            pass

        # Run the broker
        asyncio.run(self.run_broker())

    def credit_manager_process_main(self, process_id: int):
        """Entry point for each credit manager process."""
        # Set up process
        self.increase_limits()

        # Set process name for easier monitoring
        try:
            import setproctitle

            setproctitle.setproctitle(f"aiperf-timing-manager-{process_id}")
        except ImportError:
            pass

        # Run the credit manager
        asyncio.run(self._issue_credit_drops(process_id))

    async def _issue_credit_drops(self, process_id: int = 0) -> None:
        """
        Issue credit drops to workers.

        This method implements different credit distribution strategies based on
        the configured timing mode.
        """
        self.logger.info(f"Starting credit drop task for process {process_id}")

        # Create dealer socket for sending credit drops
        context = zmq.asyncio.Context.instance()
        socket = context.socket(zmq.DEALER)
        socket.setsockopt(zmq.IDENTITY, f"timing-manager-{process_id}".encode())

        # Connect to the broker's dealer endpoint
        dealer_address = self.config.zmq_config.credit_broker_dealer_address.replace(
            "*", "localhost"
        )
        socket.connect(dealer_address)

        self.logger.info(f"Credit manager {process_id} connected to {dealer_address}")

        # Calculate sleep time based on credit rate
        sleep_time = 1.0 / self.config.credit_rate

        try:
            while True:
                try:
                    # Different distribution strategies based on timing mode
                    if self.config.timing_mode == TimingMode.RATE_LIMITED:
                        # Consistent rate distribution
                        await self._rate_limited_drop(socket, process_id)
                        await asyncio.sleep(sleep_time)

                    elif self.config.timing_mode == TimingMode.BURST:
                        # Burst distribution - send multiple credits at once, then wait
                        await self._burst_drop(socket, process_id)
                        await asyncio.sleep(sleep_time * 10)

                    elif self.config.timing_mode == TimingMode.ADAPTIVE:
                        # Adaptive distribution based on system load
                        await self._adaptive_drop(socket, process_id)
                        await asyncio.sleep(sleep_time)

                except asyncio.CancelledError:
                    self.logger.info(
                        f"Credit drop task cancelled for process {process_id}"
                    )
                    break

                except Exception as e:
                    self.logger.error(
                        f"Exception issuing credit drop in process {process_id}: {e}"
                    )
                    await asyncio.sleep(0.1)

        finally:
            socket.close()
            self.logger.info(f"Credit drop task for process {process_id} shut down")

    async def _rate_limited_drop(
        self, socket: zmq.asyncio.Socket, process_id: int
    ) -> None:
        """Distribute credits at a consistent rate."""
        async with self._credit_lock:
            if self._credits_available <= 0:
                self.logger.warning("No credits available, skipping credit drop")
                return

            self.logger.debug(f"Process {process_id} issuing credit drop")
            self._credits_available -= 1

        # Create credit drop payload
        payload = CreditDropPayload(
            amount=1,
            timestamp=time.time_ns(),
        )

        # Send through the dealer socket to the broker
        await socket.send_multipart(
            [
                b"",  # Empty frame for router
                self.create_message(payload=payload).json().encode(),
            ]
        )

    async def _burst_drop(self, socket: zmq.asyncio.Socket, process_id: int) -> None:
        """Distribute credits in bursts."""
        burst_size = 10  # Number of credits to drop at once

        async with self._credit_lock:
            available = min(self._credits_available, burst_size)
            if available <= 0:
                self.logger.warning("No credits available, skipping burst drop")
                return

            self.logger.debug(
                f"Process {process_id} issuing burst drop of {available} credits"
            )
            self._credits_available -= available

        # Create credit drop payload with multiple credits
        payload = CreditDropPayload(
            amount=available,
            timestamp=time.time_ns(),
        )

        # Send through the dealer socket to the broker
        await socket.send_multipart(
            [
                b"",  # Empty frame for router
                self.create_message(payload=payload).json().encode(),
            ]
        )

    async def _adaptive_drop(self, socket: zmq.asyncio.Socket, process_id: int) -> None:
        """Distribute credits adaptively based on system load."""
        # Determine credit amount based on system load
        try:
            load = os.getloadavg()[0]  # 1-minute load average
            scale_factor = max(0.1, min(1.0, 1.0 - (load / (os.cpu_count() or 1))))
            drop_amount = max(1, int(10 * scale_factor))
        except (AttributeError, OSError):
            # Fallback if os.getloadavg() is not available
            drop_amount = 1

        async with self._credit_lock:
            available = min(self._credits_available, drop_amount)
            if available <= 0:
                self.logger.warning("No credits available, skipping adaptive drop")
                return

            self.logger.debug(
                f"Process {process_id} issuing adaptive drop of {available} credits"
            )
            self._credits_available -= available

        # Create credit drop payload
        payload = CreditDropPayload(
            amount=available,
            timestamp=time.time_ns(),
        )

        # Send through the dealer socket to the broker
        await socket.send_multipart(
            [
                b"",  # Empty frame for router
                self.create_message(payload=payload).model_dump_json().encode(),
            ]
        )

    async def _on_credit_return(self, message: Message) -> None:
        """
        Process a credit return response.

        Args:
            message: The response received from the pull request
        """
        self.logger.debug(f"Processing credit return: {message.payload}")

        # Check if message payload is a CreditReturnPayload
        if not isinstance(message.payload, CreditReturnPayload):
            self.logger.warning(
                f"Received non-credit return payload: {message.payload}"
            )
            return

        async with self._credit_lock:
            self._credits_available += message.payload.amount
            self.logger.debug(f"Credits available: {self._credits_available}")


def main() -> None:
    """Main entry point for the ZMQ timing manager."""
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(ZMQTimingManager)


if __name__ == "__main__":
    sys.exit(main())
