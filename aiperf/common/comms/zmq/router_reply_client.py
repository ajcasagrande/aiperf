# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import zmq.asyncio

from aiperf.common.comms.zmq.zmq_base_client import BaseZMQClient
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import CommClientType
from aiperf.common.factories import CommunicationClientFactory
from aiperf.common.hooks import background_task, on_stop
from aiperf.common.messages import ErrorMessage, Message
from aiperf.common.models import ErrorDetails
from aiperf.common.protocols import ReplyClientProtocol
from aiperf.common.types import MessageTypeT


@implements_protocol(ReplyClientProtocol)
@CommunicationClientFactory.register(CommClientType.REPLY)
class ZMQRouterReplyClient(BaseZMQClient):
    """
    Simple deadlock-free ZMQ ROUTER client using infinite buffers.
    """

    def __init__(
        self, address: str, bind: bool, socket_ops: dict | None = None, **kwargs
    ) -> None:
        super().__init__(zmq.SocketType.ROUTER, address, bind, socket_ops, **kwargs)

        # INFINITE BUFFERS - prevents all deadlocks
        self.socket.setsockopt(zmq.SNDHWM, 0)  # 0 = infinite
        self.socket.setsockopt(zmq.RCVHWM, 0)  # 0 = infinite

        self._request_handlers: dict[
            MessageTypeT,
            tuple[str, Callable[[Message], Coroutine[Any, Any, Message | None]]],
        ] = {}
        self._response_futures: dict[str, asyncio.Future[Message | None]] = {}

    @on_stop
    async def _clear_request_handlers(self) -> None:
        """Clear request handlers."""
        self._request_handlers.clear()

    def register_request_handler(
        self,
        service_id: str,
        message_type: MessageTypeT,
        handler: Callable[[Message], Coroutine[Any, Any, Message | None]],
    ) -> None:
        """Register a request handler."""
        if message_type in self._request_handlers:
            raise ValueError(
                f"Handler already registered for message type {message_type}"
            )
        self._request_handlers[message_type] = (service_id, handler)

    async def _handle_request(self, request_id: str, request: Message) -> None:
        """Handle a request."""
        message_type = request.message_type

        try:
            _, handler = self._request_handlers[message_type]
            response = await handler(request)
        except Exception as e:
            response = ErrorMessage(
                request_id=request_id,
                error=ErrorDetails.from_exception(e),
            )

        try:
            self._response_futures[request_id].set_result(response)
        except Exception as e:
            self.error(
                f"Exception setting response future for request {request_id}: {e}"
            )

    async def _wait_for_response(
        self, request_id: str, routing_envelope: tuple[bytes, ...]
    ) -> None:
        """Wait for a response and send it."""
        try:
            response = await self._response_futures[request_id]

            if response is None:
                response = ErrorMessage(
                    request_id=request_id,
                    error=ErrorDetails(
                        type="NO_RESPONSE",
                        message="No response was generated for the request.",
                    ),
                )

            self._response_futures.pop(request_id, None)

            # Simple blocking send - works because buffers are infinite
            response_data = [*routing_envelope, response.model_dump_json().encode()]
            await self.socket.send_multipart(response_data)

        except Exception as e:
            self.error(f"Exception waiting for response for request {request_id}: {e}")

    @background_task(immediate=True, interval=None)
    async def _rep_router_receiver(self) -> None:
        """Simple blocking receiver - no deadlock because infinite buffers."""
        while not self.stop_requested:
            try:
                data = await self.socket.recv_multipart()
                request = Message.from_json(data[-1])
                if not request.request_id:
                    continue

                routing_envelope = (
                    tuple(data[:-1])
                    if len(data) > 1
                    else (request.request_id.encode(),)
                )

                # Create future and handle request
                self._response_futures[request.request_id] = asyncio.Future()
                self.execute_async(self._handle_request(request.request_id, request))
                self.execute_async(
                    self._wait_for_response(request.request_id, routing_envelope)
                )

            except Exception as e:
                self.error(f"Receiver error: {e}")
                await asyncio.sleep(0.001)
