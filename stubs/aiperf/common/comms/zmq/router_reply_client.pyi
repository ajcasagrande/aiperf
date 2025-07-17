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
from aiperf.common.hooks import on_cleanup as on_cleanup
from aiperf.common.hooks import on_stop as on_stop
from aiperf.common.messages import ErrorMessage as ErrorMessage
from aiperf.common.messages import Message as Message
from aiperf.common.mixins import AsyncTaskManagerMixin as AsyncTaskManagerMixin
from aiperf.common.record_models import ErrorDetails as ErrorDetails

class ZMQRouterReplyClient(BaseZMQClient, AsyncTaskManagerMixin):
    logger: Incomplete
    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None: ...
    def register_request_handler(
        self,
        service_id: str,
        message_type: MessageType,
        handler: Callable[[Message], Coroutine[Any, Any, Message | None]],
    ) -> None: ...
