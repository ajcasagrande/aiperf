# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import errno
import glob
import logging
import os
from abc import ABC
from pathlib import Path

import zmq.asyncio

from aiperf.common.comms.base import BaseCommunication
from aiperf.common.comms.zmq.clients import BaseZMQClient
from aiperf.common.comms.zmq.clients.dealer_req import ZMQDealerReqClient
from aiperf.common.comms.zmq.clients.pub import ZMQPubClient
from aiperf.common.comms.zmq.clients.pull import ZMQPullClient
from aiperf.common.comms.zmq.clients.push import ZMQPushClient
from aiperf.common.comms.zmq.clients.router_rep import ZMQRouterRepClient
from aiperf.common.comms.zmq.clients.sub import ZMQSubClient
from aiperf.common.config import (
    BaseZMQCommunicationConfig,
    ZMQIPCConfig,
    ZMQTCPTransportConfig,
)
from aiperf.common.enums import CommunicationBackend, ServiceType
from aiperf.common.exceptions import (
    CommunicationError,
    CommunicationErrorReason,
)
from aiperf.common.factories import CommunicationFactory

logger = logging.getLogger(__name__)


class BaseZMQCommunication(BaseCommunication, ABC):
    """ZeroMQ-based implementation of the Communication interface.

    Uses ZeroMQ for publish/subscribe and request/reply patterns to
    facilitate communication between AIPerf components.
    """

    def __init__(
        self,
        config: BaseZMQCommunicationConfig | None = None,
        parent_service_type: ServiceType | None = None,
    ) -> None:
        """Initialize ZMQ communication.

        Args:
            config: ZMQCommunicationConfig object with configuration parameters
        """
        self.stop_event: asyncio.Event = asyncio.Event()
        self.initialized_event: asyncio.Event = asyncio.Event()
        self.config = config or ZMQIPCConfig()

        self._context: zmq.asyncio.Context | None = None
        self.clients: list[BaseZMQClient] = []

        # TODO: Look into using this for determining bind vs connect
        self.parent_service_type: ServiceType | None = parent_service_type

        logger.debug(
            "ZMQ communication using protocol: %s",
            type(self.config).__name__,
        )

    @property
    def context(self) -> zmq.asyncio.Context:
        """Get the ZeroMQ context.

        Returns:
            ZeroMQ context
        """
        if not self._context:
            raise CommunicationError(
                CommunicationErrorReason.INITIALIZATION_ERROR,
                "Communication channels are not initialized",
            )
        return self._context

    @property
    def is_initialized(self) -> bool:
        """Check if communication channels are initialized.

        Returns:
            True if communication channels are initialized, False otherwise
        """
        return self.initialized_event.is_set()

    @property
    def is_shutdown(self) -> bool:
        """Check if communication channels are shutdown.

        Returns:
            True if communication channels are shutdown, False otherwise
        """
        return self.stop_event.is_set()

    async def initialize(self) -> None:
        """Initialize communication channels.

        Returns:
            True if initialization was successful, False otherwise
        """
        if self.is_initialized:
            return

        # Increase the number of IO threads to 2
        self._context = zmq.asyncio.Context(io_threads=2)
        self.initialized_event.set()

    async def shutdown(self) -> None:
        """Gracefully shutdown communication channels.

        This method will wait for all clients to shutdown before shutting down
        the context.

        Returns:
            True if shutdown was successful, False otherwise
        """
        if self.is_shutdown:
            return

        try:
            if not self.stop_event.is_set():
                self.stop_event.set()

            await asyncio.gather(*(client.shutdown() for client in self.clients))

            if self.context:
                self.context.term()

            self._context = None

        except asyncio.CancelledError:
            pass

        except Exception as e:
            raise CommunicationError(
                CommunicationErrorReason.SHUTDOWN_ERROR,
                "Failed to shutdown ZMQ communication",
            ) from e

        finally:
            self.clients.clear()
            self._context = None

    async def _ensure_initialized(self) -> None:
        """Ensure the communication channels are initialized.

        Raises:
            CommunicationError: If the communication channels are not initialized
                or shutdown
            asyncio.CancelledError: If the communication channels are shutdown
        """
        if not self.is_initialized:
            await self.initialize()
        if self.is_shutdown:
            raise asyncio.CancelledError()

    async def create_pub_client(
        self, address: str, bind: bool = False, socket_ops: dict | None = None
    ) -> ZMQPubClient:
        """Create a publish client.

        Args:
            address: The address to bind or connect to.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        await self._ensure_initialized()

        pub_client = ZMQPubClient(self.context, address, bind, socket_ops)
        self.clients.append(pub_client)
        return pub_client

    async def create_sub_client(
        self, address: str, bind: bool = False, socket_ops: dict | None = None
    ) -> ZMQSubClient:
        """Create a subscribe client.

        Args:
            address: The address to bind or connect to.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        await self._ensure_initialized()

        sub_client = ZMQSubClient(self.context, address, bind, socket_ops)
        self.clients.append(sub_client)
        return sub_client

    async def create_push_client(
        self, address: str, bind: bool = False, socket_ops: dict | None = None
    ) -> ZMQPushClient:
        """Create a push client.

        Args:
            address: The address to bind or connect to.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        await self._ensure_initialized()

        push_client = ZMQPushClient(self.context, address, bind, socket_ops)
        self.clients.append(push_client)
        return push_client

    async def create_pull_client(
        self, address: str, bind: bool = False, socket_ops: dict | None = None
    ) -> ZMQPullClient:
        """Create a pull client.

        Args:
            address: The address to bind or connect to.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        await self._ensure_initialized()

        pull_client = ZMQPullClient(self.context, address, bind, socket_ops)
        self.clients.append(pull_client)
        return pull_client

    async def create_req_client(
        self, address: str, bind: bool = False, socket_ops: dict | None = None
    ) -> ZMQDealerReqClient:
        """Create a request DEALER client.

        Args:
            address: The address to bind or connect to.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        await self._ensure_initialized()

        req_client = ZMQDealerReqClient(self.context, address, bind, socket_ops)
        self.clients.append(req_client)
        return req_client

    async def create_rep_client(
        self, address: str, bind: bool = False, socket_ops: dict | None = None
    ) -> ZMQRouterRepClient:
        """Create a reply ROUTER client.

        Args:
            address: The address to bind or connect to.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        await self._ensure_initialized()

        rep_client = ZMQRouterRepClient(self.context, address, bind, socket_ops)
        self.clients.append(rep_client)
        return rep_client


