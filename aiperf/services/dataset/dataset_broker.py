# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import sys

from aiperf.common.comms.zmq.clients.dealer_router import ZMQDealerRouterBroker
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import (
    on_configure,
    on_init,
    on_run,
    on_stop,
)
from aiperf.common.messages import Message
from aiperf.common.service.base_component_service import BaseComponentService


@ServiceFactory.register(ServiceType.DATASET_BROKER)
class DatasetBroker(BaseComponentService):
    """
    The DatasetBroker is responsible for managing the DealerRouterBroker for the dataset.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing dataset broker")
        self.dealer_router_broker: ZMQDealerRouterBroker | None = None

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.DATASET_BROKER

    @on_init
    async def _initialize(self) -> None:
        """Initialize dataset broker-specific components."""
        self.logger.debug("Initializing dataset broker")
        self.dealer_router_broker = ZMQDealerRouterBroker.from_config(
            config=self.service_config.comm_config.dataset_broker_config,
        )

    @on_run
    async def _run(self) -> None:
        """Start the dataset broker."""
        self.logger.debug("Running dataset broker")
        if self.dealer_router_broker is None:
            raise ValueError("DealerRouterBroker is not initialized")
        await self.dealer_router_broker.run()

    @on_stop
    async def _stop(self) -> None:
        """Stop the dataset broker."""
        self.logger.debug("Stopping dataset broker")
        if self.dealer_router_broker is None:
            raise ValueError("DealerRouterBroker is not initialized")
        await self.dealer_router_broker.stop()

    @on_configure
    async def _configure(self, message: Message) -> None:
        """Configure the dataset broker."""
        self.logger.debug(f"Configuring dataset broker with message: {message}")
        # TODO: Implement dataset broker configuration


def main() -> None:
    """Main entry point for the dataset broker."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(DatasetBroker)


if __name__ == "__main__":
    sys.exit(main())
