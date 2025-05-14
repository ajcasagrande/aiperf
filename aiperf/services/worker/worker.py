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
import sys

import uvloop

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import (
    ServiceType,
    Topic,
    ClientType,
)
from aiperf.common.models.messages import BaseMessage
from aiperf.common.models.payloads import CreditDropPayload, CreditReturnPayload
from aiperf.common.service.base import ServiceBase


class Worker(ServiceBase):
    """Worker responsible for sending requests to the server."""

    def __init__(self, service_config: ServiceConfig, service_id: str = None) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing worker")

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER

    async def _initialize(self) -> None:
        """Initialize worker-specific components."""
        self.logger.debug("Initializing worker")
        await self.communication.create_clients(
            ClientType.CREDIT_RETURN_PUSH,
            ClientType.CREDIT_DROP_PULL,
            ClientType.CONVERSATION_DATA_REQ,
        )

    async def run(self) -> None:
        """Run the worker."""
        self.logger.debug("Running worker")

        await self._base_init()

        await self._initialize()
        await self._on_start()

        # Wait for the worker to finish
        # TODO: implement actual worker run logic
        await self.stop_event.wait()

        await self._on_stop()
        await self._cleanup()

    async def _on_start(self) -> None:
        """Start the worker."""
        self.logger.debug("Starting worker")
        # Subscribe to the credit drop topic
        await self.communication.pull(
            ClientType.CREDIT_DROP_PULL,
            Topic.CREDIT_DROP,
            self._process_credit_drop,
        )

    async def _on_stop(self) -> None:
        """Stop the worker."""
        self.logger.debug("Stopping worker")

    async def _cleanup(self) -> None:
        """Clean up worker-specific components."""
        self.logger.debug("Cleaning up worker")

    async def _process_credit_drop(self, payload: CreditDropPayload) -> None:
        """Process a credit drop message.

        Args:
            pull_data: The data received from the pull request
        """
        self.logger.debug(f"Processing credit drop: {payload}")

        await asyncio.sleep(1)  # Simulate some processing time

        # await self.communication.request(
        #     ClientType.CONVERSATION_DATA_REQ,
        #     target=ServiceType.DATASET_MANAGER,
        #     request_data=RequestData(
        #         request_id=f"req_{uuid.uuid4().hex[:8]}",
        #         client_id=self.service_id,
        #         target=ServiceType.DATASET_MANAGER,
        #         payload=WorkerRequestPayload(
        #             operation="get_conversation_data",
        #             parameters={},
        #         ),
        #     ),
        # )

        self.logger.debug("Returning credits")
        (
            await self.communication.push(
                ClientType.CREDIT_RETURN_PUSH,
                BaseMessage(
                    topic=Topic.CREDIT_RETURN,
                    source=self.service_id,
                    payload=CreditReturnPayload(amount=1),
                ),
            ),
        )


if __name__ == "__main__":
    uvloop.install()

    # Load the service configuration
    from aiperf.common.config.loader import load_worker_config

    cfg = load_worker_config()
    worker = Worker(cfg)
    sys.exit(uvloop.run(worker.run()))
