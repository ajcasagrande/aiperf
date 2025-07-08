# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for the ZMQ base client functionality.
"""

import asyncio
from unittest.mock import MagicMock

import pytest
import zmq
import zmq.asyncio

from aiperf.common.comms.zmq import BaseZMQClient, ZMQSocketDefaults
from aiperf.common.exceptions import CommunicationError, InitializationError
from aiperf.common.hooks import AIPerfHook, AIPerfTaskHook


class TestBaseZMQClient:
    """Tests for BaseZMQClient class."""

    def test_init_basic(self, mock_zmq_context_instance: MagicMock):
        """Test basic initialization of BaseZMQClient."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.PUB,
            address="inproc://test_addr_5555",
            bind=True,
        )

        assert client.context == mock_zmq_context_instance
        assert client.socket_type == zmq.PUB
        assert client.address == "inproc://test_addr_5555"
        assert client.bind is True
        assert client.socket_ops == {}
        assert client.client_id.startswith("pub_client_")
        assert not client.is_initialized
        assert not client.stop_requested

    def test_init_with_options(self, mock_zmq_context_instance: MagicMock):
        """Test initialization with socket options."""
        socket_ops = {zmq.RCVTIMEO: 1000, zmq.SNDTIMEO: 2000}
        client_id = "test_client_123"

        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.SUB,
            address="inproc://test_addr_5556",
            bind=False,
            socket_ops=socket_ops,
            client_id=client_id,
        )

        assert client.socket_ops == socket_ops
        assert client.client_id == client_id
        assert client.bind is False

    def test_socket_type_name(self, mock_zmq_context_instance: MagicMock):
        """Test socket type name property."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.PUSH,
            address="inproc://test_addr_5557",
            bind=True,
        )

        assert client.socket_type_name == "PUSH"

    def test_socket_property_not_initialized(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test socket property when not initialized."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.PULL,
            address="inproc://test_addr_5558",
            bind=False,
        )

        with pytest.raises(
            CommunicationError, match="Communication channels are not initialized"
        ):
            _ = client.socket

    @pytest.mark.asyncio
    async def test_initialize_bind(self, mock_zmq_context_instance: MagicMock):
        """Test initialization with bind=True."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.PUB,
            address="inproc://test_addr_5555",
            bind=True,
        )

        await client.initialize()

        assert client.is_initialized
        mock_zmq_context_instance.socket.assert_called_once_with(zmq.PUB)

        mock_socket = mock_zmq_context_instance.socket.return_value
        mock_socket.bind.assert_called_once_with("inproc://test_addr_5555")
        mock_socket.connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_connect(self, mock_zmq_context_instance: MagicMock):
        """Test initialization with bind=False."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.SUB,
            address="inproc://test_addr_5556",
            bind=False,
        )

        await client.initialize()

        assert client.is_initialized
        mock_zmq_context_instance.socket.assert_called_once_with(zmq.SUB)

        mock_socket = mock_zmq_context_instance.socket.return_value
        mock_socket.connect.assert_called_once_with("inproc://test_addr_5556")
        mock_socket.bind.assert_not_called()

    @pytest.mark.asyncio
    async def test_initialize_socket_defaults(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test that socket defaults are set during initialization."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.PUSH,
            address="inproc://test_addr_5557",
            bind=True,
        )

        await client.initialize()

        mock_socket = mock_zmq_context_instance.socket.return_value

        # Check that default socket options are set
        expected_calls = [
            (zmq.RCVTIMEO, ZMQSocketDefaults.RCVTIMEO),
            (zmq.SNDTIMEO, ZMQSocketDefaults.SNDTIMEO),
            (zmq.TCP_KEEPALIVE, ZMQSocketDefaults.TCP_KEEPALIVE),
            (zmq.TCP_KEEPALIVE_IDLE, ZMQSocketDefaults.TCP_KEEPALIVE_IDLE),
            (zmq.TCP_KEEPALIVE_INTVL, ZMQSocketDefaults.TCP_KEEPALIVE_INTVL),
            (zmq.TCP_KEEPALIVE_CNT, ZMQSocketDefaults.TCP_KEEPALIVE_CNT),
            (zmq.IMMEDIATE, ZMQSocketDefaults.IMMEDIATE),
            (zmq.LINGER, ZMQSocketDefaults.LINGER),
        ]

        for option, value in expected_calls:
            mock_socket.setsockopt.assert_any_call(option, value)

    @pytest.mark.asyncio
    async def test_initialize_custom_socket_options(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test initialization with custom socket options."""
        custom_options = {
            zmq.RCVTIMEO: 5000,
            zmq.SNDTIMEO: 3000,
            zmq.LINGER: 1000,
        }

        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.PULL,
            address="inproc://test_addr_5558",
            bind=False,
            socket_ops=custom_options,
        )

        await client.initialize()

        mock_socket = mock_zmq_context_instance.socket.return_value

        # Check that custom options are set
        for option, value in custom_options.items():
            mock_socket.setsockopt.assert_any_call(option, value)

    @pytest.mark.asyncio
    async def test_initialize_already_initialized(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test that initialize is idempotent."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.REQ,
            address="inproc://test_addr_5559",
            bind=False,
        )

        await client.initialize()
        assert client.is_initialized

        # Initialize again - should not create another socket
        await client.initialize()
        assert client.is_initialized

        # Should only be called once
        mock_zmq_context_instance.socket.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_error_handling(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test error handling during initialization."""
        mock_zmq_context_instance.socket.side_effect = zmq.ZMQError(
            errno=1, msg="Socket creation failed"
        )

        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.REP,
            address="inproc://test_addr_5560",
            bind=True,
        )

        with pytest.raises(
            InitializationError, match="Failed to initialize ZMQ socket"
        ):
            await client.initialize()

        assert not client.is_initialized

    @pytest.mark.asyncio
    async def test_shutdown_basic(self, mock_zmq_context_instance: MagicMock):
        """Test basic shutdown functionality."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.DEALER,
            address="inproc://test_addr_1",
            bind=False,
        )

        await client.initialize()
        assert client.is_initialized
        assert not client.stop_requested

        await client.shutdown()
        assert client.stop_requested

    @pytest.mark.asyncio
    async def test_shutdown_already_stopped(self, mock_zmq_context_instance: MagicMock):
        """Test shutdown when already stopped."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.ROUTER,
            address="inproc://test_addr_2",
            bind=True,
        )

        await client.initialize()
        await client.shutdown()
        assert client.stop_requested

        # Shutdown again - should not raise error
        await client.shutdown()
        assert client.stop_requested

    @pytest.mark.asyncio
    async def test_ensure_initialized_not_initialized(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test _ensure_initialized when not initialized."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.XPUB,
            address="inproc://test_addr_3",
            bind=True,
        )

        # Should initialize automatically
        await client._ensure_initialized()
        assert client.is_initialized

    @pytest.mark.asyncio
    async def test_ensure_initialized_stop_requested(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test _ensure_initialized when stop is requested."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.XSUB,
            address="inproc://test_addr_4",
            bind=False,
        )

        await client.initialize()
        await client.shutdown()

        with pytest.raises(asyncio.CancelledError):
            await client._ensure_initialized()

    @pytest.mark.asyncio
    async def test_socket_property_after_initialize(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test socket property after initialization."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.PAIR,
            address="inproc://test_addr_5",
            bind=True,
        )

        await client.initialize()

        socket = client.socket
        assert socket == mock_zmq_context_instance.socket.return_value

    @pytest.mark.parametrize(
        "socket_type,bind",
        [
            (zmq.PUB, True),
            (zmq.SUB, False),
            (zmq.PUSH, True),
            (zmq.PULL, False),
            (zmq.REQ, False),
            (zmq.REP, True),
            (zmq.DEALER, False),
            (zmq.ROUTER, True),
            (zmq.XPUB, True),
            (zmq.XSUB, False),
        ],
    )
    @pytest.mark.asyncio
    async def test_various_socket_types(
        self, mock_zmq_context_instance: MagicMock, socket_type, bind
    ):
        """Test various socket types and bind configurations."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=socket_type,
            address="inproc://test_addr_6",
            bind=bind,
        )

        await client.initialize()

        mock_zmq_context_instance.socket.assert_called_once_with(socket_type)
        mock_socket = mock_zmq_context_instance.socket.return_value

        if bind:
            mock_socket.bind.assert_called_once()
            mock_socket.connect.assert_not_called()
        else:
            mock_socket.connect.assert_called_once()
            mock_socket.bind.assert_not_called()

    @pytest.mark.asyncio
    async def test_client_id_generation(self, mock_zmq_context_instance: MagicMock):
        """Test client ID generation."""
        client1 = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.PUB,
            address="inproc://test_addr_7",
            bind=True,
        )

        client2 = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.SUB,
            address="inproc://test_addr_8",
            bind=False,
        )

        # Should have different IDs
        assert client1.client_id != client2.client_id
        assert client1.client_id.startswith("pub_client_")
        assert client2.client_id.startswith("sub_client_")

    @pytest.mark.asyncio
    async def test_hooks_support(self, mock_zmq_context_instance: MagicMock):
        """Test that BaseZMQClient supports hooks."""

        # Check that the class is decorated with supports_hooks
        assert hasattr(BaseZMQClient, "_supported_hooks")

        # Check that expected hooks are supported
        supported_hooks = BaseZMQClient._supported_hooks
        assert AIPerfHook.ON_INIT in supported_hooks
        assert AIPerfHook.ON_STOP in supported_hooks
        assert AIPerfHook.ON_CLEANUP in supported_hooks
        assert AIPerfTaskHook.AIPERF_TASK in supported_hooks

    @pytest.mark.asyncio
    async def test_lifecycle_integration(self, mock_zmq_context_instance: MagicMock):
        """Test complete lifecycle integration."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.PUB,
            address="inproc://test_addr_9",
            bind=True,
            socket_ops={zmq.LINGER: 0},
        )

        # Initial state
        assert not client.is_initialized
        assert not client.stop_requested

        # Initialize
        await client.initialize()
        assert client.is_initialized
        assert not client.stop_requested

        # Can access socket
        socket = client.socket
        assert socket is not None

        # Shutdown
        await client.shutdown()
        assert client.is_initialized  # Still initialized
        assert client.stop_requested  # But shutdown requested

        # Socket should still be accessible
        socket = client.socket
        assert socket is not None

    @pytest.mark.asyncio
    async def test_multiple_clients_same_context(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test multiple clients sharing the same context."""
        client1 = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.PUB,
            address="inproc://test_addr_10",
            bind=True,
        )

        client2 = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.SUB,
            address="inproc://test_addr_11",
            bind=False,
        )

        await client1.initialize()
        await client2.initialize()

        assert client1.is_initialized
        assert client2.is_initialized

        # Should have called socket creation twice
        assert mock_zmq_context_instance.socket.call_count == 2

        await client1.shutdown()
        await client2.shutdown()

        assert client1.stop_requested
        assert client2.stop_requested

    @pytest.mark.asyncio
    async def test_error_scenarios(self, mock_zmq_context_instance: MagicMock):
        """Test various error scenarios."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.PUSH,
            address="inproc://test_addr_12",
            bind=True,
        )

        # Error during socket creation
        mock_zmq_context_instance.socket.side_effect = zmq.ZMQError(
            errno=1, msg="Context terminated"
        )

        with pytest.raises(InitializationError):
            await client.initialize()

        assert not client.is_initialized

    @pytest.mark.asyncio
    async def test_concurrent_initialization(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test concurrent initialization calls."""
        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.PULL,
            address="inproc://test_addr_13",
            bind=False,
        )

        # Try to initialize concurrently
        tasks = [client.initialize() for _ in range(5)]
        await asyncio.gather(*tasks)

        assert client.is_initialized
        # Should only create one socket despite multiple calls
        mock_zmq_context_instance.socket.assert_called_once()

    @pytest.mark.asyncio
    async def test_address_types(self, mock_zmq_context_instance: MagicMock):
        """Test different address types."""
        addresses = [
            "inproc://test_addr_14",
            "inproc://test_addr_15",
            "inproc://test_ipc_base",
            "inproc://test",
        ]

        for address in addresses:
            client = BaseZMQClient(
                context=mock_zmq_context_instance,
                socket_type=zmq.PAIR,
                address=address,
                bind=True,
            )

            await client.initialize()
            assert client.is_initialized
            assert client.address == address

            await client.shutdown()

    @pytest.mark.asyncio
    async def test_socket_options_validation(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test socket options validation."""
        valid_options = {
            zmq.RCVTIMEO: 1000,
            zmq.SNDTIMEO: 2000,
            zmq.LINGER: 0,
            zmq.TCP_KEEPALIVE: 1,
        }

        client = BaseZMQClient(
            context=mock_zmq_context_instance,
            socket_type=zmq.REQ,
            address="inproc://test_addr_16",
            bind=False,
            socket_ops=valid_options,
        )

        await client.initialize()

        mock_socket = mock_zmq_context_instance.socket.return_value
        for option, value in valid_options.items():
            mock_socket.setsockopt.assert_any_call(option, value)

    @pytest.mark.asyncio
    async def test_context_sharing(self, mock_zmq_context_instance: MagicMock):
        """Test that multiple clients can share the same context."""
        clients = []

        for _ in range(3):
            client = BaseZMQClient(
                context=mock_zmq_context_instance,
                socket_type=zmq.PUB,
                address="inproc://test_addr_17",
                bind=True,
            )
            clients.append(client)

        # Initialize all clients
        for client in clients:
            await client.initialize()
            assert client.is_initialized
            assert client.context == mock_zmq_context_instance

        # Shutdown all clients
        for client in clients:
            await client.shutdown()
            assert client.stop_requested
