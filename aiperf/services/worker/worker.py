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
import sys

from aiperf.common.comms.base import BaseCommunication
from aiperf.common.config.loader import load_service_config
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.decorators import (
    on_cleanup,
    on_init,
    on_run,
    on_start,
    on_stop,
)
from aiperf.common.enums import (
    ClientType,
    PullClientType,
    PushClientType,
    ServiceType,
    Topic,
)
from aiperf.common.models.message import CreditDropMessage
from aiperf.common.models.payload import CreditReturnPayload
from aiperf.common.service.service_metaclass import ServiceMetaclass


class Worker(metaclass=ServiceMetaclass):
    """Worker is primarily responsible for converting the data into the appropriate
    format for the interface being used by the server. Also responsible for managing
    the conversation between turns.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
        shared_comms: BaseCommunication | None = None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.service_config = service_config
        self.service_id = service_id
        self.comms = shared_comms

    async def initialize(self) -> None:
        """Initialize the worker."""
        self.logger.debug("Initializing worker")
        await self.comms.create_clients(*self.required_clients)

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER

    @property
    def required_clients(self) -> list[ClientType]:
        """The communication clients required by the service."""
        return [
            *(super().required_clients or []),
            PullClientType.CREDIT_DROP,
            PushClientType.CREDIT_RETURN,
        ]

    @on_init
    async def _initialize(self) -> None:
        """Initialize worker-specific components."""
        self.logger.debug("Initializing worker")

    @on_run
    async def _run(self) -> None:
        """Automatically start the worker in the run method."""
        await self.start()

    @on_start
    async def _start(self) -> None:
        """Start the worker."""
        self.logger.debug("Starting worker")
        # Subscribe to the credit drop topic
        await self.comms.pull(
            topic=Topic.CREDIT_DROP,
            callback=self._process_credit_drop,
        )

    @on_stop
    async def _stop(self) -> None:
        """Stop the worker."""
        self.logger.debug("Stopping worker")

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up worker-specific components."""
        self.logger.debug("Cleaning up worker")

    async def _process_credit_drop(self, message: CreditDropMessage) -> None:
        """Process a credit drop response.

        Args:
            message: The message received from the credit drop
        """
        self.logger.debug(f"Processing credit drop: {message}")
        # TODO: Implement actual worker logic
        await asyncio.sleep(1)  # Simulate some processing time

        self.logger.debug("Returning credits")
        await self.comms.push(
            topic=Topic.CREDIT_RETURN,
            message=self.create_message(
                payload=CreditReturnPayload(amount=1),
            ),
        )


async def run_workers(workers: list[Worker]) -> None:
    """Run a list of workers."""
    tasks = [asyncio.create_task(worker.run_forever()) for worker in workers]
    await asyncio.gather(*tasks)


def create_workers(cfg: ServiceConfig, num_workers: int) -> list[Worker]:
    """Create a list of workers."""
    return [Worker(cfg) for _ in range(num_workers)]


def run_from_config(cfg: ServiceConfig) -> None:
    """Run a worker from a configuration."""
    import uvloop

    # Create and run the workers
    workers = create_workers(cfg, 10)
    import logging

    logger = logging.getLogger(__name__)
    print(workers)
    for worker in workers:
        logger.error(worker.service_id)
    uvloop.run(run_workers(workers))


def main() -> None:
    """Main entry point for the worker."""

    # Load the service configuration
    cfg = load_service_config()
    run_from_config(cfg)


if __name__ == "__main__":
    sys.exit(main())
