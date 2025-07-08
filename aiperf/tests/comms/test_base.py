# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the base communication functionality including protocols, factories, and interfaces.
"""

from unittest.mock import MagicMock

import pytest

from aiperf.common.comms.base import (
    BaseCommunication,
    CommunicationClientFactory,
    CommunicationClientProtocol,
    CommunicationClientProtocolFactory,
    CommunicationFactory,
    PubClientProtocol,
    PullClientProtocol,
    PushClientProtocol,
    ReplyClientProtocol,
    RequestClientProtocol,
    SubClientProtocol,
    _create_specific_client,
)
from aiperf.common.enums import (
    CommunicationClientAddressType,
    CommunicationClientType,
)


class TestCommunicationClientProtocol:
    """Tests for the CommunicationClientProtocol interface."""

    def test_protocol_interface_methods(self):
        """Test that the protocol defines the required methods."""
        protocol = CommunicationClientProtocol

        # Check that required methods exist
        assert hasattr(protocol, "initialize")
        assert hasattr(protocol, "shutdown")

        # Check method signatures
        assert callable(protocol.initialize)
        assert callable(protocol.shutdown)

    def test_protocol_is_abc(self):
        """Test that CommunicationClientProtocol is properly defined as a protocol."""
        # Protocol should not be instantiable directly
        with pytest.raises(TypeError):
            CommunicationClientProtocol()


class TestCommunicationClientProtocolFactory:
    """Tests for the CommunicationClientProtocolFactory."""

    def test_factory_initialization(self):
        """Test factory initialization."""
        factory = CommunicationClientProtocolFactory()
        assert factory is not None

    def test_factory_register_get_classes(self):
        """Test that the factory properly registers protocol classes."""
        # The factory should have pre-registered classes
        classes_and_types = (
            CommunicationClientProtocolFactory.get_all_classes_and_types()
        )

        # Should have all the expected client types
        expected_types = {
            CommunicationClientType.PUB,
            CommunicationClientType.SUB,
            CommunicationClientType.PUSH,
            CommunicationClientType.PULL,
            CommunicationClientType.REQUEST,
            CommunicationClientType.REPLY,
        }

        registered_types = {client_type for _, client_type in classes_and_types}
        assert registered_types == expected_types

    def test_factory_get_class_by_type(self):
        """Test getting protocol class by type."""
        pub_class = CommunicationClientProtocolFactory.get_class_from_type(
            CommunicationClientType.PUB
        )
        assert pub_class == PubClientProtocol

        sub_class = CommunicationClientProtocolFactory.get_class_from_type(
            CommunicationClientType.SUB
        )
        assert sub_class == SubClientProtocol

        push_class = CommunicationClientProtocolFactory.get_class_from_type(
            CommunicationClientType.PUSH
        )
        assert push_class == PushClientProtocol

        pull_class = CommunicationClientProtocolFactory.get_class_from_type(
            CommunicationClientType.PULL
        )
        assert pull_class == PullClientProtocol

        request_class = CommunicationClientProtocolFactory.get_class_from_type(
            CommunicationClientType.REQUEST
        )
        assert request_class == RequestClientProtocol

        reply_class = CommunicationClientProtocolFactory.get_class_from_type(
            CommunicationClientType.REPLY
        )
        assert reply_class == ReplyClientProtocol

    def test_factory_invalid_type(self):
        """Test factory with invalid type."""
        with pytest.raises(TypeError):
            CommunicationClientProtocolFactory.get_class_from_type("invalid_type")


class TestClientProtocols:
    """Tests for individual client protocol classes."""

    def test_push_client_protocol(self):
        """Test PushClientProtocol interface."""
        # Should have the push method
        assert hasattr(PushClientProtocol, "push")

        # Should inherit from base protocol
        assert issubclass(PushClientProtocol, CommunicationClientProtocol)

    def test_pull_client_protocol(self):
        """Test PullClientProtocol interface."""
        # Should have the register_pull_callback method
        assert hasattr(PullClientProtocol, "register_pull_callback")

        # Should inherit from base protocol
        assert issubclass(PullClientProtocol, CommunicationClientProtocol)

    def test_request_client_protocol(self):
        """Test RequestClientProtocol interface."""
        # Should have the request and request_async methods
        assert hasattr(RequestClientProtocol, "request")
        assert hasattr(RequestClientProtocol, "request_async")

        # Should inherit from base protocol
        assert issubclass(RequestClientProtocol, CommunicationClientProtocol)

    def test_reply_client_protocol(self):
        """Test ReplyClientProtocol interface."""
        # Should have the register_request_handler method
        assert hasattr(ReplyClientProtocol, "register_request_handler")

        # Should inherit from base protocol
        assert issubclass(ReplyClientProtocol, CommunicationClientProtocol)

    def test_sub_client_protocol(self):
        """Test SubClientProtocol interface."""
        # Should have the subscribe method
        assert hasattr(SubClientProtocol, "subscribe")

        # Should inherit from base protocol
        assert issubclass(SubClientProtocol, CommunicationClientProtocol)

    def test_pub_client_protocol(self):
        """Test PubClientProtocol interface."""
        # Should have the publish method
        assert hasattr(PubClientProtocol, "publish")

        # Should inherit from base protocol
        assert issubclass(PubClientProtocol, CommunicationClientProtocol)


class TestCommunicationClientFactory:
    """Tests for the CommunicationClientFactory."""

    def test_factory_initialization(self):
        """Test factory initialization."""
        factory = CommunicationClientFactory()
        assert factory is not None

    def test_factory_is_mixin(self):
        """Test that factory inherits from FactoryMixin."""
        from aiperf.common.factories import FactoryMixin

        assert issubclass(CommunicationClientFactory, FactoryMixin)


class TestBaseCommunication:
    """Tests for the BaseCommunication abstract base class."""

    def test_is_abstract(self):
        """Test that BaseCommunication is abstract."""
        with pytest.raises(TypeError):
            BaseCommunication()

    def test_required_methods(self):
        """Test that BaseCommunication defines required abstract methods."""
        abstract_methods = BaseCommunication.__abstractmethods__

        expected_methods = {
            "initialize",
            "shutdown",
            "is_initialized",
            "stop_requested",
            "get_address",
            "create_client",
        }

        assert abstract_methods == expected_methods

    def test_dynamic_client_creation_methods(self):
        """Test that dynamic client creation methods are added to BaseCommunication."""
        # Test that methods are dynamically added
        assert hasattr(BaseCommunication, "create_pub_client")
        assert hasattr(BaseCommunication, "create_sub_client")
        assert hasattr(BaseCommunication, "create_push_client")
        assert hasattr(BaseCommunication, "create_pull_client")
        assert hasattr(BaseCommunication, "create_request_client")
        assert hasattr(BaseCommunication, "create_reply_client")

    def test_create_specific_client_function(self):
        """Test the _create_specific_client helper function."""
        # Create a mock client type and class
        mock_client_type = CommunicationClientType.PUB
        mock_client_class = MagicMock()

        # Create the specific client creation function
        client_creator = _create_specific_client(mock_client_type, mock_client_class)

        # Test the function name and docstring
        assert client_creator.__name__ == f"create_{mock_client_type.lower()}_client"
        assert client_creator.__doc__ == f"Create a {mock_client_type.upper()} client"

        # Test the function behavior
        mock_communication = MagicMock()
        mock_communication.create_client.return_value = mock_client_class

        _ = client_creator(
            mock_communication, "test_address", True, {"option": "value"}
        )

        mock_communication.create_client.assert_called_once_with(
            mock_client_type, "test_address", True, {"option": "value"}
        )


class TestCommunicationFactory:
    """Tests for the CommunicationFactory."""

    def test_factory_initialization(self):
        """Test factory initialization."""
        factory = CommunicationFactory()
        assert factory is not None

    def test_factory_is_mixin(self):
        """Test that factory inherits from FactoryMixin."""
        from aiperf.common.factories import FactoryMixin

        assert issubclass(CommunicationFactory, FactoryMixin)


class TestCommunicationIntegration:
    """Integration tests for communication components."""

    @pytest.fixture
    def mock_communication_impl(self):
        """Create a mock implementation of BaseCommunication."""

        class MockCommunication(BaseCommunication):
            def __init__(self):
                self._initialized = False
                self._stop_requested = False
                self.clients = []

            async def initialize(self):
                self._initialized = True

            async def shutdown(self):
                self._stop_requested = True

            @property
            def is_initialized(self):
                return self._initialized

            @property
            def stop_requested(self):
                return self._stop_requested

            def get_address(self, address_type):
                if isinstance(address_type, CommunicationClientAddressType):
                    return f"tcp://127.0.0.1:555{address_type.value}"
                return address_type

            def create_client(self, client_type, address, bind=False, socket_ops=None):
                mock_client = MagicMock()
                mock_client.client_type = client_type
                mock_client.address = address
                mock_client.bind = bind
                mock_client.socket_ops = socket_ops
                self.clients.append(mock_client)
                return mock_client

        return MockCommunication()

    @pytest.mark.asyncio
    async def test_communication_lifecycle(self, mock_communication_impl):
        """Test the communication lifecycle."""
        comm = mock_communication_impl

        # Initially not initialized
        assert not comm.is_initialized
        assert not comm.stop_requested

        # Initialize
        await comm.initialize()
        assert comm.is_initialized
        assert not comm.stop_requested

        # Shutdown
        await comm.shutdown()
        assert comm.is_initialized  # Still initialized
        assert comm.stop_requested  # But stop requested

    def test_address_resolution(self, mock_communication_impl):
        """Test address resolution."""
        comm = mock_communication_impl

        # Test with address type
        address = comm.get_address(
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND
        )
        assert address.startswith("tcp://127.0.0.1:")

        # Test with direct address
        direct_address = "tcp://192.168.1.1:8080"
        assert comm.get_address(direct_address) == direct_address

    def test_client_creation(self, mock_communication_impl):
        """Test client creation."""
        comm = mock_communication_impl

        # Create a client
        client = comm.create_client(
            CommunicationClientType.PUB,
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
            bind=True,
            socket_ops={"option": "value"},
        )

        # Verify client properties
        assert client.client_type == CommunicationClientType.PUB
        assert client.bind is True
        assert client.socket_ops == {"option": "value"}

        # Verify client is tracked
        assert len(comm.clients) == 1
        assert comm.clients[0] == client

    def test_dynamic_client_creation_methods(self, mock_communication_impl):
        """Test dynamic client creation methods."""
        comm = mock_communication_impl

        # Test pub client creation
        pub_client = comm.create_pub_client("tcp://127.0.0.1:5555")
        assert pub_client.client_type == CommunicationClientType.PUB

        # Test sub client creation
        sub_client = comm.create_sub_client("tcp://127.0.0.1:5556", bind=True)
        assert sub_client.client_type == CommunicationClientType.SUB
        assert sub_client.bind is True

        # Test all client types
        push_client = comm.create_push_client("tcp://127.0.0.1:5557")
        assert push_client.client_type == CommunicationClientType.PUSH

        pull_client = comm.create_pull_client("tcp://127.0.0.1:5558")
        assert pull_client.client_type == CommunicationClientType.PULL

        request_client = comm.create_request_client("tcp://127.0.0.1:5559")
        assert request_client.client_type == CommunicationClientType.REQUEST

        reply_client = comm.create_reply_client("tcp://127.0.0.1:5560")
        assert reply_client.client_type == CommunicationClientType.REPLY

    @pytest.mark.parametrize(
        "client_type,address_type",
        [
            (
                CommunicationClientType.PUB,
                CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
            ),
            (
                CommunicationClientType.SUB,
                CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND,
            ),
            (CommunicationClientType.PUSH, CommunicationClientAddressType.CREDIT_DROP),
            (
                CommunicationClientType.PULL,
                CommunicationClientAddressType.CREDIT_RETURN,
            ),
            (
                CommunicationClientType.REQUEST,
                CommunicationClientAddressType.DATASET_MANAGER_PROXY_FRONTEND,
            ),
            (
                CommunicationClientType.REPLY,
                CommunicationClientAddressType.DATASET_MANAGER_PROXY_BACKEND,
            ),
        ],
    )
    def test_client_types_with_address_types(
        self, mock_communication_impl, client_type, address_type
    ):
        """Test creating different client types with different address types."""
        comm = mock_communication_impl

        client = comm.create_client(client_type, address_type, bind=False)

        assert client.client_type == client_type
        assert client.bind is False
        assert client.address == comm.get_address(address_type)

    def test_multiple_clients(self, mock_communication_impl):
        """Test creating multiple clients."""
        comm = mock_communication_impl

        # Create multiple clients
        clients = []
        for i, client_type in enumerate(
            [
                CommunicationClientType.PUB,
                CommunicationClientType.SUB,
                CommunicationClientType.PUSH,
                CommunicationClientType.PULL,
            ]
        ):
            client = comm.create_client(client_type, f"tcp://127.0.0.1:555{i}")
            clients.append(client)

        # Verify all clients are tracked
        assert len(comm.clients) == 4
        assert all(client in comm.clients for client in clients)

        # Verify each client has correct type
        for i, client in enumerate(clients):
            expected_type = [
                CommunicationClientType.PUB,
                CommunicationClientType.SUB,
                CommunicationClientType.PUSH,
                CommunicationClientType.PULL,
            ][i]
            assert client.client_type == expected_type
