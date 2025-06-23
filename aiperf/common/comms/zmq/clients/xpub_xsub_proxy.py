# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging

import zmq.asyncio

from aiperf.common.comms.zmq.clients.base import BaseZMQClient
from aiperf.common.exceptions import CommunicationError, CommunicationErrorReason
from aiperf.common.hooks import AIPerfHook

logger = logging.getLogger(__name__)


class ZMQXPubXSubProxyClient(BaseZMQClient):
    """ZMQ XPUB/XSUB Proxy client for many-to-many pub/sub communications.

    This proxy sits between publishers and subscribers using ZMQ's built-in
    proxy functionality for optimal performance. Features:
    - Multiple publishers to multiple subscribers communication
    - Dynamic subscription management with automatic forwarding
    - Efficient message routing using zmq.proxy()
    - High-performance C implementation under the hood
    - Scalable pub/sub architecture
    """

    def __init__(
        self,
        context: zmq.asyncio.Context,
        frontend_address: str,
        backend_address: str,
        frontend_bind: bool = True,
        backend_bind: bool = True,
        socket_ops: dict | None = None,
    ) -> None:
        """Initialize the XPUB/XSUB proxy.

        Args:
            context: ZMQ context
            frontend_address: Address for XSUB socket (connects to publishers)
            backend_address: Address for XPUB socket (binds for subscribers)
            frontend_bind: Whether to bind the frontend socket (default: True)
            backend_bind: Whether to bind the backend socket (default: True)
            socket_ops: Additional socket options
        """
        # Initialize base with XSUB socket type (we'll create XPUB separately)
        super().__init__(
            context=context,
            socket_type=zmq.SocketType.XSUB,
            address=frontend_address,
            bind=frontend_bind,
            socket_ops=socket_ops,
        )

        self.frontend_address = frontend_address
        self.backend_address = backend_address
        self.frontend_bind = frontend_bind
        self.backend_bind = backend_bind

        self._backend_socket: zmq.asyncio.Socket | None = None
        self._proxy_task: asyncio.Task | None = None

    @property
    def backend_socket(self) -> zmq.asyncio.Socket:
        """Get the backend XPUB socket.

        Raises:
            CommunicationError: If the client is not initialized
        """
        if not self._backend_socket:
            raise CommunicationError(
                CommunicationErrorReason.NOT_INITIALIZED_ERROR,
                "Backend socket is not initialized",
            )
        return self._backend_socket

    async def initialize(self) -> None:
        """Initialize both XSUB and XPUB sockets and start the proxy."""
        try:
            # Initialize the frontend XSUB socket (via parent)
            await super().initialize()

            # Create and configure the backend XPUB socket
            backend_socket = self.context.socket(zmq.SocketType.XPUB)

            # Configure backend socket options
            backend_socket.setsockopt(zmq.RCVTIMEO, 300000)  # 5 minutes
            backend_socket.setsockopt(zmq.SNDTIMEO, 300000)  # 5 minutes
            backend_socket.setsockopt(zmq.TCP_KEEPALIVE, 1)
            backend_socket.setsockopt(zmq.TCP_KEEPALIVE_IDLE, 60)
            backend_socket.setsockopt(zmq.TCP_KEEPALIVE_INTVL, 10)
            backend_socket.setsockopt(zmq.TCP_KEEPALIVE_CNT, 3)
            backend_socket.setsockopt(zmq.IMMEDIATE, 1)
            backend_socket.setsockopt(zmq.LINGER, 0)

            # Apply additional socket options to backend socket
            if self.socket_ops:
                for key, val in self.socket_ops.items():
                    backend_socket.setsockopt(key, val)

            # Bind or connect the backend socket
            if self.backend_bind:
                backend_socket.bind(self.backend_address)
                logger.debug(
                    "XPUB backend socket bound to %s (%s)",
                    self.backend_address,
                    self.client_id,
                )
            else:
                backend_socket.connect(self.backend_address)
                logger.debug(
                    "XPUB backend socket connected to %s (%s)",
                    self.backend_address,
                    self.client_id,
                )

            # Assign the configured socket
            self._backend_socket = backend_socket

            # Start the proxy task
            self._proxy_task = asyncio.create_task(self._run_proxy())
            self.register_task("proxy", self._proxy_task)

            await self.run_hooks(AIPerfHook.ON_INIT)

            logger.info(
                "XPUB/XSUB proxy initialized - Frontend: %s, Backend: %s (%s)",
                self.frontend_address,
                self.backend_address,
                self.client_id,
            )

        except Exception as e:
            raise CommunicationError(
                CommunicationErrorReason.INITIALIZATION_ERROR,
                f"Failed to initialize XPUB/XSUB proxy: {e}",
            ) from e

    async def _run_proxy(self) -> None:
        """Run the proxy using ZMQ's built-in proxy functionality."""
        try:
            logger.debug(
                "Starting XPUB/XSUB proxy using zmq.proxy (%s)", self.client_id
            )

            # Run the built-in ZMQ proxy in a thread since it's blocking
            loop = asyncio.get_event_loop()

            def _run_zmq_proxy():
                """Run the blocking ZMQ proxy in a separate thread."""
                try:
                    # Use ZMQ's built-in proxy - much more efficient than manual forwarding
                    zmq.proxy(self.socket, self.backend_socket)
                except zmq.error.ContextTerminated:
                    # Context was terminated, which is expected during shutdown
                    logger.debug(
                        "ZMQ proxy stopped due to context termination (%s)",
                        self.client_id,
                    )
                except Exception as e:
                    logger.error("Error in ZMQ proxy: %s (%s)", e, self.client_id)

            # Run the proxy in a thread pool executor to avoid blocking the event loop
            await loop.run_in_executor(None, _run_zmq_proxy)

        except asyncio.CancelledError:
            logger.debug("Proxy task cancelled (%s)", self.client_id)
        except Exception as e:
            logger.error("Error running proxy: %s (%s)", e, self.client_id)
        finally:
            logger.debug("XPUB/XSUB proxy stopped (%s)", self.client_id)

    async def shutdown(self) -> None:
        """Shutdown the proxy and close both sockets."""
        if self.is_shutdown:
            return

        logger.debug("Shutting down XPUB/XSUB proxy (%s)", self.client_id)

        # Stop the proxy task
        if self._proxy_task and not self._proxy_task.done():
            self._proxy_task.cancel()
            try:
                await self._proxy_task
            except asyncio.CancelledError:
                pass

        # Shutdown parent (XSUB socket)
        await super().shutdown()

        # Close the backend XPUB socket
        if self._backend_socket:
            self._backend_socket.close()
            self._backend_socket = None

        logger.debug("XPUB/XSUB proxy shutdown complete (%s)", self.client_id)

    def get_frontend_address(self) -> str:
        """Get the frontend (XSUB) address for publisher connections."""
        return self.frontend_address

    def get_backend_address(self) -> str:
        """Get the backend (XPUB) address for subscriber connections."""
        return self.backend_address
