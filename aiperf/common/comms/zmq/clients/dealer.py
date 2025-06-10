#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import time
import uuid

import zmq
import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.exceptions import CommunicationError
from aiperf.common.hooks import aiperf_task, on_cleanup, on_init
from aiperf.common.messages import Message, MessageTypeAdapter


class ZMQDealerClient(BaseZMQClient):
    """A ZMQ Dealer client with proper request/response correlation using futures."""

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool = False,
        id: str | None = None,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ Dealer client.
        """
        super().__init__(context, SocketType.DEALER, address, bind, socket_ops)
        # keep the id fairly short for smaller messages
        self.id = id or f"{os.getpid()}_{uuid.uuid4().hex[:8]}"

        # Request correlation using futures keyed by request_id
        self._pending_requests: dict[str, asyncio.Future[Message]] = {}
        self._receiver_running = False

    @on_init
    async def _on_init(self) -> None:
        """
        Initialize the ZMQ Dealer client's identity.
        """
        self.socket.setsockopt(zmq.IDENTITY, self.id.encode())
        self.logger.debug(f"DEALER[{self.id}] initialized with identity: {self.id}")
        self._receiver_running = True

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up the dealer client."""
        self._receiver_running = False

        # Cancel any pending requests
        for request_id, future in self._pending_requests.items():
            if not future.done():
                future.set_exception(CommunicationError("Client is shutting down"))
        self._pending_requests.clear()

    @aiperf_task
    async def _response_receiver(self) -> None:
        """Background task to receive and correlate responses using request_id."""
        self.logger.debug(f"DEALER[{self.id}] RESPONSE RECEIVER STARTED")

        while self._receiver_running and not self.is_shutdown:
            try:
                # Use non-blocking receive with a short timeout
                if self.socket.poll(100):  # 100ms timeout
                    response_frames = await self.socket.recv_multipart(zmq.NOBLOCK)

                    # Extract the actual response content from the frames
                    response_json = None
                    if len(response_frames) == 1:
                        response_json = response_frames[0].decode("utf-8")
                    elif len(response_frames) >= 2:
                        # Try the last frame first (most likely to be the response)
                        try:
                            response_json = response_frames[-1].decode("utf-8")
                            # Verify it looks like JSON
                            if not response_json.startswith("{"):
                                # If last frame doesn't look like JSON, try frame 0
                                response_json = response_frames[0].decode("utf-8")
                        except UnicodeDecodeError:
                            # Try frame 0 if last frame decode fails
                            response_json = response_frames[0].decode("utf-8")

                    if response_json:
                        try:
                            # Parse the response to get the request_id
                            response_message = MessageTypeAdapter.validate_json(
                                response_json
                            )
                            request_id = response_message.request_id

                            self.logger.debug(
                                f"DEALER[{self.id}] RECEIVED RESPONSE - ID: {request_id}"
                            )

                            # Find the waiting future for this request_id
                            if request_id in self._pending_requests:
                                future = self._pending_requests.pop(request_id)
                                if not future.done():
                                    future.set_result(response_message)
                                    self.logger.debug(
                                        f"DEALER[{self.id}] CORRELATED RESPONSE - ID: {request_id}"
                                    )
                                else:
                                    self.logger.warning(
                                        f"DEALER[{self.id}] FUTURE ALREADY DONE - ID: {request_id}"
                                    )
                            else:
                                self.logger.warning(
                                    f"DEALER[{self.id}] UNEXPECTED RESPONSE - ID: {request_id}"
                                )

                        except Exception as e:
                            self.logger.error(
                                f"DEALER[{self.id}] RESPONSE PARSE ERROR - {e}"
                            )
                            # If we can't parse request_id, try to correlate with oldest pending request
                            if self._pending_requests:
                                oldest_id = next(iter(self._pending_requests))
                                future = self._pending_requests.pop(oldest_id)
                                if not future.done():
                                    future.set_exception(
                                        CommunicationError(f"Parse error: {e}")
                                    )

            except zmq.Again:
                # No message available, continue loop
                continue
            except asyncio.CancelledError:
                self.logger.debug(f"DEALER[{self.id}] RESPONSE RECEIVER CANCELLED")
                break
            except Exception as e:
                self.logger.error(f"DEALER[{self.id}] RESPONSE RECEIVER ERROR - {e}")
                await asyncio.sleep(0.1)  # Brief pause on error

        self.logger.debug(f"DEALER[{self.id}] RESPONSE RECEIVER STOPPED")

    async def request(self, message: Message, timeout: float = 300.0) -> Message:
        """Send a message and await response using request_id correlation.

        Args:
            message: The message to send
            timeout: The timeout in seconds

        Returns:
            The response from the dealer

        Raises:
            CommunicationTimeoutError: If the request times out
            CommunicationError: If there's an error with the communication
        """

        # Ensure client is initialized
        self._ensure_initialized()

        # Generate request ID if not provided
        if not message.request_id:
            message.request_id = uuid.uuid4().hex

        request_start_time = time.time()
        self.logger.info(
            f"DEALER[{self.id}] REQUEST START - ID: {message.request_id}, Type: {message.message_type}, Target: {self.address}"
        )
        self.logger.debug(f"DEALER[{self.id}] REQUEST DETAILS - Message: {message}")

        # Create future for this request_id
        response_future: asyncio.Future[Message] = asyncio.Future()
        self._pending_requests[message.request_id] = response_future

        try:
            # Convert to JSON and send
            data = message.model_dump_json()
            data_size = len(data.encode("utf-8"))
            self.logger.info(
                f"DEALER[{self.id}] SENDING REQUEST - ID: {message.request_id}, Size: {data_size} bytes"
            )
            self.logger.debug(
                f"DEALER[{self.id}] REQUEST DATA - {data[:500]}{'...' if len(data) > 500 else ''}"
            )

            send_start = time.time()
            await self.socket.send_multipart([self.id.encode(), data.encode()])
            send_duration = time.time() - send_start
            self.logger.debug(
                f"DEALER[{self.id}] REQUEST SENT - ID: {message.request_id}, Send duration: {send_duration:.3f}s"
            )

            # Wait for response using the future with timeout
            try:
                response_message = await asyncio.wait_for(
                    response_future, timeout=timeout
                )

                total_duration = time.time() - request_start_time
                self.logger.info(
                    f"DEALER[{self.id}] REQUEST COMPLETE - ID: {message.request_id}, Response Type: {response_message.message_type}, Total Duration: {total_duration:.3f}s"
                )
                self.logger.debug(
                    f"DEALER[{self.id}] PARSED RESPONSE - {response_message}"
                )

                return response_message

            except asyncio.TimeoutError:
                total_duration = time.time() - request_start_time
                self.logger.error(
                    f"DEALER[{self.id}] REQUEST TIMEOUT - ID: {message.request_id}, Duration: {total_duration:.3f}s, Expected: {timeout}s"
                )
                raise CommunicationError(f"Request timed out after {timeout} seconds")

        except CommunicationError:
            total_duration = time.time() - request_start_time
            self.logger.error(
                f"DEALER[{self.id}] REQUEST FAILED - ID: {message.request_id}, Duration: {total_duration:.3f}s"
            )
            raise  # Re-raise communication errors
        except Exception as e:
            total_duration = time.time() - request_start_time
            self.logger.error(
                f"DEALER[{self.id}] REQUEST EXCEPTION - ID: {message.request_id}, Duration: {total_duration:.3f}s, Error: {e}"
            )
            raise CommunicationError(f"Dealer request failed: {e}") from e
        finally:
            # Clean up the pending request if it wasn't consumed by the receiver
            self._pending_requests.pop(message.request_id, None)

    async def send_message(self, message: Message) -> None:
        """Send a message without expecting a response (fire and forget).

        Args:
            message: The message to send

        Raises:
            CommunicationError: If there's an error sending the message
        """
        try:
            # Ensure client is initialized
            self._ensure_initialized()

            # Generate request ID if not provided
            if not message.request_id:
                message.request_id = uuid.uuid4().hex

            self.logger.info(
                f"DEALER[{self.id}] FIRE-AND-FORGET START - ID: {message.request_id}, Type: {message.message_type}"
            )
            self.logger.debug(f"DEALER[{self.id}] FIRE-AND-FORGET MESSAGE - {message}")

            # Convert to JSON and send
            data = message.model_dump_json()
            data_size = len(data.encode("utf-8"))

            send_start = time.time()
            await self.socket.send_multipart([self.id.encode(), data.encode()])
            send_duration = time.time() - send_start

            self.logger.info(
                f"DEALER[{self.id}] FIRE-AND-FORGET SENT - ID: {message.request_id}, Size: {data_size} bytes, Duration: {send_duration:.3f}s"
            )

        except Exception as e:
            self.logger.error(
                f"DEALER[{self.id}] FIRE-AND-FORGET ERROR - ID: {getattr(message, 'request_id', 'unknown')}, Error: {e}"
            )
            raise CommunicationError(f"Dealer send failed: {e}") from e
