# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import zmq.asyncio

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.enums import MessageType
from aiperf.common.hooks import aiperf_task, on_cleanup
from aiperf.common.models.messages import ErrorMessage, Message


class ZMQRouterRepClient(BaseZMQClient):
    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ Router (Rep) client class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, zmq.SocketType.ROUTER, address, bind, socket_ops)

        self._request_handlers: dict[
            MessageType,
            tuple[str, Callable[[Message], Coroutine[Any, Any, Message | None]]],
        ] = {}
        self._response_futures: dict[str, asyncio.Future[Message | None]] = {}

    @on_cleanup
    async def _cleanup(self) -> None:
        self._request_handlers.clear()

    def register_request_handler(
        self,
        service_id: str,
        message_type: MessageType,
        handler: Callable[[Message], Coroutine[Any, Any, Message | None]],
    ) -> None:
        """Register a request handler.

        Args:
            service_id: The service ID to register the handler for
            message_type: The message type to register the handler for
            handler: The handler to register
        """
        self._request_handlers[message_type] = (service_id, handler)

    async def _handle_request(self, request_id: str, request_json: str) -> None:
        """Handle a request."""
        # Parse JSON to create RequestData object
        request: Message = Message.from_json(request_json)
        message_type = request.message_type

        # Call the handler
        _ = None
        try:
            _, handler = self._request_handlers[message_type]
            response = await handler(request)

        except Exception as e:
            self.logger.error("Exception calling handler for %s: %s", message_type, e)
            response = ErrorMessage(
                request_id=request.request_id,
                error=str(e),
            )

        self._response_futures[request_id].set_result(response)

    @aiperf_task
    async def _rep_receiver(self) -> None:
        """Background task for receiving requests and sending responses.

        This method is a coroutine that will run indefinitely until the client is
        shutdown. It will wait for requests from the socket and send responses.
        """
        if not self.is_initialized:
            await self.initialized_event.wait()

        while not self.is_shutdown:
            try:
                # Receive request
                try:
                    request_id, request_json = await self.socket.recv_multipart()
                except zmq.Again:
                    continue

                self._response_futures[request_id] = asyncio.Future()
                asyncio.create_task(self._handle_request(request_id, request_json))
                response = await self._response_futures[request_id]  # type: ignore
                if response is not None:
                    await self.socket.send_multipart(
                        [request_id, response.model_dump_json().encode()]
                    )
                else:
                    self.logger.warning("No response for request %s", request_id)
                    await self.socket.send_multipart([request_id, b"ERROR"])

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("Exception receiving request: %s", e)
                await asyncio.sleep(0.1)
