#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import asyncio
import contextlib
import logging
import time

import zmq
import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.exceptions import CommunicationError
from aiperf.common.models import BaseZMQDealerRouterBrokerConfig


class ZMQDealerRouterBroker:
    """
    A ZMQ Dealer Router Broker class.

    This class is responsible for creating the ZMQ proxy that forwards messages
    between DEALER clients and ROUTER services.

    **Connection Architecture:**
    - DEALER clients connect to frontend_address (broker's ROUTER socket)
    - ROUTER services connect to backend_address (broker's DEALER socket)
    - The proxy forwards messages bidirectionally between the two sockets

    **Message Flow:**
    DEALER Client -> frontend_address -> ROUTER Socket (Frontend) -> Proxy -> DEALER Socket (Backend) -> backend_address -> ROUTER Service
    ROUTER Service -> backend_address -> DEALER Socket (Backend) -> Proxy -> ROUTER Socket (Frontend) -> frontend_address -> DEALER Client

    The proxy is started in a separate thread using asyncio.to_thread.
    This is because the proxy is a blocking operation and we want to avoid blocking the main thread.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        frontend_address: str,
        backend_address: str,
        control_address: str | None = None,
        capture_address: str | None = None,
        socket_ops: dict | None = None,
    ) -> None:
        """
        Initialize the ZMQ Dealer Router Broker class.

        Args:
            context (zmq.asyncio.Context): The ZMQ context.
            frontend_address (str): The frontend address to bind to (ROUTER socket - for DEALER clients).
            backend_address (str): The backend address to bind to (DEALER socket - for ROUTER services).
            control_address (str, optional): The control address to bind to.
            capture_address (str, optional): The capture address to bind to.
            socket_ops (dict, optional): Additional socket options to set.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.context = context
        self.logger.info(
            f"BROKER INIT - Frontend: {frontend_address} (ROUTER for DEALER clients), Backend: {backend_address} (DEALER for ROUTER services)"
        )
        self.frontend_address = frontend_address
        self.backend_address = backend_address
        self.control_address = control_address
        self.capture_address = capture_address
        self.socket_ops = socket_ops

        # Broker sockets with clear frontend/backend naming
        self.backend_socket = _BrokerBackendDealerClient(
            self.context,
            self.backend_address,
            bind=True,
            socket_ops=self.socket_ops,
        )
        self.frontend_socket = _BrokerFrontendRouterClient(
            self.context,
            self.frontend_address,
            bind=True,
            socket_ops=self.socket_ops,
        )

        self.control_client = None
        if self.control_address:
            self.logger.info(f"BROKER CONTROL - Address: {self.control_address}")
            self.control_client = BaseZMQClient(
                self.context,
                SocketType.REP,
                self.control_address,
                bind=True,
                socket_ops=self.socket_ops,
            )

        self.capture_client = None
        if self.capture_address:
            self.logger.info(f"BROKER CAPTURE - Address: {self.capture_address}")
            self.capture_client = BaseZMQClient(
                self.context,
                SocketType.PUB,
                self.capture_address,
                bind=True,
                socket_ops=self.socket_ops,
            )

        self.proxy: zmq.asyncio.Socket | None = None
        self._proxy_start_time: float | None = None

    @classmethod
    def from_config(
        cls,
        config: BaseZMQDealerRouterBrokerConfig | None,
        socket_ops: dict | None = None,
    ) -> "ZMQDealerRouterBroker | None":
        """Create a DealerRouterBroker from a BaseZMQDealerRouterBrokerConfig, or None if not provided."""
        if config is None:
            return None
        return cls(
            context=zmq.asyncio.Context.instance(),
            frontend_address=config.frontend_address,  # DEALER clients connect here
            backend_address=config.backend_address,  # ROUTER services connect here
            control_address=config.control_address,
            capture_address=config.capture_address,
            socket_ops=socket_ops,
        )

    async def _initialize(self) -> None:
        """Initialize and start the DealerRouterBroker."""
        init_start = time.time()
        self.logger.info("BROKER INITIALIZING SOCKETS...")
        self.logger.info(
            f"  Frontend ROUTER socket binding to: {self.frontend_address} (for DEALER clients)"
        )
        self.logger.info(
            f"  Backend DEALER socket binding to: {self.backend_address} (for ROUTER services)"
        )
        if hasattr(self.backend_socket, "broker_id"):
            self.logger.info(
                f"  Backend DEALER socket identity: {self.backend_socket.broker_id}"
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
            self.logger.info(
                f"BROKER SOCKETS INITIALIZED SUCCESSFULLY - Duration: {init_duration:.3f}s"
            )
            self.logger.info(
                f"  Frontend ROUTER socket bound to: {self.frontend_address}"
            )
            self.logger.info(
                f"  Backend DEALER socket bound to: {self.backend_address}"
            )
            if hasattr(self.backend_socket, "broker_id"):
                self.logger.info(
                    f"  Backend DEALER socket identity confirmed: {self.backend_socket.broker_id}"
                )

            if self.control_client:
                self.logger.info(f"  Control socket bound to: {self.control_address}")
            if self.capture_client:
                self.logger.info(f"  Capture socket bound to: {self.capture_address}")

        except Exception as e:
            self.logger.error(f"BROKER SOCKET INITIALIZATION FAILED - Error: {e}")
            raise

    async def stop(self) -> None:
        """Shutdown the DealerRouterBroker."""
        stop_start = time.time()
        self.logger.info("BROKER STOPPING...")

        try:
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
            self.logger.info(
                f"BROKER STOPPED - Stop Duration: {stop_duration:.3f}s, Total Uptime: {total_uptime:.3f}s"
            )

        except Exception as e:
            self.logger.error(f"BROKER STOP ERROR - {e}")

    async def run(self) -> None:
        """Start the ZMQ Dealer Router Proxy.

        This method starts the proxy and waits for it to complete asynchronously.
        The proxy forwards messages between the DEALER and ROUTER sockets.

        Raises:
            CommunicationError: If the proxy produces an error.
        """
        try:
            await self._initialize()

            # Proxy configuration: frontend=ROUTER (for DEALER clients), backend=DEALER (for ROUTER services)
            self.logger.info("BROKER STARTING PROXY...")
            self.logger.info(
                f"  Frontend: ROUTER@{self.frontend_address} (receives from DEALER clients)"
            )
            self.logger.info(
                f"  Backend: DEALER@{self.backend_address} (sends to ROUTER services)"
            )
            if self.capture_client:
                self.logger.info(
                    f"  Capture: PUB@{self.capture_address} (message monitoring)"
                )
            if self.control_client:
                self.logger.info(
                    f"  Control: REP@{self.control_address} (proxy control)"
                )

            self._proxy_start_time = time.time()

            # Start message monitoring task if capture is enabled
            monitor_task = None
            if self.capture_client:
                monitor_task = asyncio.create_task(self._monitor_messages())
                self.logger.info("BROKER MESSAGE MONITORING STARTED")

            # Start the proxy in a separate thread (blocking operation)
            await asyncio.to_thread(
                zmq.proxy_steerable,
                self.frontend_socket.socket,  # Frontend: ROUTER socket (DEALER clients connect here)
                self.backend_socket.socket,  # Backend: DEALER socket (ROUTER services connect here)
                capture=self.capture_client.socket if self.capture_client else None,
                control=self.control_client.socket if self.control_client else None,
            )

            # This should not be reached unless proxy is terminated
            self.logger.warning("BROKER PROXY TERMINATED UNEXPECTEDLY")

        except Exception as e:
            proxy_duration = (
                time.time() - self._proxy_start_time if self._proxy_start_time else 0
            )
            self.logger.error(
                f"BROKER PROXY ERROR - Duration: {proxy_duration:.3f}s, Error: {e}"
            )
            raise CommunicationError(f"Broker proxy failed: {e}") from e
        finally:
            if monitor_task and not monitor_task.done():
                monitor_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await monitor_task
            await self.stop()

    async def _monitor_messages(self) -> None:
        """Monitor messages flowing through the proxy via the capture socket."""
        if not self.capture_client or not self.capture_address:
            return

        self.logger.info(
            f"BROKER MONITOR STARTING - Capture Address: {self.capture_address}"
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

                    self.logger.info(
                        f"BROKER CAPTURED MESSAGE #{message_count} - Total Size: {total_size}b, Frames: {len(frames)}"
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
                                        f"BROKER CAPTURE - Found JSON in frame {i}"
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

                    self.logger.info(
                        f"BROKER CAPTURE ANALYSIS - Direction: {direction}, Sender: {sender_info}"
                    )

                    # Log detailed frame info at debug level with enhanced analysis
                    for _, info in enumerate(frame_info):
                        self.logger.debug(f"BROKER CAPTURE - {info}")

                    # Additional analysis for single frame messages (potential routing issues)
                    if len(frames) == 1:
                        self.logger.warning(
                            "BROKER SINGLE FRAME DETECTED - This may indicate a routing problem"
                        )
                        self.logger.warning(
                            f"BROKER SINGLE FRAME CONTENT - {frames[0][:100]}..."
                        )

                        # Check if this looks like a response that lost its routing envelope
                        if message_content and "response" in message_content:
                            self.logger.error(
                                "BROKER RESPONSE ROUTING FAILURE - Response message has no routing envelope"
                            )

                    # Try to extract and parse the actual message content
                    if message_content:
                        try:
                            import json

                            message_data = json.loads(message_content)
                            msg_type = message_data.get("message_type", "unknown")
                            msg_id = message_data.get("request_id", "unknown")
                            service_id = message_data.get("service_id", "unknown")

                            self.logger.info(
                                f"BROKER CAPTURED PARSED - ID: {msg_id}, Type: {msg_type}, Service: {service_id}, Direction: {direction}"
                            )

                            # Special attention to conversation_response messages
                            if msg_type == "conversation_response":
                                self.logger.warning(
                                    f"BROKER CONVERSATION_RESPONSE DETECTED - ID: {msg_id}, Direction: {direction}, Service: {service_id}"
                                )
                                self.logger.warning(
                                    f"BROKER RESPONSE FRAMES - Count: {len(frames)}, Sizes: {[len(f) for f in frames]}"
                                )

                                # If this is a single frame response, it means routing is broken
                                if len(frames) == 1:
                                    self.logger.error(
                                        "BROKER RESPONSE ROUTING BROKEN - Response should have routing envelope but only has 1 frame"
                                    )
                                    self.logger.error(
                                        "BROKER EXPECTED STRUCTURE - Should be [sender_id, response_json] but got single frame"
                                    )

                        except Exception as parse_error:
                            self.logger.debug(
                                f"BROKER CAPTURE PARSE ERROR - {parse_error}"
                            )
                            if message_content:
                                self.logger.debug(
                                    f"BROKER UNPARSABLE CONTENT - {message_content[:200]}..."
                                )

                except zmq.Again:
                    # No message available, short sleep and continue
                    await asyncio.sleep(0.001)
                    continue

        except asyncio.CancelledError:
            self.logger.info(
                f"BROKER MONITOR CANCELLED - Messages Captured: {message_count}"
            )
            raise
        except Exception as e:
            self.logger.error(f"BROKER MONITOR ERROR - {e}")
        finally:
            monitor_socket.close()


class _BrokerFrontendRouterClient(BaseZMQClient):
    """
    A ROUTER socket for the broker's frontend.

    This ROUTER socket receives messages from DEALER clients and forwards them
    through the proxy to ROUTER services. The ZMQ proxy handles the message
    routing automatically.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        super().__init__(context, SocketType.ROUTER, address, bind, socket_ops)
        self.logger.debug(f"BROKER FRONTEND ROUTER - Address: {address}, Bind: {bind}")

    def send_message(self, message: str) -> None:
        self.socket.send_multipart([b"", message.encode()])


class _BrokerBackendDealerClient(BaseZMQClient):
    """
    A DEALER socket for the broker's backend.

    This DEALER socket forwards messages from the proxy to ROUTER services.
    The ZMQ proxy handles the message routing automatically.

    CRITICAL: This socket must NOT have an identity when used in a proxy
    configuration, as it needs to be transparent to preserve routing envelopes
    for proper response forwarding back to original DEALER clients.
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        address: str,
        bind: bool,
        socket_ops: dict | None = None,
    ) -> None:
        # DO NOT set identity for backend DEALER in proxy configuration
        # The proxy needs this socket to be transparent for proper routing envelope forwarding

        super().__init__(context, SocketType.DEALER, address, bind, socket_ops)
        self.logger.debug(
            f"BROKER BACKEND DEALER - Address: {address}, Bind: {bind}, Identity: None (transparent for proxy)"
        )
