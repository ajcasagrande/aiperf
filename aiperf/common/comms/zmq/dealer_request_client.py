# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import uuid

import zmq.asyncio

from aiperf.common.comms.zmq.zmq_base_client import BaseZMQClient
from aiperf.common.constants import DEFAULT_COMMS_REQUEST_TIMEOUT
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import CommClientType
from aiperf.common.factories import CommunicationClientFactory
from aiperf.common.hooks import background_task, on_stop
from aiperf.common.messages import Message
from aiperf.common.mixins import TaskManagerMixin
from aiperf.common.protocols import RequestClientProtocol
from aiperf.common.utils import yield_to_event_loop


@implements_protocol(RequestClientProtocol)
@CommunicationClientFactory.register(CommClientType.REQUEST)
class ZMQDealerRequestClient(BaseZMQClient, TaskManagerMixin):
    """
    Simplest deadlock-free solution: INFINITE BUFFERS.

    The deadlock happens when ZMQ buffers fill up. Solution: make buffers infinite.
    """

    def __init__(
        self, address: str, bind: bool, socket_ops: dict | None = None, **kwargs
    ) -> None:
        super().__init__(zmq.SocketType.DEALER, address, bind, socket_ops, **kwargs)

        # INFINITE BUFFERS - this prevents all deadlocks
        self.socket.setsockopt(zmq.SNDHWM, 0)  # 0 = infinite
        self.socket.setsockopt(zmq.RCVHWM, 0)  # 0 = infinite

        self._futures: dict[str, asyncio.Future[Message]] = {}

    @background_task(immediate=True, interval=None)
    async def _receiver(self) -> None:
        """Simple blocking receiver - no deadlock because infinite buffers."""
        while not self.stop_requested:
            try:
                message = await self.socket.recv_string()
                response = Message.from_json(message)

                if response.request_id in self._futures:
                    future = self._futures.pop(response.request_id)
                    if not future.done():
                        future.set_result(response)

            except Exception as e:
                self.error(f"Receiver error: {e!r}")
                await yield_to_event_loop()

    async def request_async(
        self, message: Message, future: asyncio.Future[Message]
    ) -> None:
        """Simple blocking send - no deadlock because infinite buffers."""
        if not message.request_id:
            message.request_id = str(uuid.uuid4())

        self._futures[message.request_id] = future
        request_json = message.model_dump_json()

        # Simple blocking send - works because buffers are infinite
        await self.socket.send_string(request_json)

    async def request(
        self, message: Message, timeout: float = DEFAULT_COMMS_REQUEST_TIMEOUT
    ) -> Message:
        """Simple request with timeout."""
        future: asyncio.Future[Message] = asyncio.Future()
        await self.request_async(message, future)
        return await asyncio.wait_for(future, timeout=timeout)

    @on_stop
    async def _cleanup(self) -> None:
        """Clean shutdown."""
        for future in self._futures.values():
            if not future.done():
                future.cancel()
        self._futures.clear()
