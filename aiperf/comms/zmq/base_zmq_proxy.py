# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
from abc import ABC, abstractmethod
from contextlib import suppress

import zmq
import zmq.asyncio
from zmq import SocketType

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.config.zmq_config import BaseZMQProxyConfig
from aiperf.common.constants import TASK_CANCEL_TIMEOUT_SHORT
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
            "Proxy Initializing - Frontend: %s, Backend: %s",
            zmq_proxy_config.frontend_address,
            zmq_proxy_config.backend_address,
        )
        self.frontend_address = zmq_proxy_config.frontend_address
        self.backend_address = zmq_proxy_config.backend_address
        self.control_address = zmq_proxy_config.control_address
        self.capture_address = zmq_proxy_config.capture_address
        self.socket_ops = socket_ops
        self.monitor_task: asyncio.Task | None = None

        self.backend_socket = backend_socket_class(
            context=self.context,
            address=self.backend_address,
            bind=True,
            socket_ops=self.socket_ops,
        )  # type: ignore - child classes provide the socket_type
        self.frontend_socket = frontend_socket_class(
            context=self.context,
            address=self.frontend_address,
            bind=True,
            socket_ops=self.socket_ops,
        )  # type: ignore - child classes provide the socket_type

        self.control_client = None
        if self.control_address:
            self.logger.debug("Proxy Control - Address: %s", self.control_address)
            self.control_client = BaseZMQClient(
                context=self.context,
                socket_type=SocketType.REP,
                address=self.control_address,
                bind=True,
                socket_ops=self.socket_ops,
            )

        self.capture_client = None
        if self.capture_address:
            self.logger.debug("Proxy Capture - Address: %s", self.capture_address)
            self.capture_client = BaseZMQClient(
                context=self.context,
                socket_type=SocketType.PUB,
                address=self.capture_address,
                bind=True,
                socket_ops=self.socket_ops,
            )

        self.proxy: zmq.asyncio.Socket | None = None

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
        self.logger.debug("Proxy Initializing Sockets...")
        self.logger.debug(
            "Frontend %s socket binding to: %s (for %s clients)",
            self.frontend_socket.socket_type.name,
            self.frontend_address,
            self.backend_socket.socket_type.name,
        )
        self.logger.debug(
            "Backend %s socket binding to: %s (for %s services)",
            self.backend_socket.socket_type.name,
            self.backend_address,
            self.frontend_socket.socket_type.name,
        )
        if hasattr(self.backend_socket, "proxy_id"):
            self.logger.debug(
                "Backend socket identity: %s",
                self.backend_socket.proxy_id,
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

            self.logger.debug("Proxy Sockets Initialized Successfully")

            if self.control_client:
                self.logger.debug("Control socket bound to: %s", self.control_address)
            if self.capture_client:
                self.logger.debug("Capture socket bound to: %s", self.capture_address)

        except Exception as e:
            self.logger.error(f"Proxy Socket Initialization Failed {e}")
            raise

    async def stop(self) -> None:
        """Shutdown the BaseZMQProxy."""
        self.logger.debug("Proxy Stopping...")

        try:
            if self.monitor_task and not self.monitor_task.done():
                self.monitor_task.cancel()
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(
                        self.monitor_task, timeout=TASK_CANCEL_TIMEOUT_SHORT
                    )

            await asyncio.wait_for(
                asyncio.gather(
                    self.backend_socket.shutdown(),
                    self.frontend_socket.shutdown(),
                    *[
                        client.shutdown()
                        for client in [self.control_client, self.capture_client]
                        if client
                    ],
                ),
                timeout=TASK_CANCEL_TIMEOUT_SHORT,
            )

        except Exception as e:
            self.logger.error(f"Proxy Stop Error {e}")

    async def run(self) -> None:
        """Start the Base ZMQ Proxy.

        This method starts the proxy and waits for it to complete asynchronously.
        The proxy forwards messages between the frontend and backend sockets.

        Raises:
            CommunicationError: If the proxy produces an error.
        """
        try:
            await self._initialize()

            self.logger.debug("Proxy Starting...")

            if self.capture_client:
                self.monitor_task = asyncio.create_task(self._monitor_messages())
                self.logger.debug("Proxy Message Monitoring Started")

            await asyncio.to_thread(
                zmq.proxy_steerable,
                self.frontend_socket.socket,
                self.backend_socket.socket,
                capture=self.capture_client.socket if self.capture_client else None,
                control=self.control_client.socket if self.control_client else None,
            )

        except zmq.ContextTerminated:
            self.logger.debug("Proxy Terminated by Context")
            raise

        except Exception as e:
            self.logger.error(f"Proxy Error: {e}")
            raise CommunicationError(
                CommunicationErrorReason.PROXY_ERROR,
                f"Proxy failed: {e}",
            ) from e

    async def _monitor_messages(self) -> None:
        """Monitor messages flowing through the proxy via the capture socket."""
        if not self.capture_client or not self.capture_address:
            raise CommunicationError(
                CommunicationErrorReason.PROXY_ERROR,
                "Proxy Monitor Not Enabled",
            )

        self.logger.debug(
            "Proxy Monitor Starting - Capture Address: %s",
            self.capture_address,
        )

        capture_socket = self.context.socket(SocketType.SUB)
        capture_socket.connect(self.capture_address)
        capture_socket.setsockopt(zmq.SUBSCRIBE, b"")  # Subscribe to all messages

        try:
            while True:
                message = capture_socket.recv()
                self.logger.debug("Proxy Monitor Received Message: %s", message)
        except Exception as e:
            self.logger.error("Proxy Monitor Error - %s", e)
            raise
        finally:
            capture_socket.close()
