#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import zmq.asyncio

from aiperf.common.comms.base import (
    CommunicationClientFactory as CommunicationClientFactory,
)
from aiperf.common.comms.zmq.zmq_base_client import BaseZMQClient as BaseZMQClient
from aiperf.common.enums import CommunicationClientType as CommunicationClientType
from aiperf.common.exceptions import CommunicationError as CommunicationError
from aiperf.common.messages import Message as Message
from aiperf.common.mixins import AsyncTaskManagerMixin as AsyncTaskManagerMixin

MAX_PUSH_RETRIES: int

class ZMQPushClient(BaseZMQClient, AsyncTaskManagerMixin):
    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None: ...
    async def push(self, message: Message) -> None: ...
