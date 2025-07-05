# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for ZMQ communication implementations including TCP and IPC.
"""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from aiperf.common.comms.zmq import (
    BaseZMQCommunication,
    ZMQIPCCommunication,
    ZMQTCPCommunication,
)
from aiperf.common.config.zmq_config import ZMQIPCConfig, ZMQTCPConfig
from aiperf.common.enums import (
    CommunicationBackend,
    CommunicationClientAddressType,
    CommunicationClientType,
)
from aiperf.common.exceptions import ShutdownError


class TestBaseZMQCommunication:
    """Tests for BaseZMQCommunication class."""

    def test_abstract_base_class(self):
        """Test that BaseZMQCommunication is abstract."""
        with pytest.raises(TypeError):
            BaseZMQCommunication()

    def test_inheritance(self):
        """Test BaseZMQCommunication inheritance."""
        from aiperf.common.comms.base import BaseCommunication

        assert issubclass(BaseZMQCommunication, BaseCommunication)

    @pytest.mark.asyncio
    async def test_initialization(self, tcp_config: ZMQTCPConfig):
        """Test initialization of concrete implementation."""
        comm = ZMQTCPCommunication(tcp_config)

        assert comm.config == tcp_config
        assert not comm.is_initialized
        assert not comm.stop_requested
        assert comm.clients == []
        assert comm.context is not None


class TestZMQTCPCommunication:
    """Tests for ZMQTCPCommunication class."""

    def test_init_with_config(self, tcp_config: ZMQTCPConfig):
        """Test initialization with config."""
        comm = ZMQTCPCommunication(tcp_config)

        assert comm.config == tcp_config
        assert not comm.is_initialized
        assert not comm.stop_requested

    def test_init_without_config(self):
        """Test initialization without config."""
        comm = ZMQTCPCommunication()

        assert isinstance(comm.config, ZMQTCPConfig)
        assert not comm.is_initialized
        assert not comm.stop_requested

    def test_factory_registration(self):
        """Test that ZMQTCPCommunication is properly registered."""
        from aiperf.common.comms.base import CommunicationFactory

        # Should be able to create via factory
        comm = CommunicationFactory.create_instance(
            CommunicationBackend.ZMQ_TCP, config=ZMQTCPConfig()
        )

        assert isinstance(comm, ZMQTCPCommunication)

    @pytest.mark.asyncio
    async def test_initialize(self, tcp_config: ZMQTCPConfig):
        """Test communication initialization."""
        comm = ZMQTCPCommunication(tcp_config)

        await comm.initialize()

        assert comm.is_initialized
        assert not comm.stop_requested

        await comm.shutdown()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, tcp_config: ZMQTCPConfig):
        """Test that initialize is idempotent."""
        comm = ZMQTCPCommunication(tcp_config)

        await comm.initialize()
        assert comm.is_initialized

        # Initialize again
        await comm.initialize()
        assert comm.is_initialized

        await comm.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown(self, tcp_config: ZMQTCPConfig):
        """Test communication shutdown."""
        comm = ZMQTCPCommunication(tcp_config)

        await comm.initialize()
        assert comm.is_initialized
        assert not comm.stop_requested

        await comm.shutdown()
        assert comm.stop_requested

        # Clients should be cleared
        assert comm.clients == []

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self, tcp_config: ZMQTCPConfig):
        """Test that shutdown is idempotent."""
        comm = ZMQTCPCommunication(tcp_config)

        await comm.initialize()
        await comm.shutdown()
        assert comm.stop_requested

        # Shutdown again
        await comm.shutdown()
        assert comm.stop_requested

    @pytest.mark.asyncio
    async def test_shutdown_without_initialize(self, tcp_config: ZMQTCPConfig):
        """Test shutdown without initialization."""
        comm = ZMQTCPCommunication(tcp_config)

        # Should not raise error
        await comm.shutdown()
        assert comm.stop_requested

    def test_get_address_with_address_type(self, tcp_config: ZMQTCPConfig):
        """Test get_address with address type."""
        comm = ZMQTCPCommunication(tcp_config)

        address = comm.get_address(
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
        )
        assert address.startswith("tcp://")
        assert isinstance(address, str)

    def test_get_address_with_string(self, tcp_config: ZMQTCPConfig):
        """Test get_address with string address."""
        comm = ZMQTCPCommunication(tcp_config)

        test_address = "tcp://192.168.1.1:8080"
        address = comm.get_address(test_address)
        assert address == test_address

    @pytest.mark.asyncio
    async def test_create_client(self, tcp_config: ZMQTCPConfig):
        """Test client creation."""
        comm = ZMQTCPCommunication(tcp_config)

        client = comm.create_client(
            CommunicationClientType.PUB,
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
            bind=True,
        )

        assert client is not None
        assert len(comm.clients) == 1
        assert comm.clients[0] == client

        await comm.shutdown()

    @pytest.mark.asyncio
    async def test_create_multiple_clients(self, tcp_config: ZMQTCPConfig):
        """Test creating multiple clients."""
        comm = ZMQTCPCommunication(tcp_config)

        client1 = comm.create_client(
            CommunicationClientType.PUB,
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
        )

        client2 = comm.create_client(
            CommunicationClientType.SUB,
            CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND,
        )

        assert len(comm.clients) == 2
        assert client1 in comm.clients
        assert client2 in comm.clients

        await comm.shutdown()

    @pytest.mark.asyncio
    async def test_create_client_with_socket_options(self, tcp_config: ZMQTCPConfig):
        """Test creating client with socket options."""
        import zmq

        comm = ZMQTCPCommunication(tcp_config)

        socket_ops = {zmq.RCVTIMEO: 1000, zmq.SNDTIMEO: 2000}
        client = comm.create_client(
            CommunicationClientType.PUSH,
            CommunicationClientAddressType.CREDIT_DROP,
            bind=False,
            socket_ops=socket_ops,
        )

        assert client is not None
        assert len(comm.clients) == 1

        await comm.shutdown()

    @pytest.mark.parametrize(
        "client_type",
        [
            CommunicationClientType.PUB,
            CommunicationClientType.SUB,
            CommunicationClientType.PUSH,
            CommunicationClientType.PULL,
            CommunicationClientType.REQUEST,
            CommunicationClientType.REPLY,
        ],
    )
    @pytest.mark.asyncio
    async def test_create_all_client_types(self, tcp_config: ZMQTCPConfig, client_type):
        """Test creating all client types."""
        comm = ZMQTCPCommunication(tcp_config)

        client = comm.create_client(
            client_type, CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
        )

        assert client is not None
        assert len(comm.clients) == 1

        await comm.shutdown()

    @pytest.mark.asyncio
    async def test_clients_shutdown_on_communication_shutdown(
        self, tcp_config: ZMQTCPConfig
    ):
        """Test that clients are shutdown when communication shuts down."""
        comm = ZMQTCPCommunication(tcp_config)

        # Create some clients
        client1 = comm.create_client(
            CommunicationClientType.PUB,
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
        )

        client2 = comm.create_client(
            CommunicationClientType.SUB,
            CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND,
        )

        # Initialize clients
        await client1.initialize()
        await client2.initialize()

        assert client1.is_initialized
        assert client2.is_initialized

        # Shutdown communication
        await comm.shutdown()

        # Clients should be shutdown
        assert client1.stop_requested or not client1.is_initialized
        assert client2.stop_requested or not client2.is_initialized

        # Clients list should be cleared
        assert comm.clients == []

    @pytest.mark.asyncio
    async def test_error_handling_in_shutdown(self, tcp_config: ZMQTCPConfig):
        """Test error handling during shutdown."""
        comm = ZMQTCPCommunication(tcp_config)

        # Create a client that will fail on shutdown
        client = comm.create_client(
            CommunicationClientType.PUB,
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
        )

        # Mock the client to raise an error on shutdown
        with patch.object(client, "shutdown", side_effect=Exception("Shutdown error")):
            with pytest.raises(ShutdownError):
                await comm.shutdown()

    @pytest.mark.asyncio
    async def test_dynamic_client_creation_methods(self, tcp_config: ZMQTCPConfig):
        """Test dynamic client creation methods."""
        comm = ZMQTCPCommunication(tcp_config)

        # Test pub client
        pub_client = comm.create_pub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
        )
        assert pub_client is not None

        # Test sub client
        sub_client = comm.create_sub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND
        )
        assert sub_client is not None

        # Test push client
        push_client = comm.create_push_client(
            CommunicationClientAddressType.CREDIT_DROP
        )
        assert push_client is not None

        # Test pull client
        pull_client = comm.create_pull_client(
            CommunicationClientAddressType.CREDIT_RETURN
        )
        assert pull_client is not None

        # Test request client
        request_client = comm.create_request_client(
            CommunicationClientAddressType.DATASET_MANAGER_PROXY_FRONTEND
        )
        assert request_client is not None

        # Test reply client
        reply_client = comm.create_reply_client(
            CommunicationClientAddressType.DATASET_MANAGER_PROXY_BACKEND
        )
        assert reply_client is not None

        assert len(comm.clients) == 6

        await comm.shutdown()


class TestZMQIPCCommunication:
    """Tests for ZMQIPCCommunication class."""

    def test_init_with_config(self, ipc_config: ZMQIPCConfig):
        """Test initialization with config."""
        comm = ZMQIPCCommunication(ipc_config)

        assert comm.config == ipc_config
        assert not comm.is_initialized
        assert not comm.stop_requested

    def test_init_without_config(self):
        """Test initialization without config."""
        comm = ZMQIPCCommunication()

        assert isinstance(comm.config, ZMQIPCConfig)
        assert not comm.is_initialized
        assert not comm.stop_requested

    def test_factory_registration(self):
        """Test that ZMQIPCCommunication is properly registered."""
        from aiperf.common.comms.base import CommunicationFactory

        # Should be able to create via factory
        comm = CommunicationFactory.create_instance(
            CommunicationBackend.ZMQ_IPC, config=ZMQIPCConfig()
        )

        assert isinstance(comm, ZMQIPCCommunication)

    @pytest.mark.asyncio
    async def test_initialize(self, ipc_config: ZMQIPCConfig):
        """Test communication initialization."""
        comm = ZMQIPCCommunication(ipc_config)

        await comm.initialize()

        assert comm.is_initialized
        assert not comm.stop_requested

        await comm.shutdown()

    @pytest.mark.asyncio
    async def test_ipc_directory_creation(self):
        """Test IPC directory creation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ipc_path = Path(tmp_dir) / "test_ipc"
            config = ZMQIPCConfig(path=str(ipc_path))

            # Directory should not exist initially
            assert not ipc_path.exists()

            comm = ZMQIPCCommunication(config)

            # Directory should be created during initialization
            assert ipc_path.exists()
            assert ipc_path.is_dir()

            await comm.shutdown()

    @pytest.mark.asyncio
    async def test_ipc_directory_already_exists(self):
        """Test behavior when IPC directory already exists."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ipc_path = Path(tmp_dir) / "existing_ipc"
            ipc_path.mkdir()

            config = ZMQIPCConfig(path=str(ipc_path))
            comm = ZMQIPCCommunication(config)

            # Should not raise error
            assert ipc_path.exists()

            await comm.shutdown()

    @pytest.mark.asyncio
    async def test_ipc_socket_cleanup(self):
        """Test IPC socket cleanup."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            ipc_path = Path(tmp_dir) / "cleanup_test"
            config = ZMQIPCConfig(path=str(ipc_path))

            comm = ZMQIPCCommunication(config)

            # Create some clients
            client1 = comm.create_client(
                CommunicationClientType.PUB,
                CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
            )

            client2 = comm.create_client(
                CommunicationClientType.SUB,
                CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND,
            )

            await comm.initialize()

            # Shutdown should clean up
            await comm.shutdown()

            # Directory should still exist but may be cleaned up
            assert ipc_path.exists()

    def test_get_address_with_address_type(self, ipc_config: ZMQIPCConfig):
        """Test get_address with address type."""
        comm = ZMQIPCCommunication(ipc_config)

        address = comm.get_address(
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
        )
        assert address.startswith("ipc://")
        assert isinstance(address, str)

    def test_get_address_with_string(self, ipc_config: ZMQIPCConfig):
        """Test get_address with string address."""
        comm = ZMQIPCCommunication(ipc_config)

        test_address = "inproc://test_ipc_communication"
        address = comm.get_address(test_address)
        assert address == test_address

    @pytest.mark.asyncio
    async def test_create_client(self, ipc_config: ZMQIPCConfig):
        """Test client creation."""
        comm = ZMQIPCCommunication(ipc_config)

        client = comm.create_client(
            CommunicationClientType.PUB,
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
            bind=True,
        )

        assert client is not None
        assert len(comm.clients) == 1
        assert comm.clients[0] == client

        await comm.shutdown()

    @pytest.mark.parametrize(
        "client_type",
        [
            CommunicationClientType.PUB,
            CommunicationClientType.SUB,
            CommunicationClientType.PUSH,
            CommunicationClientType.PULL,
            CommunicationClientType.REQUEST,
            CommunicationClientType.REPLY,
        ],
    )
    @pytest.mark.asyncio
    async def test_create_all_client_types_ipc(
        self, ipc_config: ZMQIPCConfig, client_type
    ):
        """Test creating all client types for IPC."""
        comm = ZMQIPCCommunication(ipc_config)

        client = comm.create_client(
            client_type, CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
        )

        assert client is not None
        assert len(comm.clients) == 1

        await comm.shutdown()

    @pytest.mark.asyncio
    async def test_mixed_communication_types(
        self, tcp_config: ZMQTCPConfig, ipc_config: ZMQIPCConfig
    ):
        """Test using both TCP and IPC communication types."""
        tcp_comm = ZMQTCPCommunication(tcp_config)
        ipc_comm = ZMQIPCCommunication(ipc_config)

        # Create clients on both
        tcp_client = tcp_comm.create_client(
            CommunicationClientType.PUB,
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
        )

        ipc_client = ipc_comm.create_client(
            CommunicationClientType.SUB,
            CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND,
        )

        await tcp_comm.initialize()
        await ipc_comm.initialize()

        assert tcp_comm.is_initialized
        assert ipc_comm.is_initialized

        await tcp_comm.shutdown()
        await ipc_comm.shutdown()

    @pytest.mark.asyncio
    async def test_communication_lifecycle_comprehensive(
        self, tcp_config: ZMQTCPConfig
    ):
        """Test comprehensive communication lifecycle."""
        comm = ZMQTCPCommunication(tcp_config)

        # Initial state
        assert not comm.is_initialized
        assert not comm.stop_requested
        assert comm.clients == []

        # Create clients before initialization
        pub_client = comm.create_pub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
        )
        sub_client = comm.create_sub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND
        )

        assert len(comm.clients) == 2

        # Initialize communication
        await comm.initialize()
        assert comm.is_initialized

        # All clients should be initialized
        assert pub_client.is_initialized
        assert sub_client.is_initialized

        # Shutdown communication
        await comm.shutdown()
        assert comm.stop_requested

        # Clients should be shutdown
        assert pub_client.stop_requested or not pub_client.is_initialized
        assert sub_client.stop_requested or not sub_client.is_initialized

        # Clients list should be cleared
        assert comm.clients == []

    @pytest.mark.asyncio
    async def test_error_handling_client_creation(self, tcp_config: ZMQTCPConfig):
        """Test error handling during client creation."""
        comm = ZMQTCPCommunication(tcp_config)

        # Mock the factory to raise an error
        with patch(
            "aiperf.common.comms.base.CommunicationClientFactory.create_instance"
        ) as mock_create:
            mock_create.side_effect = Exception("Client creation failed")

            with pytest.raises(Exception, match="Client creation failed"):
                comm.create_client(
                    CommunicationClientType.PUB,
                    CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
                )

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, tcp_config: ZMQTCPConfig):
        """Test concurrent operations on communication."""
        comm = ZMQTCPCommunication(tcp_config)

        # Create multiple clients concurrently
        async def create_client(client_type, address_type):
            return comm.create_client(client_type, address_type)

        tasks = [
            create_client(
                CommunicationClientType.PUB,
                CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
            ),
            create_client(
                CommunicationClientType.SUB,
                CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND,
            ),
            create_client(
                CommunicationClientType.PUSH, CommunicationClientAddressType.CREDIT_DROP
            ),
            create_client(
                CommunicationClientType.PULL,
                CommunicationClientAddressType.CREDIT_RETURN,
            ),
        ]

        clients = await asyncio.gather(*tasks)

        assert len(clients) == 4
        assert len(comm.clients) == 4

        # Initialize and shutdown concurrently
        await comm.initialize()
        await comm.shutdown()

    @pytest.mark.asyncio
    async def test_context_management(self, tcp_config: ZMQTCPConfig):
        """Test ZMQ context management."""
        comm = ZMQTCPCommunication(tcp_config)

        # Context should be created
        assert comm.context is not None

        # Multiple clients should share the same context
        client1 = comm.create_client(
            CommunicationClientType.PUB,
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
        )

        client2 = comm.create_client(
            CommunicationClientType.SUB,
            CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND,
        )

        assert client1.context == comm.context
        assert client2.context == comm.context
        assert client1.context == client2.context

        await comm.shutdown()
