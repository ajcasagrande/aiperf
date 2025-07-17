#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio

from _typeshed import Incomplete

from aiperf.common.comms.zmq import BaseZMQProxy as BaseZMQProxy
from aiperf.common.comms.zmq import ZMQProxyFactory as ZMQProxyFactory
from aiperf.common.config import (
    BaseZMQCommunicationConfig as BaseZMQCommunicationConfig,
)
from aiperf.common.enums import ZMQProxyType as ZMQProxyType

class ProxyMixin:
    event_bus_proxy: BaseZMQProxy | None
    event_bus_proxy_task: asyncio.Task | None
    dataset_manager_proxy: BaseZMQProxy | None
    dataset_manager_proxy_task: asyncio.Task | None
    raw_inference_proxy: BaseZMQProxy | None
    raw_inference_proxy_task: asyncio.Task | None
    def __init__(self, *args, **kwargs) -> None: ...
    zmq_context: Incomplete
    async def run_proxies(self, comm_config: BaseZMQCommunicationConfig) -> None: ...
    async def stop_proxies(self) -> None: ...
