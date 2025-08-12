# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import zmq.asyncio

from aiperf.common.constants import (
    DEFAULT_MAX_REQUEST_QUEUE_SIZE,
    DEFAULT_MAX_RESPONSE_QUEUE_SIZE,
)
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import CommClientType
from aiperf.common.factories import CommunicationClientFactory
from aiperf.common.hooks import background_task, on_stop
from aiperf.common.messages import ErrorMessage, Message
from aiperf.common.models import ErrorDetails
from aiperf.common.protocols import ReplyClientProtocol
from aiperf.common.types import MessageTypeT
from aiperf.common.utils import yield_to_event_loop
from aiperf.zmq.zmq_base_client import BaseZMQClient


@implements_protocol(ReplyClientProtocol)
@CommunicationClientFactory.register(CommClientType.REPLY)
class ZMQRouterReplyClient(BaseZMQClient):
    """
    ZMQ ROUTER socket client for handling requests from DEALER clients.

    The ROUTER socket receives requests from DEALER clients and sends responses
    back to the originating DEALER client using routing envelopes.

    ASCII Diagram:
    ┌──────────────┐                    ┌──────────────┐
    │    DEALER    │───── Request ─────>│              │
    │   (Client)   │<──── Response ─────│              │
    └──────────────┘                    │              │
    ┌──────────────┐                    │    ROUTER    │
    │    DEALER    │───── Request ─────>│  (Service)   │
    │   (Client)   │<──── Response ─────│              │
    └──────────────┘                    │              │
    ┌──────────────┐                    │              │
    │    DEALER    │───── Request ─────>│              │
    │   (Client)   │<──── Response ─────│              │
    └──────────────┘                    └──────────────┘

    Usage Pattern:
    - ROUTER handles requests from multiple DEALER clients
    - Maintains routing envelopes to send responses back
    - Many-to-one request handling pattern
    - Supports concurrent request processing

    ROUTER/DEALER is a Many-to-One communication pattern. If you need Many-to-Many,
    use a ZMQ Proxy as well. see :class:`ZMQDealerRouterProxy` for more details.
    """

    def __init__(
        self,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
        **kwargs,
    ) -> None:
        """
        Initialize the ZMQ Router (Rep) client class.

        Args:
            address (str): The address to bind or connect to.
            bind (bool): Whether to bind or connect the socket.
            socket_ops (dict, optional): Additional socket options to set.
        """
        super().__init__(zmq.SocketType.ROUTER, address, bind, socket_ops, **kwargs)

        self._request_handlers: dict[
            MessageTypeT,
            tuple[str, Callable[[Message], Coroutine[Any, Any, Message | None]]],
        ] = {}

        self._request_queue: asyncio.Queue[tuple[tuple[bytes, ...], Message]] = (
            asyncio.Queue(maxsize=DEFAULT_MAX_REQUEST_QUEUE_SIZE)
        )

        self._response_queue: asyncio.Queue[
            tuple[str, tuple[bytes, ...], Message | None]
        ] = asyncio.Queue(maxsize=DEFAULT_MAX_RESPONSE_QUEUE_SIZE)

    @on_stop
    async def _clear_request_handlers(self) -> None:
        self._request_handlers.clear()

    def register_request_handler(
        self,
        service_id: str,
        message_type: MessageTypeT,
        handler: Callable[[Message], Coroutine[Any, Any, Message | None]],
    ) -> None:
        """Register a request handler. Anytime a request is received that matches the
        message type, the handler will be called. The handler should return a response
        message. If the handler returns None, the request will be ignored.

        Note that there is a limit of 1 to 1 mapping between message type and handler.

        Args:
            service_id: The service ID to register the handler for
            message_type: The message type to register the handler for
            handler: The handler to register
        """
        if message_type in self._request_handlers:
            raise ValueError(
                f"Handler already registered for message type {message_type}"
            )

        self.debug(
            lambda service_id=service_id,
            type=message_type: f"Registering request handler for {service_id} with message type {type}"
        )
        self._request_handlers[message_type] = (service_id, handler)

    @background_task(immediate=True, interval=None)
    async def _request_queue_processor(self) -> None:
        """Background task for processing requests from the request queue."""
        while not self.stop_requested:
            try:
                routing_envelope, request = await self._request_queue.get()
                # self.execute_async(self._handle_request(routing_envelope, request))
                await self._handle_request(routing_envelope, request)
                self._request_queue.task_done()
            except asyncio.CancelledError:
                self.debug("Router reply client request queue processor task cancelled")
                break
            except Exception as e:
                self.error(f"Exception processing request from queue: {e}")
                await yield_to_event_loop()

    @background_task(immediate=True, interval=None)
    async def _response_queue_processor(self) -> None:
        """Background task for processing responses from the response queue."""
        while not self.stop_requested:
            try:
                (
                    request_id,
                    routing_envelope,
                    response,
                ) = await self._response_queue.get()
                # NOTE: It has been benchmarked that awaiting the send_multipart is faster than using execute_async.
                #       to send the response during high concurrency.
                await self._send_response(request_id, routing_envelope, response)
                self._response_queue.task_done()
            except asyncio.CancelledError:
                self.debug(
                    "Router reply client response queue processor task cancelled"
                )
                break
            except Exception as e:
                self.error(f"Exception processing response from queue: {e!r}")
                await yield_to_event_loop()

    async def _send_response(
        self,
        request_id: str,
        routing_envelope: tuple[bytes, ...],
        response: Message | None,
    ) -> None:
        """Send a response to the client."""
        if response is None:
            self.warning(f"Got None as response for request {request_id}")
            response = ErrorMessage(
                request_id=request_id,
                error=ErrorDetails(
                    type="NO_RESPONSE",
                    message="No response was generated for the request.",
                ),
            )
        await self.socket.send_multipart(
            [*routing_envelope, response.model_dump_json().encode()]
        )

    @background_task(immediate=True, interval=None)
    async def _rep_router_receiver(self) -> None:
        """Background task for receiving requests and sending responses.

        This method is a coroutine that will run indefinitely until the client is
        shutdown. It will wait for requests from the socket and send responses in
        an asynchronous manner.
        """
        self.debug("Router reply client background task initialized")

        # cache is_trace_enabled to avoid attr lookup in loop
        _is_trace_enabled = self.is_trace_enabled

        while not self.stop_requested:
            try:
                # Receive request
                try:
                    data = await self.socket.recv_multipart()
                    if _is_trace_enabled:
                        self.trace(f"Received request: {data}")

                    request = Message.from_json(data[-1])
                    if not request.request_id:
                        self.error(f"Request ID is missing from request: {data}")
                        continue

                    routing_envelope: tuple[bytes, ...] = (
                        tuple(data[:-1])
                        if len(data) > 1
                        else (request.request_id.encode(),)
                    )
                except zmq.Again:
                    # This means we timed out waiting for a request.
                    # We can continue to the next iteration of the loop.
                    self.debug(
                        "Router reply client receiver task timed out waiting for requests. "
                        "This is normal if there are no requests for a while."
                    )
                    await yield_to_event_loop()
                    continue

                try:
                    self._request_queue.put_nowait((routing_envelope, request))
                except asyncio.QueueFull:
                    self.error(
                        f"Request queue is full for request {request.request_id}. "
                        "Waiting for an open slot. This will cause back pressure."
                    )
                    await self._request_queue.put((routing_envelope, request))
                    self.debug(
                        "Router reply client receiver task put request in queue."
                    )

            except Exception as e:
                self.error(f"Exception receiving request: {e!r}")
                await yield_to_event_loop()
            except asyncio.CancelledError:
                self.debug("Router reply client receiver task cancelled")
                break

    async def _handle_request(
        self, routing_envelope: tuple[bytes, ...], request: Message
    ) -> None:
        """Handle a request.

        This method will:
        - Parse the request JSON to create a Message object
        - Call the handler for the message type
        - Set the response future
        """
        message_type = request.message_type

        try:
            _, handler = self._request_handlers[message_type]
            response = await handler(request)

        except Exception as e:
            self.exception(f"Exception calling handler for {message_type}: {e}")
            response = ErrorMessage(
                request_id=request.request_id,
                error=ErrorDetails.from_exception(e),
            )

        await self._send_response(request.request_id, routing_envelope, response)
