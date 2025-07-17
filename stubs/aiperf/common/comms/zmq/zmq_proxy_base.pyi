#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import abc
import asyncio
from abc import ABC, abstractmethod

import zmq.asyncio
from _typeshed import Incomplete
from zmq import SocketType

from aiperf.common.comms.zmq.zmq_base_client import BaseZMQClient as BaseZMQClient
from aiperf.common.config._zmq import BaseZMQProxyConfig as BaseZMQProxyConfig
from aiperf.common.constants import (
    TASK_CANCEL_TIMEOUT_SHORT as TASK_CANCEL_TIMEOUT_SHORT,
)
from aiperf.common.enums import CaseInsensitiveStrEnum as CaseInsensitiveStrEnum
from aiperf.common.enums import ZMQProxyType as ZMQProxyType
from aiperf.common.exceptions import ProxyError as ProxyError
from aiperf.common.factories import FactoryMixin as FactoryMixin
from aiperf.common.mixins import AIPerfLoggerMixin as AIPerfLoggerMixin

class ProxyEndType(CaseInsensitiveStrEnum):
    Frontend = "frontend"
    Backend = "backend"
    Capture = "capture"
    Control = "control"

class ProxySocketClient(BaseZMQClient):
    client_id: Incomplete
    def __init__(
        self,
        context: zmq.asyncio.Context,
        socket_type: SocketType,
        address: str,
        end_type: ProxyEndType,
        socket_ops: dict | None = None,
        proxy_uuid: str | None = None,
    ) -> None: ...

class BaseZMQProxy(AIPerfLoggerMixin, ABC, metaclass=abc.ABCMeta):
    proxy_uuid: Incomplete
    proxy_id: Incomplete
    context: Incomplete
    socket_ops: Incomplete
    monitor_task: asyncio.Task | None
    proxy_task: asyncio.Task | None
    control_client: ProxySocketClient | None
    capture_client: ProxySocketClient | None
    frontend_address: Incomplete
    backend_address: Incomplete
    control_address: Incomplete
    capture_address: Incomplete
    backend_socket: Incomplete
    frontend_socket: Incomplete
    def __init__(
        self,
        frontend_socket_class: type[BaseZMQClient],
        backend_socket_class: type[BaseZMQClient],
        context: zmq.asyncio.Context,
        zmq_proxy_config: BaseZMQProxyConfig,
        socket_ops: dict | None = None,
        proxy_uuid: str | None = None,
    ) -> None: ...
    @classmethod
    @abstractmethod
    def from_config(
        cls, config: BaseZMQProxyConfig | None, socket_ops: dict | None = None
    ) -> BaseZMQProxy | None: ...
    async def stop(self) -> None: ...
    async def run(self) -> None: ...

class ZMQProxyFactory(FactoryMixin[ZMQProxyType, BaseZMQProxy]): ...
