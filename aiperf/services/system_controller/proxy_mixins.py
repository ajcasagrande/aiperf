# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio

import zmq.asyncio

from aiperf.common.comms.zmq import BaseZMQProxy, ZMQProxyFactory
from aiperf.common.config import BaseZMQCommunicationConfig
from aiperf.common.constants import DEFAULT_PROXY_STOP_TIMEOUT_SECONDS
from aiperf.common.enums import ZMQProxyType
from aiperf.common.mixins.base_mixin import BaseMixin


class ProxyMixin(BaseMixin):
    """Mixin for the System Controller to manage proxies."""

    def __init__(self, **kwargs):
        self.event_bus_proxy: BaseZMQProxy | None = None
        self.event_bus_proxy_task: asyncio.Task | None = None

        self.dataset_manager_proxy: BaseZMQProxy | None = None
        self.dataset_manager_proxy_task: asyncio.Task | None = None

        self.raw_inference_proxy: BaseZMQProxy | None = None
        self.raw_inference_proxy_task: asyncio.Task | None = None

        super().__init__(**kwargs)

    async def run_proxies(self, comm_config: BaseZMQCommunicationConfig) -> None:
        """Run the proxies."""
        self.zmq_context = zmq.asyncio.Context.instance()

        self.event_bus_proxy = ZMQProxyFactory.create_instance(
            ZMQProxyType.XPUB_XSUB,
            context=self.zmq_context,
            zmq_proxy_config=comm_config.event_bus_proxy_config,
        )
        self.event_bus_proxy_task = asyncio.create_task(self.event_bus_proxy.run())

        self.dataset_manager_proxy = ZMQProxyFactory.create_instance(
            ZMQProxyType.DEALER_ROUTER,
            context=self.zmq_context,
            zmq_proxy_config=comm_config.dataset_manager_proxy_config,
        )
        self.dataset_manager_proxy_task = asyncio.create_task(
            self.dataset_manager_proxy.run()
        )

        self.raw_inference_proxy = ZMQProxyFactory.create_instance(
            ZMQProxyType.PUSH_PULL,
            context=self.zmq_context,
            zmq_proxy_config=comm_config.raw_inference_proxy_config,
        )
        self.raw_inference_proxy_task = asyncio.create_task(
            self.raw_inference_proxy.run()
        )

    async def stop_proxies(self) -> None:
        """Stop the proxies."""

        stop_tasks: list[asyncio.Task] = []
        if self.event_bus_proxy:
            stop_tasks.append(asyncio.create_task(self.event_bus_proxy.stop()))
        if self.dataset_manager_proxy:
            stop_tasks.append(asyncio.create_task(self.dataset_manager_proxy.stop()))
        if self.raw_inference_proxy:
            stop_tasks.append(asyncio.create_task(self.raw_inference_proxy.stop()))

        tasks: list[asyncio.Task] = [
            task
            for task in [
                self.event_bus_proxy_task,
                self.dataset_manager_proxy_task,
                self.raw_inference_proxy_task,
            ]
            if task
        ]

        for task in tasks:
            task.cancel()

        await asyncio.wait_for(
            asyncio.gather(*[*stop_tasks, *tasks], return_exceptions=True),
            timeout=DEFAULT_PROXY_STOP_TIMEOUT_SECONDS,
        )

        if self.zmq_context:
            self.zmq_context.term()

        self.zmq_context = None
