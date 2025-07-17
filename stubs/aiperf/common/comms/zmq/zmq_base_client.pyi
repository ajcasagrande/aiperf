#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import asyncio

import zmq
import zmq.asyncio

from aiperf.common.comms.zmq.zmq_defaults import ZMQSocketDefaults as ZMQSocketDefaults
from aiperf.common.exceptions import AIPerfError as AIPerfError
from aiperf.common.exceptions import CommunicationError as CommunicationError
from aiperf.common.exceptions import InitializationError as InitializationError
from aiperf.common.hooks import AIPerfHook as AIPerfHook
from aiperf.common.hooks import AIPerfTaskHook as AIPerfTaskHook
from aiperf.common.mixins import AIPerfLoggerMixin as AIPerfLoggerMixin
from aiperf.common.mixins import AIPerfTaskMixin as AIPerfTaskMixin
from aiperf.common.mixins import supports_hooks as supports_hooks

class BaseZMQClient(AIPerfTaskMixin, AIPerfLoggerMixin):
    stop_event: asyncio.Event
    initialized_event: asyncio.Event
    context: zmq.asyncio.Context
    address: str
    bind: bool
    socket_type: zmq.SocketType
    socket_ops: dict
    client_id: str
    def __init__(
        self,
        context: zmq.asyncio.Context,
        socket_type: zmq.SocketType,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
        client_id: str | None = None,
    ) -> None: ...
    @property
    def is_initialized(self) -> bool: ...
    @property
    def stop_requested(self) -> bool: ...
    @property
    def socket_type_name(self) -> str: ...
    @property
    def socket(self) -> zmq.asyncio.Socket: ...
    async def initialize(self) -> None: ...
    async def shutdown(self) -> None: ...
