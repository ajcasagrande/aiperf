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
from aiperf.common.comms.zmq.clients.dealer_router import DealerRouterBroker
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.decorators import on_run, on_stop
from aiperf.common.enums import ServiceType, Topic
from aiperf.common.enums.comm_clients import (
    ClientType,
    PullClientType,
)
from aiperf.common.models.comms import ZMQCommunicationConfig
from aiperf.common.models.message import CreditDropMessage
from aiperf.common.service.base_component_service import BaseComponentService


class ZMQWorkerManager2Service(BaseComponentService):
    """
    A ZMQ worker manager service.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        zmq_config: ZMQCommunicationConfig | None = None,
        service_id: str | None = None,
    ):
        self.logger.debug("ZMQWorkerManager2Service initializing")
        super().__init__(service_config, service_id)
        self.broker = DealerRouterBroker.from_zmq_config(
            zmq_config or ZMQCommunicationConfig()
        )
        self.logger.debug("ZMQWorkerManager2Service initialized")
        # self.router_client = RouterClient(
        #     context=zmq.asyncio.Context.instance(),
        #     address=self.broker.router_address,
        #     bind=False,
        # )

    @on_run
    async def _on_run(self) -> None:
        # await self.router_client.initialize()
        self.logger.debug("Pulling credit drop")
        await self.comms.pull(
            topic=Topic.CREDIT_DROP,
            callback=self._process_credit_drop,
        )

        self.logger.debug("Running broker")
        await self.broker.run()

    @on_stop
    async def _on_stop(self) -> None:
        await self.broker.stop()

    @property
    def required_clients(self) -> list[ClientType]:
        """The communication clients required by the service.

        The component services subscribe to controller messages and publish
        component messages.
        """
        return [PullClientType.CREDIT_DROP]

    @property
    def service_type(self) -> ServiceType:
        return ServiceType.WORKER_MANAGER

    async def _process_credit_drop(self, message: CreditDropMessage) -> None:
        """Process a credit drop response.

        Args:
            message: The message received from the credit drop
        """
        self.logger.debug(f"Processing credit drop: {message}")
        await self.broker.router_client.send_message(message)

        # TODO: Send to worker


# class ZMQWorkerManager2(DealerRouterBrokerMixin, LoggingMixin, SupportsRun, SupportsStop):
#     """
#     A ZMQ manager class.
#     """

#     def __init__(self, service_config: ServiceConfig, zmq_config: ZMQCommunicationConfig | None = None, service_id: str | None = None):
#         self.service = ZMQWorkerManager2Service(service_config, service_id)
#         DealerRouterBrokerMixin.__init__(self, zmq_config=zmq_config or ZMQCommunicationConfig())
#         self.logger.info("ZMQWorkerManager2 initialized")

#     async def run(self) -> None:
#         await self.service._run_internal()
#         await super().run()

#     async def stop(self) -> None:
#         await self.service.stop()
#         await super().stop()
