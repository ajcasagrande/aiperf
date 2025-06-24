#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

from abc import ABC

import zmq.asyncio

from aiperf.common.comms.zmq.clients.base_zmq_proxy import BaseZMQProxy
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.zmq_config import BaseZMQProxyConfig
from aiperf.common.enums import ServiceType, ZMQProxyType
from aiperf.common.factories import ServiceFactory, ZMQProxyFactory
from aiperf.common.hooks import aiperf_task
from aiperf.common.service.base_component_service import BaseComponentService


class BaseZMQProxyService(BaseComponentService, ABC):
    """
    A Base ZMQ Proxy Service class.
    """

    def __init__(
        self,
        proxy_type: ZMQProxyType,
        service_config: ServiceConfig,
        proxy_config: BaseZMQProxyConfig,
    ) -> None:
        super().__init__(service_config=service_config)
        self._context = zmq.asyncio.Context.instance()
        self._proxy_config = proxy_config
        self._proxy_type = proxy_type
        self._proxy: BaseZMQProxy = ZMQProxyFactory.create_instance(
            proxy_type,
            context=self._context,
            zmq_proxy_config=proxy_config,
        )

    @property
    def proxy_type(self) -> ZMQProxyType:
        """The type of ZMQ proxy to use."""
        return self._proxy_type

    @property
    def proxy_config(self) -> BaseZMQProxyConfig:
        """The configuration for the ZMQ proxy."""
        return self._proxy_config

    @aiperf_task
    async def _run_proxy(self) -> None:
        """Run the ZMQ proxy."""
        await self._proxy.run()


@ServiceFactory.register(ServiceType.ZMQ_DEALER_ROUTER_PROXY)
class DealerRouterProxyService(BaseZMQProxyService):
    """
    A ZMQ Dealer Router Proxy Service class.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
    ) -> None:
        super().__init__(
            proxy_type=ZMQProxyType.DEALER_ROUTER,
            service_config=service_config,
            proxy_config=service_config.comm_config.dealer_router_proxy_config,
        )

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.ZMQ_DEALER_ROUTER_PROXY


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
            proxy_type=ZMQProxyType.XPUB_XSUB,
            service_config=service_config,
            proxy_config=service_config.comm_config.xpub_xsub_proxy_config,
        )

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.ZMQ_XPUB_XSUB_PROXY