@CommunicationFactory.register(CommunicationBackend.ZMQ_TCP)
class ZMQTCPCommunication(BaseZMQCommunication):
    """ZeroMQ-based implementation of the Communication interface using TCP transport."""

    def __init__(self, config: ZMQTCPTransportConfig | None = None) -> None:
        """Initialize ZMQ TCP communication.

        Args:
            config: ZMQTCPTransportConfig object with configuration parameters
        """
        super().__init__(config or ZMQTCPTransportConfig())


@CommunicationFactory.register(CommunicationBackend.ZMQ_IPC)
class ZMQIPCCommunication(BaseZMQCommunication):
    """ZeroMQ-based implementation of the Communication interface using IPC transport."""

    def __init__(self, config: ZMQIPCConfig | None = None) -> None:
        """Initialize ZMQ IPC communication.

        Args:
            config: ZMQIPCConfig object with configuration parameters
        """
        super().__init__(config or ZMQIPCConfig())

    async def initialize(self) -> None:
        """Initialize communication channels.

        This method will create the IPC socket directory if needed.

        Raises:
            CommunicationError: If the communication channels are not initialized
                or shutdown
        """
        self._setup_ipc_directory()
        await super().initialize()

    async def shutdown(self) -> None:
        """Gracefully shutdown communication channels.

        This method will wait for all clients to shutdown before shutting down
        the context.

        Raises:
            CommunicationError: If there was an error shutting down the communication
                channels
        """
        await super().shutdown()
        self._cleanup_ipc_sockets()

    def _setup_ipc_directory(self) -> None:
        """Create IPC socket directory if using IPC transport."""
        self._ipc_socket_dir = Path(self.config.path)
        self._ipc_socket_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created IPC socket directory: {self._ipc_socket_dir}")

    def _cleanup_ipc_sockets(self) -> None:
        """Clean up IPC socket files."""
        if self._ipc_socket_dir and self._ipc_socket_dir.exists():
            # Remove all .ipc files in the directory
            ipc_files = glob.glob(str(self._ipc_socket_dir / "*.ipc"))
            for ipc_file in ipc_files:
                try:
                    if os.path.exists(ipc_file):
                        os.unlink(ipc_file)
                        logger.debug(f"Removed IPC socket file: {ipc_file}")
                except OSError as e:
                    if e.errno != errno.ENOENT:
                        logger.warning(
                            "Failed to remove IPC socket file %s: %s",
                            ipc_file,
                            e,
                        )
