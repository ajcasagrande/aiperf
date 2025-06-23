# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging

import zmq.asyncio

from aiperf.common.comms.zmq.clients.xpub_xsub_proxy import ZMQXPubXSubProxyClient
from aiperf.common.config.zmq_config import BaseZMQCommunicationConfig
from aiperf.common.exceptions import CommunicationError, CommunicationErrorReason
from aiperf.common.service.base_service import BaseService

logger = logging.getLogger(__name__)


class ZMQProxyService(BaseService):
    """Service for managing XPUB/XSUB proxy instances.

    This service provides:
    - Management of one or more XPUB/XSUB proxy instances
    - Configuration-based proxy setup
    - Lifecycle management (start/stop/health monitoring)
    - Integration with the AIPerf service framework
    """

    def __init__(
        self,
        config: BaseZMQCommunicationConfig,
        proxy_name: str = "default",
        context: zmq.asyncio.Context | None = None,
    ) -> None:
        """Initialize the proxy service.

        Args:
            config: ZMQ communication configuration
            proxy_name: Name identifier for the proxy instance
            context: Optional ZMQ context (will create if not provided)
        """
        super().__init__()

        self.config = config
        self.proxy_name = proxy_name
        self._context = context
        self._own_context = context is None
        self._proxy_client: ZMQXPubXSubProxyClient | None = None

        # Default addresses - can be overridden via config
        self._frontend_address = self._get_frontend_address()
        self._backend_address = self._get_backend_address()

    @property
    def context(self) -> zmq.asyncio.Context:
        """Get the ZMQ context, creating one if needed."""
        if not self._context:
            self._context = zmq.asyncio.Context(io_threads=2)
        return self._context

    @property
    def proxy_client(self) -> ZMQXPubXSubProxyClient:
        """Get the proxy client instance.

        Raises:
            CommunicationError: If the service is not initialized
        """
        if not self._proxy_client:
            raise CommunicationError(
                CommunicationErrorReason.NOT_INITIALIZED_ERROR,
                "Proxy service is not initialized",
            )
        return self._proxy_client

    def _get_frontend_address(self) -> str:
        """Get the frontend address for publisher connections.

        This method can be overridden to use different addressing schemes.
        """
        # Use controller pub/sub address as default frontend
        base_addr = self.config.controller_pub_sub_address
        if "tcp://" in base_addr:
            # For TCP, use a different port for proxy frontend
            host, port = base_addr.replace("tcp://", "").split(":")
            frontend_port = int(port) + 100  # Offset by 100
            return f"tcp://{host}:{frontend_port}"
        elif "ipc://" in base_addr:
            # For IPC, use a different socket name
            return base_addr.replace(".ipc", "_proxy_frontend.ipc")
        elif "inproc://" in base_addr:
            # For inproc, use a different name
            return base_addr + "_proxy_frontend"
        else:
            return f"{base_addr}_proxy_frontend"

    def _get_backend_address(self) -> str:
        """Get the backend address for subscriber connections.

        This method can be overridden to use different addressing schemes.
        """
        # Use component pub/sub address as default backend
        base_addr = self.config.component_pub_sub_address
        if "tcp://" in base_addr:
            # For TCP, use a different port for proxy backend
            host, port = base_addr.replace("tcp://", "").split(":")
            backend_port = int(port) + 200  # Offset by 200
            return f"tcp://{host}:{backend_port}"
        elif "ipc://" in base_addr:
            # For IPC, use a different socket name
            return base_addr.replace(".ipc", "_proxy_backend.ipc")
        elif "inproc://" in base_addr:
            # For inproc, use a different name
            return base_addr + "_proxy_backend"
        else:
            return f"{base_addr}_proxy_backend"

    async def initialize(self) -> None:
        """Initialize the proxy service and start the proxy."""
        if self.is_initialized:
            return

        try:
            logger.info(
                "Initializing ZMQ proxy service '%s' - Frontend: %s, Backend: %s",
                self.proxy_name,
                self._frontend_address,
                self._backend_address,
            )

            # Create the proxy client
            self._proxy_client = ZMQXPubXSubProxyClient(
                context=self.context,
                frontend_address=self._frontend_address,
                backend_address=self._backend_address,
                frontend_bind=True,
                backend_bind=True,
            )

            # Initialize the proxy client
            await self._proxy_client.initialize()

            await super().initialize()

            logger.info(
                "ZMQ proxy service '%s' initialized successfully", self.proxy_name
            )

        except Exception as e:
            raise CommunicationError(
                CommunicationErrorReason.INITIALIZATION_ERROR,
                f"Failed to initialize proxy service '{self.proxy_name}': {e}",
            ) from e

    async def shutdown(self) -> None:
        """Shutdown the proxy service."""
        if self.is_shutdown:
            return

        try:
            logger.info("Shutting down ZMQ proxy service '%s'", self.proxy_name)

            # Shutdown the proxy client
            if self._proxy_client:
                await self._proxy_client.shutdown()
                self._proxy_client = None

            # Close our own context if we created it
            if self._own_context and self._context:
                self._context.term()
                self._context = None

            await super().shutdown()

            logger.info("ZMQ proxy service '%s' shutdown complete", self.proxy_name)

        except Exception as e:
            logger.error("Error during proxy service shutdown: %s", e, exc_info=True)
            raise CommunicationError(
                CommunicationErrorReason.SHUTDOWN_ERROR,
                f"Failed to shutdown proxy service '{self.proxy_name}': {e}",
            ) from e

    def get_publisher_address(self) -> str:
        """Get the address that publishers should connect to."""
        return self._frontend_address

    def get_subscriber_address(self) -> str:
        """Get the address that subscribers should connect to."""
        return self._backend_address

    async def health_check(self) -> bool:
        """Check if the proxy service is healthy.

        Returns:
            True if the service is healthy, False otherwise
        """
        try:
            if not self.is_initialized or self.is_shutdown:
                return False

            # Check if proxy client is running
            if not self._proxy_client or not self._proxy_client.is_initialized:
                return False

            # Check if proxy task is still running
            if (
                hasattr(self._proxy_client, "_proxy_task")
                and self._proxy_client._proxy_task
                and self._proxy_client._proxy_task.done()
            ):
                # Proxy task completed unexpectedly
                return False

            return True

        except Exception as e:
            logger.error("Error during health check: %s", e)
            return False

    def get_status(self) -> dict:
        """Get the current status of the proxy service.

        Returns:
            Dictionary containing service status information
        """
        status = {
            "name": self.proxy_name,
            "initialized": self.is_initialized,
            "shutdown": self.is_shutdown,
            "frontend_address": self._frontend_address,
            "backend_address": self._backend_address,
            "healthy": False,
        }

        if self._proxy_client:
            status.update(
                {
                    "proxy_initialized": self._proxy_client.is_initialized,
                    "proxy_shutdown": self._proxy_client.is_shutdown,
                    "client_id": self._proxy_client.client_id,
                }
            )

            # Check if proxy task is running
            if (
                hasattr(self._proxy_client, "_proxy_task")
                and self._proxy_client._proxy_task
            ):
                status["proxy_task_running"] = not self._proxy_client._proxy_task.done()

        # Update health status
        try:
            status["healthy"] = (
                asyncio.run(self.health_check())
                if not asyncio.get_running_loop()
                else False
            )
        except RuntimeError:
            # We're in an async context, can't run health check synchronously
            status["healthy"] = None

        return status
