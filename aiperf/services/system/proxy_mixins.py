# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Proxy management mixins for services that need to manage ZMQ proxies.

This module provides mixin classes for managing ZMQ proxies, making it easier
to separate proxy management logic from core service functionality.
"""

import asyncio
import logging

import zmq.asyncio

from aiperf.common.comms.zmq.zmq_proxy_base import (
    BaseZMQProxy,
    BaseZMQProxyConfig,
    ZMQProxyFactory,
)
from aiperf.common.config import ServiceConfig, load_service_config
from aiperf.common.constants import TASK_CANCEL_TIMEOUT_SHORT
from aiperf.common.enums import ZMQProxyType
from aiperf.common.hooks import on_post_stop, on_pre_init
from aiperf.common.lifecycle_mixins import AIPerfLifecycleMixin


class ZMQProxyManagerMixin(AIPerfLifecycleMixin):
    """
    Mixin class for managing ZMQ proxies.

    This mixin provides functionality to initialize, start, and stop multiple
    ZMQ proxies in a structured way.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._proxies: dict[str, BaseZMQProxy] = {}
        self.zmq_context: zmq.asyncio.Context = zmq.asyncio.Context.instance()

    def register_proxy(
        self,
        name: str,
        proxy_type: ZMQProxyType,
        proxy_config: BaseZMQProxyConfig,
    ) -> None:
        """Register a proxy to be managed."""
        if name in self._proxies:
            raise ValueError(f"Proxy {name} is already registered")

        self._proxies[name] = ZMQProxyFactory.create_instance(
            proxy_type,
            context=self.zmq_context,
            zmq_proxy_config=proxy_config,
        )
        self.logger.debug("Registered proxy %s of type %s", name, proxy_type)

    @on_pre_init
    async def start_all_proxies(self) -> None:
        """Start all registered proxies."""
        for proxy in self._proxies.values():
            try:
                await proxy.start()
                self.logger.debug("Started proxy %s", proxy.proxy_id)
            except Exception as e:
                self.logger.error("Failed to start proxy %s: %s", proxy.proxy_id, e)
                raise

        # TODO: HACK: Give proxies time to initialize
        if self._proxies:
            await asyncio.sleep(1)

    @on_post_stop
    async def stop_all_proxies(self) -> None:
        """Stop all running proxies."""
        if not self._proxies:
            return

        self.logger.debug("Stopping all proxies")
        try:
            await asyncio.wait_for(
                asyncio.gather(
                    *[proxy.stop() for proxy in self._proxies.values()],
                    return_exceptions=True,
                ),
                timeout=TASK_CANCEL_TIMEOUT_SHORT,
            )
        except asyncio.TimeoutError:
            self.logger.warning("Some proxy tasks did not complete within timeout")

        self._proxies.clear()
        self.logger.debug("All proxies stopped")


class SystemControllerProxyMixin(ZMQProxyManagerMixin):
    """
    Specific proxy mixin for SystemController with the standard proxies.

    This mixin sets up the three standard proxies used by the SystemController:
    - Event Bus Proxy (XPUB/XSUB)
    - Dataset Manager Proxy (DEALER/ROUTER)
    - Raw Inference Proxy (PUSH/PULL)
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.service_config: ServiceConfig = (
            kwargs.get("service_config") or load_service_config()
        )

        # Register the three standard proxies
        self.register_proxy(
            name="event_bus",
            proxy_type=ZMQProxyType.XPUB_XSUB,
            proxy_config=self.service_config.comm_config.event_bus_proxy_config,
        )

        self.register_proxy(
            name="dataset_manager",
            proxy_type=ZMQProxyType.DEALER_ROUTER,
            proxy_config=self.service_config.comm_config.dataset_manager_proxy_config,
        )

        self.register_proxy(
            name="raw_inference",
            proxy_type=ZMQProxyType.PUSH_PULL,
            proxy_config=self.service_config.comm_config.raw_inference_proxy_config,
        )

        self.logger.debug("Registered SystemController proxies")
