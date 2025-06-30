# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import zmq.asyncio

from aiperf.common.comms.base import ReqClient
from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.exceptions import CommunicationError, CommunicationErrorReason
from aiperf.common.hooks import aiperf_task
from aiperf.common.models import Message


class ZMQDealerReqClient(BaseZMQClient, ReqClient):
    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ Dealer (Req) client class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, zmq.SocketType.DEALER, address, bind, socket_ops)

        self.request_callbacks: dict[
            str, Callable[[Message], Coroutine[Any, Any, None]]
        ] = {}

    @aiperf_task
    async def _request_async_task(self) -> None:
        """Task to handle incoming requests."""
        while not self.stop_event.is_set():
            try:
                message = await self._socket.recv_string()
                self.logger.debug("Received response: %s", message)
                response_message = Message.from_json(message)

                # Call the callback if it exists
                if response_message.request_id in self.request_callbacks:
                    callback = self.request_callbacks.pop(response_message.request_id)
                    asyncio.create_task(callback(response_message))

            except (asyncio.CancelledError, zmq.ContextTerminated):
                raise  # re-raise the cancelled error

            except Exception as e:
                raise CommunicationError(
                    CommunicationErrorReason.RESPONSE_ERROR,
                    f"Exception receiving responses: {e.__class__.__name__} {e}",
                ) from e

    async def request_async(
        self,
        message: Message,
        callback: Callable[[Message], Coroutine[Any, Any, None]],
    ) -> None:
        """Send a request and be notified when the response is received."""
        await self._ensure_initialized()

        # Generate request ID if not provided
        if not message.request_id:
            message.request_id = uuid.uuid4().hex

        self.request_callbacks[message.request_id] = callback

        request_json = message.model_dump_json()
        self.logger.debug("Sending request: %s", request_json)

        try:
            await self._socket.send_string(request_json)

        except Exception as e:
            raise CommunicationError(
                CommunicationErrorReason.REQUEST_ERROR,
                f"Exception sending request: {e.__class__.__name__} {e}",
            ) from e

    async def request(
        self,
        message: Message,
        timeout: float = 10,
    ) -> Message:
        """Send a request and wait for a response."""
        future = asyncio.Future[Message]()

        async def callback(x: Message) -> None:
            future.set_result(x)

        await self.request_async(message, callback)
        return await asyncio.wait_for(future, timeout=timeout)
