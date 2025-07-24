# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio

from aiperf.common.comms import BaseZMQProxy
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.constants import TASK_CANCEL_TIMEOUT_SHORT
from aiperf.common.enums import ZMQProxyType
from aiperf.common.factories import ZMQProxyFactory
from aiperf.common.hooks import on_init, on_start, on_stop
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin


class ProxyManager(AIPerfLifecycleMixin):
    def __init__(self, service_config: ServiceConfig, **kwargs) -> None:
        super().__init__(**kwargs)
        self.service_config = service_config

    @on_init
    async def _initialize_proxies(self) -> None:
        comm_config = self.service_config.comm_config

        self.event_bus_proxy: BaseZMQProxy = ZMQProxyFactory.create_instance(
            ZMQProxyType.XPUB_XSUB,
            zmq_proxy_config=comm_config.event_bus_proxy_config,
        )
        await self.event_bus_proxy.initialize()

        self.dataset_manager_proxy: BaseZMQProxy = ZMQProxyFactory.create_instance(
            ZMQProxyType.DEALER_ROUTER,
            zmq_proxy_config=comm_config.dataset_manager_proxy_config,
        )
        await self.dataset_manager_proxy.initialize()

        self.raw_inference_proxy: BaseZMQProxy = ZMQProxyFactory.create_instance(
            ZMQProxyType.PUSH_PULL,
            zmq_proxy_config=comm_config.raw_inference_proxy_config,
        )
        await self.raw_inference_proxy.initialize()
        self.debug("All proxies initialized successfully")

    @on_start
    async def _start_proxies(self) -> None:
        self.debug("Starting all proxies")
        await asyncio.gather(
            self.event_bus_proxy.start(),
            self.dataset_manager_proxy.start(),
            self.raw_inference_proxy.start(),
            return_exceptions=True,
        )
        self.debug("All proxies started successfully")

    @on_stop
    async def _stop_proxies(self) -> None:
        self.debug("Stopping all proxies")
        await asyncio.wait_for(
            asyncio.gather(
                self.event_bus_proxy.stop(),
                self.dataset_manager_proxy.stop(),
                self.raw_inference_proxy.stop(),
                return_exceptions=True,
            ),
            timeout=TASK_CANCEL_TIMEOUT_SHORT,
        )
        self.debug("All proxies stopped successfully")
