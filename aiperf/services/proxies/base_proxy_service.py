#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

from abc import ABC

import zmq.asyncio

from aiperf.common.comms.zmq.clients.base_zmq_broker import BaseZMQBroker
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.zmq_config import BaseZMQProxyConfig
from aiperf.common.enums import ServiceType, ZMQBrokerType
from aiperf.common.factories import ServiceFactory, ZMQBrokerFactory
from aiperf.common.hooks import aiperf_task
from aiperf.common.service.base_component_service import BaseComponentService


class BaseZMQProxyService(BaseComponentService, ABC):
    """
    A Base ZMQ Proxy Service class.
    """

    def __init__(
        self,
        broker_type: ZMQBrokerType,
        service_config: ServiceConfig,
        proxy_config: BaseZMQProxyConfig,
    ) -> None:
        super().__init__(service_config=service_config)
        self._context = zmq.asyncio.Context.instance()
        self._proxy_config = proxy_config
        self._broker_type = broker_type
        self._broker: BaseZMQBroker = ZMQBrokerFactory.create_instance(
            broker_type,
            context=self._context,
            zmq_proxy_config=proxy_config,
        )

    @property
    def broker_type(self) -> ZMQBrokerType:
        """The type of ZMQ broker to use."""
        return self._broker_type

    @property
    def proxy_config(self) -> BaseZMQProxyConfig:
        """The configuration for the ZMQ proxy."""
        return self._proxy_config

    @aiperf_task
    async def _run_broker(self) -> None:
        """Run the ZMQ broker."""
        await self._broker.run()


@ServiceFactory.register(ServiceType.ZMQ_DEALER_ROUTER_BROKER)
class DealerRouterProxyService(BaseZMQProxyService):
    """
    A ZMQ Dealer Router Proxy Service class.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
    ) -> None:
        super().__init__(
            broker_type=ZMQBrokerType.DEALER_ROUTER,
            service_config=service_config,
            proxy_config=service_config.comm_config.dealer_router_broker_config,
        )

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.ZMQ_DEALER_ROUTER_BROKER


@ServiceFactory.register(ServiceType.ZMQ_XPUB_XSUB_PROXY)
class XPubXSubProxyService(BaseZMQProxyService):
    """
    A ZMQ XPub XSub Proxy Service class.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
    ) -> None:
        super().__init__(
            broker_type=ZMQBrokerType.XPUB_XSUB,
            service_config=service_config,
            proxy_config=service_config.comm_config.xpub_xsub_proxy_config,
        )

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.ZMQ_XPUB_XSUB_PROXY
