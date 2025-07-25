# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import errno
import glob
import os
from abc import ABC
from pathlib import Path

import zmq.asyncio

from aiperf.common.comms.base_comms import (
    BaseCommunication,
    CommunicationClientProtocol,
)
from aiperf.common.config import BaseZMQCommunicationConfig
from aiperf.common.config.zmq_config import ZMQIPCConfig, ZMQTCPConfig
from aiperf.common.enums import (
    CommAddress,
    CommClientType,
    CommunicationBackend,
)
from aiperf.common.exceptions import ShutdownError
from aiperf.common.factories import CommunicationClientFactory, CommunicationFactory
from aiperf.common.hooks import implements_protocol, on_init, on_start, on_stop
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.protocols import CommunicationProtocol
from aiperf.common.types import CommAddressType


@implements_protocol(CommunicationProtocol)
class BaseZMQCommunication(BaseCommunication, AIPerfLoggerMixin, ABC):
    """ZeroMQ-based implementation of the Communication interface.

    Uses ZeroMQ for publish/subscribe and request/reply patterns to
    facilitate communication between AIPerf components.
    """

    def __init__(
        self,
        config: BaseZMQCommunicationConfig,
    ) -> None:
        super().__init__()
        self.config = config

        self.context = zmq.asyncio.Context.instance()
        self.clients: list[CommunicationClientProtocol] = []
        self._clients_cache: dict[
            tuple[CommClientType, CommAddressType, bool], CommunicationClientProtocol
        ] = {}

        self.debug(f"ZMQ communication using protocol: {type(self.config).__name__}")

    def get_address(self, address_type: CommAddressType) -> str:
        """Get the actual address based on the address type from the config."""
        if isinstance(address_type, CommAddress):
            return self.config.get_address(address_type)
        return address_type

    @on_init
    async def _initialize_clients(self) -> None:
        for client in self.clients:
            self.debug(lambda client=client: f"Initializing ZMQ client: {client}")
            await client.initialize()

    @on_start
    async def _start_clients(self) -> None:
        for client in self.clients:
            self.debug(lambda client=client: f"Starting ZMQ client: {client}")
            await client.start()

    @on_stop
    async def _stop_clients(self) -> None:
        """Gracefully shutdown communication channels.

        This method will wait for all clients to shutdown before shutting down
        the context.

        Returns:
            True if shutdown was successful, False otherwise
        """
        try:
            for client in self.clients:
                self.debug(lambda client=client: f"Stopping ZMQ client: {client}")
                await client.stop()

        except Exception as e:
            raise ShutdownError(
                "Failed to shutdown ZMQ communication",
            ) from e

        finally:
            self.clients.clear()

    def create_client(
        self,
        client_type: CommClientType,
        address: CommAddressType,
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
        if (client_type, address, bind) in self._clients_cache:
            return self._clients_cache[(client_type, address, bind)]

        client = CommunicationClientFactory.create_instance(
            client_type,
            address=self.get_address(address),
            bind=bind,
            socket_ops=socket_ops,
        )

        self._clients_cache[(client_type, address, bind)] = client
        self.clients.append(client)
        return client


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

    def _setup_ipc_directory(self) -> None:
        """Create IPC socket directory if using IPC transport."""
        self._ipc_socket_dir = Path(self.config.path)
        if not self._ipc_socket_dir.exists():
            self.debug(
                f"IPC socket directory does not exist, creating: {self._ipc_socket_dir}"
            )
            self._ipc_socket_dir.mkdir(parents=True, exist_ok=True)
            self.debug(f"Created IPC socket directory: {self._ipc_socket_dir}")
        else:
            self.debug(f"IPC socket directory already exists: {self._ipc_socket_dir}")

    @on_stop
    def _cleanup_ipc_sockets(self) -> None:
        """Clean up IPC socket files."""
        if self._ipc_socket_dir and self._ipc_socket_dir.exists():
            # Remove all .ipc files in the directory
            ipc_files = glob.glob(str(self._ipc_socket_dir / "*.ipc"))
            for ipc_file in ipc_files:
                try:
                    if os.path.exists(ipc_file):
                        os.unlink(ipc_file)
                        self.debug(f"Removed IPC socket file: {ipc_file}")
                except OSError as e:
                    if e.errno != errno.ENOENT:
                        self.warning(
                            f"Failed to remove IPC socket file {ipc_file}: {e}"
                        )
