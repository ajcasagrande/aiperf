#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from collections.abc import Callable as Callable
from collections.abc import Coroutine
from typing import Any

import zmq.asyncio
from _typeshed import Incomplete

from aiperf.common.comms.base import (
    CommunicationClientFactory as CommunicationClientFactory,
)
from aiperf.common.comms.zmq.zmq_base_client import BaseZMQClient as BaseZMQClient
from aiperf.common.enums import CommunicationClientType as CommunicationClientType
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.hooks import aiperf_task as aiperf_task
from aiperf.common.hooks import on_stop as on_stop
from aiperf.common.messages import Message as Message
from aiperf.common.mixins import AsyncTaskManagerMixin as AsyncTaskManagerMixin

class ZMQPullClient(BaseZMQClient, AsyncTaskManagerMixin):
    semaphore: Incomplete
    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
        max_concurrency: int | None = None,
    ) -> None: ...
    async def register_pull_callback(
        self,
        message_type: MessageType,
        callback: Callable[[Message], Coroutine[Any, Any, None]],
        max_concurrency: int | None = None,
    ) -> None: ...
