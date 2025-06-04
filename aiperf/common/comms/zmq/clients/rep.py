# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import logging
from collections.abc import Callable, Coroutine
from typing import Any

import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.enums import MessageType
from aiperf.common.exceptions import CommunicationResponseError
from aiperf.common.hooks import aiperf_task, on_cleanup
from aiperf.common.models import BaseMessage, ErrorMessage, ErrorPayload, Message

logger = logging.getLogger(__name__)


class ZMQRepClient(BaseZMQClient):
    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ REP class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(context, SocketType.REP, address, bind, socket_ops)

        self._request_handlers: dict[
            MessageType,
            tuple[str, Callable[[Message], Coroutine[Any, Any, Message | None]]],
        ] = {}

    @on_cleanup
    async def _cleanup(self) -> None:
        self._request_handlers.clear()

    async def respond(self, response: Message) -> None:
        """Send a response to a request.

        Args:
            response: Response message (must be a Message instance)

        Raises:
            CommunicationNotInitializedError: If the client is not initialized
            CommunicationResponseError: If the response was not sent successfully
        """
        self._ensure_initialized()

        try:
            # Serialize response using Pydantic's built-in method
            response_json = response.model_dump_json()

            # Send response
            await self.socket.send_string(response_json)

        except Exception as e:
            logger.error(f"Exception sending response: {e}")
            raise CommunicationResponseError("Exception sending response") from e

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

    async def _handle_request(self, request_json: str) -> None:
        """Handle a request."""
        # Parse JSON to create RequestData object
        request = BaseMessage.model_validate_json(request_json)
        message_type = request.payload.message_type

        # Call the handler
        service_id = None
        try:
            service_id, handler = self._request_handlers[message_type]
            response = await handler(request)

        except Exception as e:
            logger.error(f"Exception calling handler for {message_type}: {e}")
            response = ErrorMessage(
                service_id=service_id or request.service_id,
                request_id=request.request_id,
                payload=ErrorPayload(
                    error=str(e),
                ),
            )

        if response is not None:
            await self.respond(response)

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
                request_json = await self.socket.recv_string()
                asyncio.create_task(self._handle_request(request_json))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Exception receiving request: {e}")
                await asyncio.sleep(0.1)
