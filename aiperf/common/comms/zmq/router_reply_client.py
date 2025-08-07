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
    Robust deadlock-free ZMQ ROUTER client using infinite buffers.
    Handles request-reply patterns with proper error handling and cleanup.
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
    async def _cleanup_resources(self) -> None:
        """Clean up request handlers and cancel pending futures."""
        # Cancel all pending futures to prevent memory leaks
        for request_id, future in self._response_futures.items():
            if not future.done():
                future.cancel()
                self.debug(
                    "Cancelled pending response future for request %s", request_id
                )

        self._response_futures.clear()
        self._request_handlers.clear()

    def register_request_handler(
        self,
        service_id: str,
        message_type: MessageTypeT,
        handler: Callable[[Message], Coroutine[Any, Any, Message | None]],
    ) -> None:
        """Register a request handler for a specific message type."""
        if message_type in self._request_handlers:
            raise ValueError(
                "Handler already registered for message type %s" % message_type
            )
        self._request_handlers[message_type] = (service_id, handler)
        self.debug("Registered handler for message type %s", message_type)

    async def _handle_request(self, request_id: str, request: Message) -> None:
        """Handle a request with comprehensive error handling."""
        try:
            # Check if handler exists
            if request.message_type not in self._request_handlers:
                response = ErrorMessage(
                    request_id=request_id,
                    error=ErrorDetails(
                        type="HANDLER_NOT_FOUND",
                        message="No handler registered for message type %s"
                        % request.message_type,
                    ),
                )
            else:
                _, handler = self._request_handlers[request.message_type]
                response = await handler(request)

        except asyncio.CancelledError:
            self.debug("Request handling cancelled for request %s", request_id)
            response = ErrorMessage(
                request_id=request_id,
                error=ErrorDetails(
                    type="CANCELLED",
                    message="Request processing was cancelled",
                ),
            )
        except Exception as e:
            self.error("Exception handling request %s: %s", request_id, e)
            response = ErrorMessage(
                request_id=request_id,
                error=ErrorDetails.from_exception(e),
            )

        # Set response future result safely
        try:
            future = self._response_futures.get(request_id)
            if future and not future.cancelled():
                future.set_result(response)
            elif not future:
                self.warning("No response future found for request %s", request_id)
        except Exception as e:
            self.error(
                "Exception setting response future for request %s: %s", request_id, e
            )

    async def _wait_for_response(
        self, request_id: str, routing_envelope: tuple[bytes, ...]
    ) -> None:
        """Wait for response and send it with proper error handling."""
        try:
            future = self._response_futures.get(request_id)
            if not future:
                self.error("No response future found for request %s", request_id)
                return

            response = await future

            if response is None:
                response = ErrorMessage(
                    request_id=request_id,
                    error=ErrorDetails(
                        type="NO_RESPONSE",
                        message="No response was generated for the request",
                    ),
                )

            # Send response with proper serialization error handling
            try:
                response_json = response.model_dump_json()
                response_data = [*routing_envelope, response_json.encode()]
                await self.socket.send_multipart(response_data)
                self.trace("Sent response for request %s", request_id)
            except Exception as e:
                self.error(
                    "Failed to serialize or send response for request %s: %s",
                    request_id,
                    e,
                )

        except asyncio.CancelledError:
            self.debug("Response wait cancelled for request %s", request_id)
        except Exception as e:
            self.error(
                "Exception waiting for response for request %s: %s", request_id, e
            )
        finally:
            # Always clean up the future to prevent memory leaks
            self._response_futures.pop(request_id, None)

    @background_task(immediate=True, interval=None)
    async def _rep_router_receiver(self) -> None:
        """Robust receiver with comprehensive error handling and validation."""
        while not self.stop_requested:
            try:
                data = await self.socket.recv_multipart()

                # Validate message structure
                if not data:
                    self.warning("Received empty multipart message")
                    continue

                # Parse and validate message
                try:
                    request = Message.from_json(data[-1])
                except Exception as e:
                    self.error("Failed to parse message: %s", e)
                    continue

                # Validate request_id
                if not request.request_id or not request.request_id.strip():
                    self.warning("Received message without valid request_id")
                    continue

                # Extract routing envelope
                routing_envelope = (
                    tuple(data[:-1])
                    if len(data) > 1
                    else (request.request_id.encode(),)
                )

                # Check for duplicate request_id
                if request.request_id in self._response_futures:
                    self.warning(
                        "Duplicate request_id received: %s", request.request_id
                    )
                    continue

                # Create future and handle request
                self._response_futures[request.request_id] = asyncio.Future()

                # Launch async tasks for request handling
                self.execute_async(self._handle_request(request.request_id, request))
                self.execute_async(
                    self._wait_for_response(request.request_id, routing_envelope)
                )

            except asyncio.CancelledError:
                self.debug("Receiver cancelled during graceful shutdown")
                break
            except zmq.ContextTerminated:
                self.debug("ZMQ context terminated, stopping receiver")
                break
            except Exception as e:
                self.error("Receiver error: %s", e)
                # Small delay to prevent tight error loops
                await asyncio.sleep(0.001)
