# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import contextlib
import logging
import time
from abc import ABC, abstractmethod

import zmq
import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.config.zmq_config import BaseZMQProxyConfig
from aiperf.common.exceptions import CommunicationError, CommunicationErrorReason


class BaseZMQProxy(ABC):
    """
    A Base ZMQ Proxy class.

    This class is responsible for creating the ZMQ proxy that forwards messages
    between clients and services.

    **Connection Architecture:**
    - Clients connect to frontend_address (proxy's frontend socket)
    - Services connect to backend_address (proxy's backend socket)
    - The proxy forwards messages bidirectionally between the two sockets

    **Message Flow:**
    Client -> frontend_address -> frontend_socket -> proxy -> backend_socket -> backend_address -> Service
    Service -> backend_address -> backend_socket -> proxy -> frontend_socket -> frontend_address -> Client

    The proxy is started in a separate thread using asyncio.to_thread.
    This is because the proxy is a blocking operation and we want to avoid blocking the main thread.
    """

    def __init__(
        self,
        frontend_socket_class: type[BaseZMQClient],
        backend_socket_class: type[BaseZMQClient],
        context: zmq.asyncio.Context,
        zmq_proxy_config: BaseZMQProxyConfig,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the Base ZMQ Proxy class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            zmq_proxy_config (BaseZMQProxyConfig): The ZMQ proxy configuration.
            socket_ops (dict, optional): Additional socket options to set.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.context = context
        self.logger.debug(
            f"PROXY INIT - Frontend: {zmq_proxy_config.frontend_address} (ROUTER for DEALER clients), Backend: {zmq_proxy_config.backend_address} (DEALER for ROUTER services)"
        )
        self.frontend_address = zmq_proxy_config.frontend_address
        self.backend_address = zmq_proxy_config.backend_address
        self.control_address = zmq_proxy_config.control_address
        self.capture_address = zmq_proxy_config.capture_address
        self.socket_ops = socket_ops
        self.monitor_task: asyncio.Task | None = None

        # Proxy sockets with clear frontend/backend naming
        self.backend_socket = backend_socket_class(
            context=self.context,
            address=self.backend_address,
            bind=True,
            socket_ops=self.socket_ops,
        )  # type: ignore - child classes porovide the socket_type
        self.frontend_socket = frontend_socket_class(
            context=self.context,
            address=self.frontend_address,
            bind=True,
            socket_ops=self.socket_ops,
        )  # type: ignore - child classes porovide the socket_type

        self.control_client = None
        if self.control_address:
            self.logger.debug(f"PROXY CONTROL - Address: {self.control_address}")
            self.control_client = BaseZMQClient(
                context=self.context,
                socket_type=SocketType.REP,
                address=self.control_address,
                bind=True,
                socket_ops=self.socket_ops,
            )

        self.capture_client = None
        if self.capture_address:
            self.logger.debug(f"PROXY CAPTURE - Address: {self.capture_address}")
            self.capture_client = BaseZMQClient(
                context=self.context,
                socket_type=SocketType.PUB,
                address=self.capture_address,
                bind=True,
                socket_ops=self.socket_ops,
            )

        self.proxy: zmq.asyncio.Socket | None = None
        self._proxy_start_time: float | None = None

    @classmethod
    @abstractmethod
    def from_config(
        cls,
        config: BaseZMQProxyConfig | None,
        socket_ops: dict | None = None,
    ) -> "BaseZMQProxy | None":
        """Create a BaseZMQProxy from a BaseZMQProxyConfig, or None if not provided."""
        ...

    async def _initialize(self) -> None:
        """Initialize and start the BaseZMQProxy."""
        init_start = time.time()
        self.logger.debug("PROXY INITIALIZING SOCKETS...")
        self.logger.debug(
            f"  Frontend ROUTER socket binding to: {self.frontend_address} (for DEALER clients)"
        )
        self.logger.debug(
            f"  Backend socket binding to: {self.backend_address} (for ROUTER services)"
        )
        if hasattr(self.backend_socket, "proxy_id"):
            self.logger.debug(
                f"  Backend socket identity: {self.backend_socket.proxy_id}"
            )

        try:
            await asyncio.gather(
                self.backend_socket.initialize(),
                self.frontend_socket.initialize(),
                *[
                    client.initialize()
                    for client in [self.control_client, self.capture_client]
                    if client
                ],
            )

            init_duration = time.time() - init_start
            self.logger.debug(
                f"PROXY SOCKETS INITIALIZED SUCCESSFULLY - Duration: {init_duration:.3f}s"
            )
            self.logger.debug(
                f"  Frontend ROUTER socket bound to: {self.frontend_address}"
            )
            self.logger.debug(
                f"  Backend DEALER socket bound to: {self.backend_address}"
            )
            if hasattr(self.backend_socket, "proxy_id"):
                self.logger.debug(
                    f"  Backend DEALER socket identity confirmed: {self.backend_socket.proxy_id}"
                )

            if self.control_client:
                self.logger.debug(f"  Control socket bound to: {self.control_address}")
            if self.capture_client:
                self.logger.debug(f"  Capture socket bound to: {self.capture_address}")

        except Exception as e:
            self.logger.error(f"PROXY SOCKET INITIALIZATION FAILED - Error: {e}")
            raise

    async def stop(self) -> None:
        """Shutdown the BaseZMQProxy."""
        stop_start = time.time()
        self.logger.debug("PROXY STOPPING...")

        try:
            if self.monitor_task and not self.monitor_task.done():
                self.monitor_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self.monitor_task

            await asyncio.gather(
                self.backend_socket.shutdown(),
                self.frontend_socket.shutdown(),
                *[
                    client.shutdown()
                    for client in [self.control_client, self.capture_client]
                    if client
                ],
            )

            stop_duration = time.time() - stop_start
            total_uptime = (
                time.time() - self._proxy_start_time if self._proxy_start_time else 0
            )
            self.logger.debug(
                f"PROXY STOPPED - Stop Duration: {stop_duration:.3f}s, Total Uptime: {total_uptime:.3f}s"
            )

        except Exception as e:
            self.logger.error(f"PROXY STOP ERROR - {e}")

    async def run(self) -> None:
        """Start the Base ZMQ Proxy.

        This method starts the proxy and waits for it to complete asynchronously.
        The proxy forwards messages between the frontend and backend sockets.

        Raises:
            CommunicationError: If the proxy produces an error.
        """
        try:
            await self._initialize()

            # Proxy configuration: frontend=ROUTER (for DEALER clients), backend=DEALER (for ROUTER services)
            self.logger.debug("PROXY STARTING...")
            self.logger.debug(
                f"  Frontend: ROUTER@{self.frontend_address} (receives from DEALER clients)"
            )
            self.logger.debug(
                f"  Backend: DEALER@{self.backend_address} (sends to ROUTER services)"
            )
            if self.capture_client:
                self.logger.debug(
                    f"  Capture: PUB@{self.capture_address} (message monitoring)"
                )
            if self.control_client:
                self.logger.debug(
                    f"  Control: REP@{self.control_address} (proxy control)"
                )

            self._proxy_start_time = time.time()

            # Start message monitoring task if capture is enabled (optional)
            self.monitor_task = None
            if self.capture_client:
                self.monitor_task = asyncio.create_task(self._monitor_messages())
                self.logger.debug("PROXY MESSAGE MONITORING STARTED")

            # Start the proxy in a separate thread (blocking operation)
            await asyncio.to_thread(
                zmq.proxy_steerable,
                self.frontend_socket.socket,  # Frontend: ROUTER socket (DEALER clients connect here)
                self.backend_socket.socket,  # Backend: DEALER socket (ROUTER services connect here)
                capture=self.capture_client.socket if self.capture_client else None,
                control=self.control_client.socket if self.control_client else None,
            )

            # This should not be reached unless proxy is terminated
            self.logger.warning("PROXY TERMINATED UNEXPECTEDLY")
        except zmq.ContextTerminated:
            self.logger.debug("PROXY TERMINATED BY CONTEXT")
            return

        except Exception as e:
            proxy_duration = (
                time.time() - self._proxy_start_time if self._proxy_start_time else 0
            )
            self.logger.error(
                f"PROXY ERROR - Duration: {proxy_duration:.3f}s, Error: {e}"
            )
            raise CommunicationError(
                CommunicationErrorReason.PROXY_ERROR,
                f"Proxy failed: {e}",
            ) from e

    async def _monitor_messages(self) -> None:
        """Monitor messages flowing through the proxy via the capture socket."""
        if not self.capture_client or not self.capture_address:
            return

        self.logger.debug(
            f"PROXY MONITOR STARTING - Capture Address: {self.capture_address}"
        )

        # Create a subscriber to monitor captured messages
        monitor_socket = self.context.socket(SocketType.SUB)
        monitor_socket.connect(self.capture_address)
        monitor_socket.setsockopt(zmq.SUBSCRIBE, b"")  # Subscribe to all messages

        message_count = 0

        try:
            while True:
                try:
                    # Receive captured message (this will be multipart)
                    frames = await monitor_socket.recv_multipart(zmq.NOBLOCK)
                    message_count += 1

                    frame_info = []
                    total_size = 0

                    # Enhanced frame analysis
                    for i, frame in enumerate(frames):
                        frame_size = len(frame)
                        total_size += frame_size
                        # Try to decode as string for logging (first 100 chars)
                        try:
                            frame_preview = frame.decode("utf-8")[:100]
                            if len(frame_preview) < len(frame.decode("utf-8")):
                                frame_preview += "..."
                        except UnicodeDecodeError:
                            # Show hex representation for binary frames
                            frame_preview = f"<binary:{frame_size}bytes:0x{frame[:20].hex()}{'...' if frame_size > 20 else ''}>"

                        frame_info.append(
                            f"Frame[{i}]: {frame_size}b - {frame_preview!r}"
                        )

                    self.logger.debug(
                        f"PROXY CAPTURED MESSAGE #{message_count} - Total Size: {total_size}b, Frames: {len(frames)}"
                    )

                    # Determine message direction and content
                    direction = "UNKNOWN"
                    message_content = None
                    sender_info = "unknown"

                    if len(frames) >= 1:
                        # First frame should be sender/destination identity
                        identity_frame = frames[0] if frames else b""
                        sender_info = (
                            f"0x{identity_frame.hex()}" if identity_frame else "empty"
                        )

                        # Try to find the JSON message content
                        for i in range(len(frames)):
                            try:
                                if frames[i].startswith(b"{"):
                                    message_content = frames[i].decode("utf-8")
                                    self.logger.debug(
                                        f"PROXY CAPTURE - Found JSON in frame {i}"
                                    )
                                    break
                            except UnicodeDecodeError:
                                continue

                        # Determine direction based on frame structure and content
                        if len(frames) == 1:
                            # Single frame - this is unusual, might be a response not properly routed
                            if message_content:
                                direction = (
                                    "SINGLE FRAME (possibly broken response routing)"
                                )
                            else:
                                direction = "SINGLE FRAME (non-JSON)"
                        elif len(frames) == 2:
                            # Simple case: [identity, message] - likely frontend->backend (DEALER->ROUTER)
                            direction = "FRONTEND->BACKEND (DEALER to ROUTER)"
                        elif len(frames) == 3:
                            # Three frames: complex routing scenario
                            direction = f"MULTI-HOP (3 frames) - Frame0: 0x{frames[0].hex()[:10]}..., Frame1: 0x{frames[1].hex()[:10]}..."
                        else:
                            direction = f"COMPLEX ({len(frames)} frames)"

                    self.logger.debug(
                        f"PROXY CAPTURE ANALYSIS - Direction: {direction}, Sender: {sender_info}"
                    )

                    # Log detailed frame info at debug level with enhanced analysis
                    for _, info in enumerate(frame_info):
                        self.logger.debug(f"PROXY CAPTURE - {info}")

                    # Additional analysis for single frame messages (potential routing issues)
                    if len(frames) == 1:
                        self.logger.warning(
                            "PROXY SINGLE FRAME DETECTED - This may indicate a routing problem"
                        )
                        self.logger.warning(
                            f"PROXY SINGLE FRAME CONTENT - {frames[0][:100]}..."
                        )

                        # Check if this looks like a response that lost its routing envelope
                        if message_content and "response" in message_content:
                            self.logger.error(
                                "PROXY RESPONSE ROUTING FAILURE - Response message has no routing envelope"
                            )

                    # Try to extract and parse the actual message content
                    if message_content:
                        try:
                            import json

                            message_data = json.loads(message_content)
                            msg_type = message_data.get("message_type", "unknown")
                            msg_id = message_data.get("request_id", "unknown")
                            service_id = message_data.get("service_id", "unknown")

                            self.logger.debug(
                                f"PROXY CAPTURED PARSED - ID: {msg_id}, Type: {msg_type}, Service: {service_id}, Direction: {direction}"
                            )

                            # Special attention to conversation_response messages
                            if msg_type == "conversation_response":
                                self.logger.warning(
                                    f"PROXY CONVERSATION_RESPONSE DETECTED - ID: {msg_id}, Direction: {direction}, Service: {service_id}"
                                )
                                self.logger.warning(
                                    f"PROXY RESPONSE FRAMES - Count: {len(frames)}, Sizes: {[len(f) for f in frames]}"
                                )

                                # If this is a single frame response, it means routing is broken
                                if len(frames) == 1:
                                    self.logger.error(
                                        "PROXY RESPONSE ROUTING BROKEN - Response should have routing envelope but only has 1 frame"
                                    )
                                    self.logger.error(
                                        "PROXY EXPECTED STRUCTURE - Should be [sender_id, response_json] but got single frame"
                                    )

                        except Exception as parse_error:
                            self.logger.debug(
                                f"PROXY CAPTURE PARSE ERROR - {parse_error}"
                            )
                            if message_content:
                                self.logger.debug(
                                    f"PROXY UNPARSABLE CONTENT - {message_content[:200]}..."
                                )

                except zmq.Again:
                    # No message available, short sleep and continue
                    await asyncio.sleep(0.001)
                    continue

        except asyncio.CancelledError:
            self.logger.debug(
                f"PROXY MONITOR CANCELLED - Messages Captured: {message_count}"
            )
            raise
        except Exception as e:
            self.logger.error(f"PROXY MONITOR ERROR - {e}")
        finally:
            monitor_socket.close()
