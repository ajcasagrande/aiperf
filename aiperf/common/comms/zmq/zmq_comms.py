# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import errno
import glob
import logging
import os
from pathlib import Path

import zmq.asyncio

from aiperf.common.comms.base import (
    CommunicationClientFactory,
    CommunicationClientProtocol,
    CommunicationFactory,
    CommunicationProtocol,
)
from aiperf.common.comms.zmq.zmq_base_client import BaseZMQClient
from aiperf.common.config import BaseZMQCommunicationConfig
from aiperf.common.config.zmq_config import ZMQIPCConfig, ZMQTCPConfig
from aiperf.common.enums import (
    CommunicationBackend,
    CommunicationClientAddressType,
    CommunicationClientType,
)
from aiperf.common.hooks import on_start, on_stop
from aiperf.common.lifecycle_mixins import AIPerfLifecycleMixin


class BaseZMQCommunication(AIPerfLifecycleMixin, CommunicationProtocol):
    """ZeroMQ-based implementation of the Communication interface.

    Uses ZeroMQ for publish/subscribe and request/reply patterns to
    facilitate communication between AIPerf components.
    """

    def __init__(
        self,
        config: BaseZMQCommunicationConfig,
    ) -> None:
        super().__init__()
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)
        self.config = config

        self.context = zmq.asyncio.Context.instance()
        self.clients: list[BaseZMQClient] = []

        self.logger.debug(
            "ZMQ communication using protocol: %s",
            type(self.config).__name__,
        )

    def get_address(self, address_type: CommunicationClientAddressType | str) -> str:
        """Get the actual address based on the address type from the config."""
        if isinstance(address_type, CommunicationClientAddressType):
            return self.config.get_address(address_type)
        return address_type

    @on_start
    async def _start_clients(self) -> None:
        """Start all the clients."""
        await asyncio.gather(*(client.start() for client in self.clients))

    @on_stop
    async def _stop_clients(self) -> None:
        """Stop all the clients."""
        await asyncio.gather(*(client.stop() for client in self.clients))
        self.clients.clear()

    def create_client(
        self,
        client_type: CommunicationClientType,
        address: CommunicationClientAddressType | str,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> CommunicationClientProtocol:
        """Create a communication client for a given client type and address.

        Args:
            client_type: The type of client to create.
            address: The type of address to use when looking up in the communication config, or the address itself.
            bind: Whether to bind or connect the socket.
            socket_ops: Additional socket options to set.
        """
        return CommunicationClientFactory.create_instance(
            client_type,
            context=self.context,
            address=self.get_address(address),
            bind=bind,
            socket_ops=socket_ops,
        )


@CommunicationFactory.register(CommunicationBackend.ZMQ_TCP)
class ZMQTCPCommunication(BaseZMQCommunication):
    """ZeroMQ-based implementation of the Communication interface using TCP transport."""

    def __init__(self, config: ZMQTCPConfig | None = None) -> None:
        """Initialize ZMQ TCP communication.

        Args:
            config: ZMQTCPTransportConfig object with configuration parameters
        """
        super().__init__(config or ZMQTCPConfig())


@CommunicationFactory.register(CommunicationBackend.ZMQ_IPC)
class ZMQIPCCommunication(BaseZMQCommunication):
    """ZeroMQ-based implementation of the Communication interface using IPC transport."""

    def __init__(self, config: ZMQIPCConfig | None = None) -> None:
        """Initialize ZMQ IPC communication.

        Args:
            config: ZMQIPCConfig object with configuration parameters
        """
        super().__init__(config or ZMQIPCConfig())
        # call after super init so that way self.config is set
        self._setup_ipc_directory()

    async def initialize(self) -> None:
        """Initialize communication channels.

        This method will create the IPC socket directory if needed.
        """
        await super().initialize()

    async def shutdown(self) -> None:
        """Gracefully shutdown communication channels.

        This method will wait for all clients to shutdown before shutting down
        the context.
        """
        await super().shutdown()
        self._cleanup_ipc_sockets()

    def _setup_ipc_directory(self) -> None:
        """Create IPC socket directory if using IPC transport."""
        self._ipc_socket_dir = Path(self.config.path)
        if not self._ipc_socket_dir.exists():
            self.logger.debug(
                "IPC socket directory does not exist, creating: %s",
                self._ipc_socket_dir,
            )
            self._ipc_socket_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug("Created IPC socket directory: %s", self._ipc_socket_dir)
        else:
            self.logger.debug(
                "IPC socket directory already exists: %s", self._ipc_socket_dir
            )

    def _cleanup_ipc_sockets(self) -> None:
        """Clean up IPC socket files."""
        if self._ipc_socket_dir and self._ipc_socket_dir.exists():
            # Remove all .ipc files in the directory
            ipc_files = glob.glob(str(self._ipc_socket_dir / "*.ipc"))
            for ipc_file in ipc_files:
                try:
                    if os.path.exists(ipc_file):
                        os.unlink(ipc_file)
                        self.logger.debug(f"Removed IPC socket file: {ipc_file}")
                except OSError as e:
                    if e.errno != errno.ENOENT:
                        self.logger.warning(
                            "Failed to remove IPC socket file %s: %s",
                            ipc_file,
                            e,
                        )
