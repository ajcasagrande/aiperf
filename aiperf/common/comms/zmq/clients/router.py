#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import time
import uuid
from collections.abc import Callable, Coroutine
from typing import Any

import zmq
import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.enums import MessageType
from aiperf.common.hooks import aiperf_task, on_cleanup, on_init
from aiperf.common.messages import ErrorMessage, Message, MessageTypeAdapter


class ZMQRouterClient(BaseZMQClient):
    """A ZMQ Router client."""

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool = False,
        id: str | None = None,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ Router client.
        """
        super().__init__(context, SocketType.ROUTER, address, bind, socket_ops)
        # keep the id fairly short for smaller messages
        self.id = id or f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
        self._request_handlers: dict[
            MessageType,
            tuple[str, Callable[[Message], Coroutine[Any, Any, Message | None]]],
        ] = {}

    @on_cleanup
    async def _cleanup(self) -> None:
        self._request_handlers.clear()

    @on_init
    async def _on_init(self) -> None:
        """
        Initialize the ZMQ Router client's identity. Connection has already been made by base class.
        """
        # self.socket.setsockopt(zmq.IDENTITY, self.id.encode())
        self.logger.info(
            f"ROUTER[{self.id}] initialized with identity: {self.id}, Address: {self.address}"
        )

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
        self.logger.info(
            f"ROUTER[{self.id}] HANDLER REGISTERED - Service: {service_id}, Type: {message_type}"
        )

    async def _handle_request(self, request: Message) -> Message | None:
        """Handle a request."""
        # Parse JSON to create RequestData object
        message_type = request.message_type
        request_id = request.request_id

        self.logger.info(
            f"ROUTER[{self.id}] HANDLING REQUEST - ID: {request_id}, Type: {message_type}"
        )
        self.logger.debug(f"ROUTER[{self.id}] REQUEST DETAILS - {request}")

        # Check if handler is registered
        if message_type not in self._request_handlers:
            self.logger.warning(
                f"ROUTER[{self.id}] NO HANDLER - ID: {request_id}, Type: {message_type}"
            )
            return ErrorMessage(
                request_id=request_id,
                error=f"No handler registered for message type: {message_type}",
            )

        # Call the handler
        try:
            service_id, handler = self._request_handlers[message_type]
            self.logger.info(
                f"ROUTER[{self.id}] CALLING HANDLER - ID: {request_id}, Service: {service_id}"
            )

            handler_start = time.time()
            response = await handler(request)
            handler_duration = time.time() - handler_start

            if response:
                self.logger.info(
                    f"ROUTER[{self.id}] HANDLER SUCCESS - ID: {request_id}, Response Type: {response.message_type}, Duration: {handler_duration:.3f}s"
                )
                self.logger.debug(f"ROUTER[{self.id}] HANDLER RESPONSE - {response}")
            else:
                self.logger.info(
                    f"ROUTER[{self.id}] HANDLER NO RESPONSE - ID: {request_id}, Duration: {handler_duration:.3f}s"
                )

        except Exception as e:
            self.logger.error(
                f"ROUTER[{self.id}] HANDLER EXCEPTION - ID: {request_id}, Error: {e}"
            )
            response = ErrorMessage(
                request_id=request_id,
                error=str(e),
            )

        return response

    @aiperf_task
    async def _router_receiver(self) -> None:
        """Background task for receiving requests and sending responses.

        This method is a coroutine that will run indefinitely until the client is
        shutdown. It will wait for requests from the socket and handle them.
        """
        if not self.is_initialized:
            await self.initialized_event.wait()

        self.logger.info(
            f"ROUTER[{self.id}] RECEIVER STARTED - Address: {self.address}"
        )

        while not self.is_shutdown:
            try:
                # ROUTER sockets receive multipart messages: [sender_id, message, ...]
                recv_start = time.time()
                frames = await self.socket.recv_multipart()
                recv_duration = time.time() - recv_start

                frame_info = [
                    f"Frame[{i}]: {len(f)} bytes - {f[:50]!r}{'...' if len(f) > 50 else ''}"
                    for i, f in enumerate(frames)
                ]
                self.logger.info(
                    f"ROUTER[{self.id}] RECEIVED FRAMES - Count: {len(frames)}, Duration: {recv_duration:.3f}s"
                )
                self.logger.debug(f"ROUTER[{self.id}] FRAME DETAILS - {frame_info}")

                # Determine message content and sender identity
                sender_envelope = []
                request_json = ""

                if len(frames) == 0:
                    self.logger.warning(f"ROUTER[{self.id}] EMPTY MESSAGE - Skipping")
                    continue
                elif len(frames) == 1:
                    # Single frame case: [message_content]
                    # This should not happen with ROUTER sockets through a proxy, but handle it
                    self.logger.warning(
                        f"ROUTER[{self.id}] SINGLE FRAME - Unusual for ROUTER socket"
                    )
                    sender_envelope = [b"unknown"]
                    try:
                        request_json = frames[0].decode("utf-8")
                        self.logger.debug(
                            f"ROUTER[{self.id}] DECODED SINGLE FRAME - {request_json[:200]}..."
                        )
                    except UnicodeDecodeError as e:
                        self.logger.error(
                            f"ROUTER[{self.id}] DECODE ERROR - Single frame: {e}"
                        )
                        self.logger.error(
                            f"ROUTER[{self.id}] FRAME BYTES - {frames[0][:100]}..."
                        )
                        continue  # Skip this message
                elif len(frames) >= 2:
                    # Standard ROUTER case with potential proxy routing envelopes
                    # The message structure through a proxy can be:
                    # [proxy_sender_id, original_sender_id, message_content] (3 frames)
                    # [proxy_sender_id, original_sender_id, dealer_id, message_content] (4 frames)
                    # or [sender_id, message_content] (2 frames - direct connection)

                    # Find the JSON message (should be the last frame)
                    try:
                        request_json = frames[-1].decode("utf-8")
                        self.logger.debug(
                            f"ROUTER[{self.id}] TRYING LAST FRAME - {request_json[:100]}..."
                        )

                        # Verify it's JSON-like
                        if not request_json.startswith("{"):
                            # If last frame is not JSON, try frame 1 (second frame)
                            self.logger.debug(
                                f"ROUTER[{self.id}] LAST FRAME NOT JSON - Trying frame 1"
                            )
                            request_json = frames[1].decode("utf-8")
                            self.logger.debug(
                                f"ROUTER[{self.id}] FRAME 1 CONTENT - {request_json[:100]}..."
                            )
                            # In this case, sender envelope is just frame 0
                            sender_envelope = [frames[0]]
                        else:
                            # Last frame is JSON, so all preceding frames are routing envelope
                            sender_envelope = frames[:-1]

                    except UnicodeDecodeError as e:
                        self.logger.error(
                            f"ROUTER[{self.id}] DECODE ERROR - Multiframe: {e}"
                        )
                        self.logger.error(
                            f"ROUTER[{self.id}] FAILED FRAMES - {frame_info}"
                        )
                        continue
                    except IndexError as e:
                        self.logger.error(f"ROUTER[{self.id}] INDEX ERROR - {e}")
                        self.logger.error(
                            f"ROUTER[{self.id}] FRAME COUNT - {len(frames)}"
                        )
                        continue

                self.logger.info(
                    f"ROUTER[{self.id}] MESSAGE EXTRACTED - Routing Envelope: {len(sender_envelope)} frames, Message Size: {len(request_json)} bytes"
                )
                self.logger.debug(
                    f"ROUTER[{self.id}] ENVELOPE DETAILS - {[f[:20].hex() for f in sender_envelope]}"
                )
                self.logger.debug(
                    f"ROUTER[{self.id}] MESSAGE CONTENT - {request_json[:300]}..."
                )

                request = None
                try:
                    parse_start = time.time()
                    request = MessageTypeAdapter.validate_json(request_json)
                    parse_duration = time.time() - parse_start

                    self.logger.info(
                        f"ROUTER[{self.id}] MESSAGE PARSED - ID: {request.request_id}, Type: {request.message_type}, Parse Duration: {parse_duration:.3f}s"
                    )

                    handle_start = time.time()
                    result = await self._handle_request(request)
                    handle_duration = time.time() - handle_start

                    # Send response back through broker to client
                    if result:
                        response_json = result.model_dump_json()
                        response_size = len(response_json.encode("utf-8"))

                        self.logger.info(
                            f"ROUTER[{self.id}] SENDING RESPONSE - ID: {request.request_id}, Type: {result.message_type}, Size: {response_size} bytes, Handle Duration: {handle_duration:.3f}s"
                        )
                        self.logger.debug(
                            f"ROUTER[{self.id}] RESPONSE CONTENT - {response_json[:300]}..."
                        )

                        # Log details about the response routing
                        self.logger.info(
                            f"ROUTER[{self.id}] RESPONSE ROUTING - Sender ID: {sender_envelope!r} ({len(sender_envelope)} bytes)"
                        )
                        self.logger.debug(
                            f"ROUTER[{self.id}] RESPONSE ROUTING HEX - Sender ID: {[f[:20].hex() for f in sender_envelope]}"
                        )

                        send_start = time.time()
                        # ROUTER must send multipart: [sender_id, response]
                        response_frames = sender_envelope + [
                            response_json.encode("utf-8")
                        ]
                        self.logger.debug(
                            f"ROUTER[{self.id}] SENDING FRAMES - Count: {len(response_frames)}, Sizes: {[len(f) for f in response_frames]}"
                        )

                        await self.socket.send_multipart(response_frames)
                        send_duration = time.time() - send_start

                        self.logger.info(
                            f"ROUTER[{self.id}] RESPONSE SENT - ID: {request.request_id}, Send Duration: {send_duration:.3f}s"
                        )

                        # Additional verification - check if we can poll for any immediate socket events
                        post_send_events = self.socket.poll(0)
                        if post_send_events:
                            self.logger.debug(
                                f"ROUTER[{self.id}] POST-SEND EVENTS - {post_send_events}"
                            )
                    else:
                        # Send acknowledgment if no specific result
                        self.logger.info(
                            f"ROUTER[{self.id}] SENDING ACK - ID: {request.request_id}, Handle Duration: {handle_duration:.3f}s"
                        )

                        # Log ACK routing details
                        self.logger.debug(
                            f"ROUTER[{self.id}] ACK ROUTING - Sender ID: {sender_envelope!r} ({len(sender_envelope)} bytes)"
                        )

                        send_start = time.time()
                        ack_frames = sender_envelope + [b"ACK"]
                        self.logger.debug(
                            f"ROUTER[{self.id}] SENDING ACK FRAMES - Count: {len(ack_frames)}, Sizes: {[len(f) for f in ack_frames]}"
                        )

                        await self.socket.send_multipart(ack_frames)
                        send_duration = time.time() - send_start

                        self.logger.debug(
                            f"ROUTER[{self.id}] ACK SENT - ID: {request.request_id}, Send Duration: {send_duration:.3f}s"
                        )

                except Exception as e:
                    self.logger.error(
                        f"ROUTER[{self.id}] PROCESSING ERROR - ID: {getattr(request, 'request_id', 'unknown')}, Error: {e}"
                    )
                    # Send error response
                    err_response = ErrorMessage(
                        request_id=request.request_id if request else None,
                        error=str(e),
                    )
                    error_json = err_response.model_dump_json()

                    try:
                        send_start = time.time()
                        await self.socket.send_multipart(
                            sender_envelope + [error_json.encode("utf-8")]
                        )
                        send_duration = time.time() - send_start

                        self.logger.info(
                            f"ROUTER[{self.id}] ERROR RESPONSE SENT - ID: {getattr(request, 'request_id', 'unknown')}, Send Duration: {send_duration:.3f}s"
                        )
                    except Exception as send_error:
                        self.logger.error(
                            f"ROUTER[{self.id}] FAILED TO SEND ERROR RESPONSE - {send_error}"
                        )

            except asyncio.CancelledError:
                self.logger.info(f"ROUTER[{self.id}] RECEIVER CANCELLED")
                break
            except Exception as e:
                self.logger.error(f"ROUTER[{self.id}] RECEIVER ERROR - {e}")
                await asyncio.sleep(0.1)

        self.logger.info(f"ROUTER[{self.id}] RECEIVER STOPPED")
