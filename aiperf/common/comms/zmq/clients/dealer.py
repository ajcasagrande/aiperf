#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import os
import time
import uuid

import zmq
import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.exceptions import CommunicationError
from aiperf.common.hooks import on_init
from aiperf.common.messages import Message, MessageTypeAdapter


class ZMQDealerClient(BaseZMQClient):
    """A ZMQ Dealer client."""

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

    @on_init
    async def _on_init(self) -> None:
        """
        Initialize the ZMQ Dealer client's identity. Connection has already been made.
        """
        # self.socket.setsockopt(zmq.IDENTITY, self.id.encode())
        self.logger.debug(f"DEALER[{self.id}] initialized with identity: {self.id}")

    async def request(self, message: Message, timeout: float = 300.0) -> Message:
        """Send a message to a dealer and await response.

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

        try:
            # Store original timeout to restore later
            original_timeout = self.socket.getsockopt(zmq.RCVTIMEO)
            self.logger.debug(
                f"DEALER[{self.id}] Original socket timeout: {original_timeout}ms"
            )

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

            # Set timeout for this request
            timeout_ms = int(timeout * 1000)
            self.socket.setsockopt(zmq.RCVTIMEO, timeout_ms)
            self.logger.debug(
                f"DEALER[{self.id}] WAITING FOR RESPONSE - ID: {message.request_id}, Timeout: {timeout}s ({timeout_ms}ms)"
            )

            # Wait for response
            try:
                recv_start = time.time()
                self.logger.info(
                    f"DEALER[{self.id}] BLOCKING ON RECV - ID: {message.request_id}, Timeout: {timeout}s"
                )
                self.logger.debug(
                    f"DEALER[{self.id}] Socket state before recv - Connected: {not self.socket.closed}, Events: {self.socket.poll(0)}"
                )

                # Use a shorter timeout with polling to provide periodic status updates
                original_recv_timeout = self.socket.getsockopt(zmq.RCVTIMEO)
                poll_interval = min(
                    5000, timeout_ms // 10
                )  # Poll every 5 seconds or 10% of timeout
                self.socket.setsockopt(zmq.RCVTIMEO, poll_interval)

                response_json = None
                elapsed_time = 0

                while response_json is None and elapsed_time < timeout:
                    try:
                        response_frames = await self.socket.recv_multipart()
                        # Extract the actual response content from the frames
                        # DEALER sockets receive responses as multipart: could be [response] or [identity, response]
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
                        else:
                            self.logger.warning(
                                f"DEALER[{self.id}] EMPTY RESPONSE FRAMES - ID: {message.request_id}"
                            )
                            continue
                        break
                    except zmq.Again:
                        elapsed_time = time.time() - recv_start
                        remaining_time = timeout - elapsed_time
                        self.logger.info(
                            f"DEALER[{self.id}] STILL WAITING - ID: {message.request_id}, Elapsed: {elapsed_time:.1f}s, Remaining: {remaining_time:.1f}s"
                        )

                        # Check socket state periodically
                        events = self.socket.poll(0)
                        self.logger.debug(
                            f"DEALER[{self.id}] Socket poll events: {events}, Connected: {not self.socket.closed}"
                        )

                        if remaining_time <= 0:
                            break

                # Restore original timeout
                self.socket.setsockopt(zmq.RCVTIMEO, original_recv_timeout)

                if response_json is None:
                    # Final timeout
                    timeout_duration = time.time() - recv_start
                    self.logger.error(
                        f"DEALER[{self.id}] REQUEST TIMEOUT - ID: {message.request_id}, Duration: {timeout_duration:.3f}s, Expected: {timeout}s"
                    )
                    self.logger.error(
                        f"DEALER[{self.id}] Socket state on timeout - Connected: {not self.socket.closed}, Events: {self.socket.poll(0)}"
                    )
                    raise CommunicationError(
                        f"Request timed out after {timeout} seconds"
                    )

                recv_duration = time.time() - recv_start
                response_size = len(response_json.encode("utf-8"))

                self.logger.info(
                    f"DEALER[{self.id}] RESPONSE RECEIVED - ID: {message.request_id}, Size: {response_size} bytes, Duration: {recv_duration:.3f}s"
                )
                self.logger.debug(
                    f"DEALER[{self.id}] RESPONSE DATA - {response_json[:500]}{'...' if len(response_json) > 500 else ''}"
                )

                # Parse the response
                try:
                    parse_start = time.time()
                    response_message = MessageTypeAdapter.validate_json(response_json)
                    parse_duration = time.time() - parse_start

                    total_duration = time.time() - request_start_time
                    self.logger.info(
                        f"DEALER[{self.id}] REQUEST COMPLETE - ID: {message.request_id}, Response Type: {response_message.message_type}, Total Duration: {total_duration:.3f}s, Parse Duration: {parse_duration:.3f}s"
                    )
                    self.logger.debug(
                        f"DEALER[{self.id}] PARSED RESPONSE - {response_message}"
                    )

                    return response_message
                except Exception as parse_error:
                    self.logger.error(
                        f"DEALER[{self.id}] PARSE ERROR - ID: {message.request_id}, Error: {parse_error}"
                    )
                    self.logger.error(
                        f"DEALER[{self.id}] RAW RESPONSE - {response_json}"
                    )
                    raise CommunicationError(
                        f"Invalid response format: {parse_error}"
                    ) from parse_error

            except zmq.Again as e:
                # This shouldn't happen with our polling approach, but keep for safety
                timeout_duration = time.time() - request_start_time
                self.logger.error(
                    f"DEALER[{self.id}] UNEXPECTED TIMEOUT - ID: {message.request_id}, Duration: {timeout_duration:.3f}s"
                )
                raise CommunicationError(
                    f"Request timed out after {timeout} seconds"
                ) from e
            except Exception as recv_error:
                recv_duration = time.time() - recv_start
                self.logger.error(
                    f"DEALER[{self.id}] RECV ERROR - ID: {message.request_id}, Duration: {recv_duration:.3f}s, Error: {recv_error}"
                )
                self.logger.error(
                    f"DEALER[{self.id}] Socket state on error - Connected: {not self.socket.closed}"
                )
                raise CommunicationError(
                    f"Failed to receive response: {recv_error}"
                ) from recv_error

            finally:
                # Restore original timeout
                self.socket.setsockopt(zmq.RCVTIMEO, original_timeout)
                self.logger.debug(
                    f"DEALER[{self.id}] Restored original socket timeout: {original_timeout}ms"
                )

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
