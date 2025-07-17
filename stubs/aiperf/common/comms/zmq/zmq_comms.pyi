#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio
from abc import ABC

from _typeshed import Incomplete

from aiperf.common.comms.base import BaseCommunication as BaseCommunication
from aiperf.common.comms.base import (
    CommunicationClientFactory as CommunicationClientFactory,
)
from aiperf.common.comms.base import (
    CommunicationClientProtocol as CommunicationClientProtocol,
)
from aiperf.common.comms.base import CommunicationFactory as CommunicationFactory
from aiperf.common.comms.zmq.zmq_base_client import BaseZMQClient as BaseZMQClient
from aiperf.common.config import (
    BaseZMQCommunicationConfig as BaseZMQCommunicationConfig,
)
from aiperf.common.config._zmq import ZMQIPCConfig as ZMQIPCConfig
from aiperf.common.config._zmq import ZMQTCPConfig as ZMQTCPConfig
from aiperf.common.enums import CommunicationBackend as CommunicationBackend
from aiperf.common.enums import (
    CommunicationClientAddressType as CommunicationClientAddressType,
)
from aiperf.common.enums import CommunicationClientType as CommunicationClientType
from aiperf.common.exceptions import ShutdownError as ShutdownError
from aiperf.common.mixins import AIPerfLoggerMixin as AIPerfLoggerMixin

class BaseZMQCommunication(BaseCommunication, AIPerfLoggerMixin, ABC):
    stop_event: asyncio.Event
    initialized_event: asyncio.Event
    config: Incomplete
    context: Incomplete
    clients: list[BaseZMQClient]
    def __init__(self, config: BaseZMQCommunicationConfig) -> None: ...
    @property
    def is_initialized(self) -> bool: ...
    @property
    def stop_requested(self) -> bool: ...
    def get_address(
        self, address_type: CommunicationClientAddressType | str
    ) -> str: ...
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
    def create_client(
        self,
        client_type: CommunicationClientType,
        address: CommunicationClientAddressType | str,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> CommunicationClientProtocol: ...

class ZMQTCPCommunication(BaseZMQCommunication):
    def __init__(self, config: ZMQTCPConfig | None = None) -> None: ...

class ZMQIPCCommunication(BaseZMQCommunication):
    def __init__(self, config: ZMQIPCConfig | None = None) -> None: ...
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
