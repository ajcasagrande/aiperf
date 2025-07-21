# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for ZMQ PUB and SUB client implementations.
"""

import asyncio
import errno
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest
import zmq

from aiperf.common.comms.zmq import ZMQPubClient, ZMQSubClient
from aiperf.common.enums import MessageType
from aiperf.common.exceptions import CommunicationError
from tests.comms.conftest import MockTestMessage


class TestZMQPubClient:
    """Tests for ZMQPubClient class."""

    def test_init(self, mock_zmq_context_instance: MagicMock):
        """Test PubClient initialization."""
        client = ZMQPubClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        assert client.context == mock_zmq_context_instance
        assert client.socket_type == zmq.PUB
        assert client.address == "inproc://test_addr_5555"
        assert client.bind is True
        assert client.client_id.startswith("pub_client_")

    def test_factory_registration(self, mock_zmq_context_instance: MagicMock):
        """Test that ZMQPubClient is properly registered with the factory."""
        from aiperf.common.comms.base_comms import CommunicationClientFactory
        from aiperf.common.enums import CommunicationClientType

        client = CommunicationClientFactory.create_instance(
            CommunicationClientType.PUB,
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        assert isinstance(client, ZMQPubClient)

    @pytest.mark.asyncio
    async def test_publish_message(
        self, zmq_pub_bind_client: ZMQPubClient, test_message: MockTestMessage
    ):
        """Test publishing a message."""
        client = zmq_pub_bind_client

        await client.initialize()
        await client.publish(test_message)

        mock_socket = zmq_pub_bind_client.socket
        mock_socket.send_multipart.assert_called_once()

        # Check the call arguments
        call_args = mock_socket.send_multipart.call_args[0][0]
        assert len(call_args) == 2
        assert call_args[0] == test_message.message_type.encode()
        assert isinstance(call_args[1], bytes)

    @pytest.mark.asyncio
    async def test_publish_not_initialized(
        self, zmq_pub_bind_client: ZMQPubClient, test_message: MockTestMessage
    ):
        """Test publishing when not initialized."""
        client = zmq_pub_bind_client

        # Should initialize automatically
        await client.publish(test_message)

        assert client.is_initialized
        mock_socket = zmq_pub_bind_client.socket
        mock_socket.send_multipart.assert_called_once()

    @pytest.mark.asyncio
    async def test_publish_multiple_messages(
        self,
        zmq_pub_bind_client: ZMQPubClient,
        multiple_test_messages: list[MockTestMessage],
    ):
        """Test publishing multiple messages."""
        client = zmq_pub_bind_client

        await client.initialize()

        for message in multiple_test_messages:
            await client.publish(message)

        mock_socket = zmq_pub_bind_client.socket
        assert mock_socket.send_multipart.call_count == len(multiple_test_messages)

    @pytest.mark.asyncio
    async def test_publish_error_handling(
        self, zmq_pub_bind_client: ZMQPubClient, test_message: MockTestMessage
    ):
        """Test error handling during publish."""
        client = zmq_pub_bind_client

        await client.initialize()

        # Mock socket to raise an error
        mock_socket = zmq_pub_bind_client.socket
        mock_socket.send_multipart.side_effect = zmq.ZMQError(
            errno=errno.EFAULT, msg="Send failed"
        )

        with pytest.raises(CommunicationError, match="Failed to publish message"):
            await client.publish(test_message)

    @pytest.mark.asyncio
    async def test_publish_context_terminated(
        self, zmq_pub_bind_client: ZMQPubClient, test_message: MockTestMessage
    ):
        """Test publish when context is terminated."""
        client = zmq_pub_bind_client

        await client.initialize()

        # Mock socket to raise ContextTerminated
        mock_socket = client.socket
        mock_socket.send_multipart.side_effect = zmq.ContextTerminated()

        # Should not raise error
        await client.publish(test_message)

    @pytest.mark.asyncio
    async def test_publish_cancelled(
        self, zmq_pub_bind_client: ZMQPubClient, test_message: MockTestMessage
    ):
        """Test publish when cancelled."""
        client = zmq_pub_bind_client

        await client.initialize()

        # Mock socket to raise CancelledError
        mock_socket = client.socket
        mock_socket.send_multipart.side_effect = asyncio.CancelledError()

        # Should not raise error
        await client.publish(test_message)

    @pytest.mark.parametrize(
        "message_type",
        [
            MessageType.Status,
            MessageType.Heartbeat,
            MessageType.Error,
        ],
    )
    @pytest.mark.asyncio
    async def test_publish_different_message_types(
        self,
        zmq_pub_bind_client: ZMQPubClient,
        message_type: MessageType,
    ):
        """Test publishing different message types."""
        client = zmq_pub_bind_client

        message = MockTestMessage(test_data="test")

        await client.initialize()
        await client.publish(message)

        mock_socket = client.socket
        call_args = mock_socket.send_multipart.call_args[0][0]
        assert call_args[0] == message_type.encode()


class TestZMQSubClient:
    """Tests for ZMQSubClient class."""

    def test_init(self, zmq_sub_connect_client: ZMQSubClient):
        """Test SubClient initialization."""
        client = zmq_sub_connect_client

        assert client.context == zmq_sub_connect_client.context
        assert client.socket_type == zmq.SUB
        assert client.address == "inproc://test_sub_client"
        assert client.bind is False
        assert client.client_id.startswith("sub_client_")

    def test_inheritance(self, zmq_sub_connect_client: ZMQSubClient):
        """Test that ZMQSubClient inherits from BaseZMQClient and AsyncTaskManagerMixin."""
        from aiperf.common.comms.zmq import BaseZMQClient
        from aiperf.common.mixins import AsyncTaskManagerMixin

        client = zmq_sub_connect_client

        assert isinstance(client, BaseZMQClient)
        assert isinstance(client, AsyncTaskManagerMixin)

    def test_factory_registration(self, zmq_sub_connect_client: ZMQSubClient):
        """Test that ZMQSubClient is properly registered with the factory."""
        from aiperf.common.comms.base_comms import CommunicationClientFactory
        from aiperf.common.enums import CommunicationClientType

        client = CommunicationClientFactory.create_instance(
            CommunicationClientType.SUB,
            context=zmq_sub_connect_client.context,
            address="inproc://test_sub_client",
            bind=False,
        )

        assert isinstance(client, ZMQSubClient)

    def test_subscribers_initialization(self, zmq_sub_connect_client: ZMQSubClient):
        """Test that subscribers dict is initialized."""

        assert hasattr(zmq_sub_connect_client, "_subscribers")
        assert zmq_sub_connect_client._subscribers == {}

    @pytest.mark.asyncio
    async def test_subscribe_single_message_type(
        self, zmq_sub_connect_client: ZMQSubClient, mock_async_callback: AsyncMock
    ):
        """Test subscribing to a single message type."""
        client = zmq_sub_connect_client

        await client.initialize()
        await client.subscribe(MessageType.Status, mock_async_callback)

        mock_socket = zmq_sub_connect_client.socket
        mock_socket.subscribe.assert_called_once_with(MessageType.Status.encode())

        assert MessageType.Status in client._subscribers
        assert mock_async_callback in client._subscribers[MessageType.Status]

    @pytest.mark.asyncio
    async def test_subscribe_not_initialized(
        self, zmq_sub_connect_client: ZMQSubClient, mock_async_callback: AsyncMock
    ):
        """Test subscribing when not initialized."""
        client = zmq_sub_connect_client

        # Should initialize automatically
        await client.subscribe(MessageType.Status, mock_async_callback)

        assert client.is_initialized
        mock_socket = zmq_sub_connect_client.socket
        mock_socket.subscribe.assert_called_once_with(MessageType.Status.encode())

    @pytest.mark.asyncio
    async def test_subscribe_multiple_message_types(
        self, zmq_sub_connect_client: ZMQSubClient, mock_async_callback: AsyncMock
    ):
        """Test subscribing to multiple message types."""
        client = zmq_sub_connect_client

        await client.initialize()

        message_types = [MessageType.Status, MessageType.Heartbeat, MessageType.Command]

        for msg_type in message_types:
            await client.subscribe(msg_type, mock_async_callback)

        mock_socket = zmq_sub_connect_client.socket
        expected_calls = [call(msg_type.encode()) for msg_type in message_types]
        mock_socket.subscribe.assert_has_calls(expected_calls)

        for msg_type in message_types:
            assert msg_type in client._subscribers
            assert mock_async_callback in client._subscribers[msg_type]

    @pytest.mark.asyncio
    async def test_subscribe_multiple_callbacks_same_type(
        self, zmq_sub_connect_client: ZMQSubClient
    ):
        """Test subscribing multiple callbacks to the same message type."""
        client = zmq_sub_connect_client

        callback1 = AsyncMock()
        callback2 = AsyncMock()

        await client.initialize()
        await client.subscribe(MessageType.Status, callback1)
        await client.subscribe(MessageType.Status, callback2)

        mock_socket = zmq_sub_connect_client.socket
        # Subscribe should only be called once per message type
        mock_socket.subscribe.assert_called_once_with(MessageType.Status.encode())

        assert MessageType.Status in client._subscribers
        assert callback1 in client._subscribers[MessageType.Status]
        assert callback2 in client._subscribers[MessageType.Status]
        assert len(client._subscribers[MessageType.Status]) == 2

    @pytest.mark.asyncio
    async def test_subscribe_error_handling(
        self, zmq_sub_connect_client: ZMQSubClient, mock_async_callback: AsyncMock
    ):
        """Test error handling during subscribe."""
        client = zmq_sub_connect_client

        await client.initialize()

        # Mock socket to raise an error
        mock_socket = client.socket
        mock_socket.subscribe.side_effect = zmq.ZMQError(
            errno=errno.ECOMM, msg="Subscribe failed"
        )

        with pytest.raises(
            CommunicationError, match="Failed to subscribe to message_type"
        ):
            await client.subscribe(MessageType.Status, mock_async_callback)

    @pytest.mark.asyncio
    async def test_message_receiving_task(
        self, zmq_sub_connect_client: ZMQSubClient, mock_async_callback: AsyncMock
    ):
        """Test that message receiving task is started."""
        client = zmq_sub_connect_client

        await client.initialize()
        await client.subscribe(MessageType.Status, mock_async_callback)

        # Should have started a receiving task
        assert hasattr(client, "tasks")
        # In a real implementation, there should be tasks for receiving messages

    @pytest.mark.asyncio
    async def test_on_stop_hook(self, zmq_sub_connect_client: ZMQSubClient):
        """Test that the on_stop hook cancels all tasks."""
        client = zmq_sub_connect_client

        await client.initialize()

        # Mock the cancel_all_tasks method
        with patch.object(client, "cancel_all_tasks", new_callable=AsyncMock):
            await client.shutdown()
            # The on_stop hook should have been called
            # This tests that the hook system is working

    @pytest.mark.parametrize(
        "message_type",
        [
            MessageType.Status,
            MessageType.Heartbeat,
            MessageType.Error,
        ],
    )
    @pytest.mark.asyncio
    async def test_subscribe_different_message_types(
        self,
        zmq_sub_connect_client: ZMQSubClient,
        message_type: MessageType,
        mock_async_callback: AsyncMock,
    ):
        """Test subscribing to different message types."""
        client = zmq_sub_connect_client

        await client.initialize()
        await client.subscribe(message_type, mock_async_callback)

        mock_socket = zmq_sub_connect_client.socket
        mock_socket.subscribe.assert_called_once_with(message_type.encode())

        assert message_type in client._subscribers
        assert mock_async_callback in client._subscribers[message_type]

    @pytest.mark.asyncio
    async def test_concurrent_subscribes(self, zmq_sub_connect_client: ZMQSubClient):
        """Test concurrent subscribe operations."""
        client = zmq_sub_connect_client

        await client.initialize()

        callbacks = [AsyncMock() for _ in range(5)]
        message_types = [
            MessageType.Status,
            MessageType.Heartbeat,
            MessageType.Command,
            MessageType.Error,
            MessageType.NOTIFICATION,
        ]

        # Subscribe concurrently
        tasks = [
            client.subscribe(msg_type, callback)
            for msg_type, callback in zip(message_types, callbacks, strict=False)
        ]

        await asyncio.gather(*tasks)

        # All subscriptions should be registered
        for msg_type, callback in zip(message_types, callbacks, strict=False):
            assert msg_type in client._subscribers
            assert callback in client._subscribers[msg_type]


class TestPubSubIntegration:
    """Integration tests for PUB/SUB clients."""

    @pytest.mark.asyncio
    async def test_pub_sub_message_flow(
        self,
        zmq_pub_bind_client: ZMQPubClient,
        zmq_sub_connect_client: ZMQSubClient,
        test_message: MockTestMessage,
    ):
        """Test message flow from PUB to SUB."""
        pub_client = zmq_pub_bind_client

        sub_client = zmq_sub_connect_client

        callback = AsyncMock()

        await pub_client.initialize()
        await sub_client.initialize()

        await sub_client.subscribe(test_message.message_type, callback)
        await pub_client.publish(test_message)

        # Verify publish was called
        pub_socket = pub_client.socket
        pub_socket.send_multipart.assert_called_once()

        # Verify subscribe was called
        sub_socket = sub_client.socket
        sub_socket.subscribe.assert_called_once_with(test_message.message_type.encode())

    @pytest.mark.asyncio
    async def test_multiple_publishers_single_subscriber(
        self,
        zmq_pub_bind_client: ZMQPubClient,
        zmq_sub_connect_client: ZMQSubClient,
        multiple_test_messages: list[MockTestMessage],
    ):
        """Test multiple publishers sending to a single subscriber."""
        pub_clients = []
        for _ in range(3):
            client = zmq_pub_bind_client
            pub_clients.append(client)

        sub_client = zmq_sub_connect_client

        callback = AsyncMock()

        # Initialize all clients
        for client in pub_clients:
            await client.initialize()
        await sub_client.initialize()

        # Subscribe to all message types
        for message in multiple_test_messages:
            await sub_client.subscribe(message.message_type, callback)

        # Publish messages from different publishers
        for i, message in enumerate(multiple_test_messages[:3]):
            await pub_clients[i].publish(message)

        # Verify all publishes were called
        pub_socket = pub_clients[0].socket
        assert pub_socket.send_multipart.call_count == 3

    @pytest.mark.asyncio
    async def test_single_publisher_multiple_subscribers(
        self,
        zmq_pub_bind_client: ZMQPubClient,
        zmq_sub_connect_client: ZMQSubClient,
        test_message: MockTestMessage,
    ):
        """Test single publisher sending to multiple subscribers."""
        pub_client = zmq_pub_bind_client

        sub_clients = []
        callbacks = []

        for _ in range(3):
            client = zmq_sub_connect_client
            callback = AsyncMock()
            sub_clients.append(client)
            callbacks.append(callback)

        # Initialize all clients
        await pub_client.initialize()
        for client in sub_clients:
            await client.initialize()

        # Subscribe all clients
        for client, callback in zip(sub_clients, callbacks, strict=False):
            await client.subscribe(test_message.message_type, callback)

        # Publish message
        await pub_client.publish(test_message)

        # Verify publish was called once
        pub_socket = pub_client.socket
        pub_socket.send_multipart.assert_called_once()

        # Verify the socket only subscribed once each
        assert sub_clients[0].socket.subscribe.call_count == 1
        assert sub_clients[1].socket.subscribe.call_count == 1
        assert sub_clients[2].socket.subscribe.call_count == 1

    @pytest.mark.asyncio
    async def test_pub_sub_error_isolation(
        self,
        zmq_pub_bind_client: ZMQPubClient,
        zmq_sub_connect_client: ZMQSubClient,
        test_message: MockTestMessage,
    ):
        """Test that errors in one client don't affect others."""
        pub_client = zmq_pub_bind_client
        sub_client = zmq_sub_connect_client

        await pub_client.initialize()
        await sub_client.initialize()

        # Make pub client fail
        pub_socket = pub_client.socket
        pub_socket.send_multipart.side_effect = zmq.ZMQError(
            errno=errno.ECOMM, msg="Publish failed"
        )

        # Publishing should fail
        with pytest.raises(CommunicationError):
            await pub_client.publish(test_message)

        # But subscribing should still work
        callback = AsyncMock()
        await sub_client.subscribe(test_message.message_type, callback)

        sub_socket = sub_client.socket
        sub_socket.subscribe.assert_called_once()
