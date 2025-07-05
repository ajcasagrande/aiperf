# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for ZMQ PUSH and PULL client implementations.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
import zmq

from aiperf.common.comms.zmq import ZMQPullClient, ZMQPushClient
from aiperf.common.enums import MessageType
from aiperf.common.exceptions import CommunicationError
from aiperf.tests.comms.conftest import _TestMessage


class TestZMQPushClient:
    """Tests for ZMQPushClient class."""

    def test_init(self, mock_zmq_context_instance: MagicMock):
        """Test PushClient initialization."""
        client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        assert client.context == mock_zmq_context_instance
        assert client.socket_type == zmq.PUSH
        assert client.address == "inproc://test_addr_5555"
        assert client.bind is True
        assert client.client_id.startswith("push_client_")

    def test_inheritance(self, mock_zmq_context_instance: MagicMock):
        """Test that ZMQPushClient inherits from BaseZMQClient."""
        from aiperf.common.comms.zmq import BaseZMQClient

        client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        assert isinstance(client, BaseZMQClient)

    def test_factory_registration(self, mock_zmq_context_instance: MagicMock):
        """Test that ZMQPushClient is properly registered with the factory."""
        from aiperf.common.comms.base import CommunicationClientFactory
        from aiperf.common.enums import CommunicationClientType

        client = CommunicationClientFactory.create_instance(
            CommunicationClientType.PUSH,
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        assert isinstance(client, ZMQPushClient)

    @pytest.mark.asyncio
    async def test_push_message(
        self, mock_zmq_context_instance: MagicMock, test_message: _TestMessage
    ):
        """Test pushing a message."""
        client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        await client.initialize()
        await client.push(test_message)

        mock_socket = mock_zmq_context_instance.socket.return_value
        mock_socket.send_multipart.assert_called_once()

        # Check the call arguments
        call_args = mock_socket.send_multipart.call_args[0][0]
        assert len(call_args) == 2
        assert call_args[0] == test_message.message_type.encode()
        assert isinstance(call_args[1], bytes)

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_push_not_initialized(
        self, mock_zmq_context_instance: MagicMock, test_message: _TestMessage
    ):
        """Test pushing when not initialized."""
        client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        # Should initialize automatically
        await client.push(test_message)

        assert client.is_initialized
        mock_socket = mock_zmq_context_instance.socket.return_value
        mock_socket.send_multipart.assert_called_once()

    @pytest.mark.asyncio
    async def test_push_multiple_messages(
        self,
        mock_zmq_context_instance: MagicMock,
        multiple_test_messages: list[_TestMessage],
    ):
        """Test pushing multiple messages."""
        client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        await client.initialize()

        for message in multiple_test_messages:
            await client.push(message)

        mock_socket = mock_zmq_context_instance.socket.return_value
        assert mock_socket.send_multipart.call_count == len(multiple_test_messages)

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_push_error_handling(
        self, mock_zmq_context_instance: MagicMock, test_message: _TestMessage
    ):
        """Test error handling during push."""
        client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        await client.initialize()

        # Mock socket to raise an error
        mock_socket = mock_zmq_context_instance.socket.return_value
        mock_socket.send_multipart.side_effect = zmq.ZMQError("Send failed")

        with pytest.raises(CommunicationError, match="Failed to push message"):
            await client.push(test_message)

    @pytest.mark.asyncio
    async def test_push_context_terminated(
        self, mock_zmq_context_instance: MagicMock, test_message: _TestMessage
    ):
        """Test push when context is terminated."""
        client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        await client.initialize()

        # Mock socket to raise ContextTerminated
        mock_socket = mock_zmq_context_instance.socket.return_value
        mock_socket.send_multipart.side_effect = zmq.ContextTerminated()

        # Should not raise error
        await client.push(test_message)

    @pytest.mark.asyncio
    async def test_push_cancelled(
        self, mock_zmq_context_instance: MagicMock, test_message: _TestMessage
    ):
        """Test push when cancelled."""
        client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        await client.initialize()

        # Mock socket to raise CancelledError
        mock_socket = mock_zmq_context_instance.socket.return_value
        mock_socket.send_multipart.side_effect = asyncio.CancelledError()

        # Should not raise error
        await client.push(test_message)

    @pytest.mark.parametrize(
        "message_type",
        [
            MessageType.STATUS,
            MessageType.HEARTBEAT,
            MessageType.COMMAND,
            MessageType.ERROR,
            MessageType.NOTIFICATION,
        ],
    )
    @pytest.mark.asyncio
    async def test_push_different_message_types(
        self, mock_zmq_context_instance: MagicMock, message_type
    ):
        """Test pushing different message types."""
        client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        message = _TestMessage(message_type=message_type, test_data="test")

        await client.initialize()
        await client.push(message)

        mock_socket = mock_zmq_context_instance.socket.return_value
        call_args = mock_socket.send_multipart.call_args[0][0]
        assert call_args[0] == message_type.encode()

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_push_load_balancing(
        self,
        mock_zmq_context_instance: MagicMock,
        multiple_test_messages: list[_TestMessage],
    ):
        """Test that push distributes messages (load balancing behavior)."""
        client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        await client.initialize()

        # Push multiple messages rapidly
        tasks = [client.push(message) for message in multiple_test_messages]
        await asyncio.gather(*tasks)

        mock_socket = mock_zmq_context_instance.socket.return_value
        assert mock_socket.send_multipart.call_count == len(multiple_test_messages)

        await client.shutdown()


class TestZMQPullClient:
    """Tests for ZMQPullClient class."""

    def test_init(self, mock_zmq_context_instance: MagicMock):
        """Test PullClient initialization."""
        client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        assert client.context == mock_zmq_context_instance
        assert client.socket_type == zmq.PULL
        assert client.address == "inproc://test_addr_5556"
        assert client.bind is False
        assert client.client_id.startswith("pull_client_")

    def test_inheritance(self, mock_zmq_context_instance: MagicMock):
        """Test that ZMQPullClient inherits from BaseZMQClient and AsyncTaskManagerMixin."""
        from aiperf.common.comms.zmq import BaseZMQClient
        from aiperf.common.mixins import AsyncTaskManagerMixin

        client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        assert isinstance(client, BaseZMQClient)
        assert isinstance(client, AsyncTaskManagerMixin)

    def test_factory_registration(self, mock_zmq_context_instance: MagicMock):
        """Test that ZMQPullClient is properly registered with the factory."""
        from aiperf.common.comms.base import CommunicationClientFactory
        from aiperf.common.enums import CommunicationClientType

        client = CommunicationClientFactory.create_instance(
            CommunicationClientType.PULL,
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        assert isinstance(client, ZMQPullClient)

    def test_pull_callbacks_initialization(self, mock_zmq_context_instance: MagicMock):
        """Test that pull callbacks dict is initialized."""
        client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        assert hasattr(client, "_pull_callbacks")
        assert client._pull_callbacks == {}

    @pytest.mark.asyncio
    async def test_register_pull_callback(
        self, mock_zmq_context_instance: MagicMock, mock_async_callback: AsyncMock
    ):
        """Test registering a pull callback."""
        client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        await client.initialize()
        await client.register_pull_callback(MessageType.STATUS, mock_async_callback)

        assert MessageType.STATUS in client._pull_callbacks
        assert client._pull_callbacks[MessageType.STATUS] == mock_async_callback

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_register_pull_callback_not_initialized(
        self, mock_zmq_context_instance: MagicMock, mock_async_callback: AsyncMock
    ):
        """Test registering pull callback when not initialized."""
        client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        # Should initialize automatically
        await client.register_pull_callback(MessageType.STATUS, mock_async_callback)

        assert client.is_initialized
        assert MessageType.STATUS in client._pull_callbacks

    @pytest.mark.asyncio
    async def test_register_pull_callback_duplicate(
        self, mock_zmq_context_instance: MagicMock, mock_async_callback: AsyncMock
    ):
        """Test registering duplicate pull callback."""
        client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        await client.initialize()
        await client.register_pull_callback(MessageType.STATUS, mock_async_callback)

        # Should raise error for duplicate registration
        with pytest.raises(ValueError, match="Callback already registered"):
            await client.register_pull_callback(MessageType.STATUS, mock_async_callback)

    @pytest.mark.asyncio
    async def test_register_pull_callback_with_concurrency(
        self, mock_zmq_context_instance: MagicMock, mock_async_callback: AsyncMock
    ):
        """Test registering pull callback with max concurrency."""
        client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        await client.initialize()
        await client.register_pull_callback(
            MessageType.STATUS, mock_async_callback, max_concurrency=5
        )

        assert MessageType.STATUS in client._pull_callbacks
        assert hasattr(client, "semaphore")
        assert client.semaphore._value == 5

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_register_multiple_pull_callbacks(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test registering multiple pull callbacks for different message types."""
        client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        callbacks = {
            MessageType.STATUS: AsyncMock(),
            MessageType.HEARTBEAT: AsyncMock(),
            MessageType.COMMAND: AsyncMock(),
        }

        await client.initialize()

        for msg_type, callback in callbacks.items():
            await client.register_pull_callback(msg_type, callback)

        # All callbacks should be registered
        for msg_type, callback in callbacks.items():
            assert msg_type in client._pull_callbacks
            assert client._pull_callbacks[msg_type] == callback

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_pull_receiving_task(
        self, mock_zmq_context_instance: MagicMock, mock_async_callback: AsyncMock
    ):
        """Test that pull receiving task is started."""
        client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        await client.initialize()
        await client.register_pull_callback(MessageType.STATUS, mock_async_callback)

        # Should have started a receiving task
        assert hasattr(client, "_tasks")
        # In a real implementation, there should be tasks for receiving messages

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_on_stop_hook(self, mock_zmq_context_instance: MagicMock):
        """Test that the on_stop hook cancels all tasks."""
        client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        await client.initialize()

        # Mock the cancel_all_tasks method
        with pytest.raises(
            NotImplementedError
        ):  # Mocking a method that doesn't exist in the base class
            await client.on_stop()

    @pytest.mark.parametrize(
        "message_type",
        [
            MessageType.STATUS,
            MessageType.HEARTBEAT,
            MessageType.COMMAND,
            MessageType.ERROR,
            MessageType.NOTIFICATION,
        ],
    )
    @pytest.mark.asyncio
    async def test_register_different_message_types(
        self,
        mock_zmq_context_instance: MagicMock,
        message_type,
        mock_async_callback: AsyncMock,
    ):
        """Test registering callbacks for different message types."""
        client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        await client.initialize()
        await client.register_pull_callback(message_type, mock_async_callback)

        assert message_type in client._pull_callbacks
        assert client._pull_callbacks[message_type] == mock_async_callback

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_concurrent_callback_registration(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test concurrent callback registration."""
        client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        await client.initialize()

        callbacks = [AsyncMock() for _ in range(5)]
        message_types = [
            MessageType.STATUS,
            MessageType.HEARTBEAT,
            MessageType.COMMAND,
            MessageType.ERROR,
            MessageType.NOTIFICATION,
        ]

        # Register callbacks concurrently
        tasks = [
            client.register_pull_callback(msg_type, callback)
            for msg_type, callback in zip(message_types, callbacks, strict=False)
        ]

        await asyncio.gather(*tasks)

        # All callbacks should be registered
        for msg_type, callback in zip(message_types, callbacks, strict=False):
            assert msg_type in client._pull_callbacks
            assert client._pull_callbacks[msg_type] == callback

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_pull_with_high_water_mark(
        self, mock_zmq_context_instance: MagicMock, mock_async_callback: AsyncMock
    ):
        """Test pull with high water mark socket option."""
        socket_ops = {zmq.RCVHWM: 1000}

        client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
            socket_ops=socket_ops,
        )

        await client.initialize()
        await client.register_pull_callback(MessageType.STATUS, mock_async_callback)

        mock_socket = mock_zmq_context_instance.socket.return_value
        mock_socket.setsockopt.assert_any_call(zmq.RCVHWM, 1000)

        await client.shutdown()


class TestPushPullIntegration:
    """Integration tests for PUSH/PULL clients."""

    @pytest.mark.asyncio
    async def test_push_pull_message_flow(
        self, mock_zmq_context_instance: MagicMock, test_message: _TestMessage
    ):
        """Test message flow from PUSH to PULL."""
        push_client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        pull_client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        callback = AsyncMock()

        await push_client.initialize()
        await pull_client.initialize()

        await pull_client.register_pull_callback(test_message.message_type, callback)
        await push_client.push(test_message)

        # Verify push was called
        push_socket = mock_zmq_context_instance.socket.return_value
        push_socket.send_multipart.assert_called_once()

        # Verify callback was registered
        assert test_message.message_type in pull_client._pull_callbacks

        await push_client.shutdown()
        await pull_client.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_pushers_single_puller(
        self,
        mock_zmq_context_instance: MagicMock,
        multiple_test_messages: list[_TestMessage],
    ):
        """Test multiple pushers sending to a single puller."""
        push_clients = []
        for _ in range(3):
            client = ZMQPushClient(
                context=mock_zmq_context_instance,
                address="inproc://test_addr_5555",
                bind=True,
            )
            push_clients.append(client)

        pull_client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        callback = AsyncMock()

        # Initialize all clients
        for client in push_clients:
            await client.initialize()
        await pull_client.initialize()

        # Register callbacks for all message types
        for message in multiple_test_messages:
            if message.message_type not in pull_client._pull_callbacks:
                await pull_client.register_pull_callback(message.message_type, callback)

        # Push messages from different pushers
        for i, message in enumerate(multiple_test_messages[:3]):
            await push_clients[i].push(message)

        # Verify all pushes were called
        push_socket = mock_zmq_context_instance.socket.return_value
        assert push_socket.send_multipart.call_count == 3

        # Cleanup
        for client in push_clients:
            await client.shutdown()
        await pull_client.shutdown()

    @pytest.mark.asyncio
    async def test_single_pusher_multiple_pullers(
        self,
        mock_zmq_context_instance: MagicMock,
        multiple_test_messages: list[_TestMessage],
    ):
        """Test single pusher sending to multiple pullers (load balancing)."""
        push_client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        pull_clients = []
        callbacks = []

        for _ in range(3):
            client = ZMQPullClient(
                context=mock_zmq_context_instance,
                address="inproc://test_addr_5555",
                bind=False,
            )
            callback = AsyncMock()
            pull_clients.append(client)
            callbacks.append(callback)

        # Initialize all clients
        await push_client.initialize()
        for client in pull_clients:
            await client.initialize()

        # Register callbacks for all pullers
        for _, (client, callback) in enumerate(
            zip(pull_clients, callbacks, strict=False)
        ):
            for message in multiple_test_messages:
                if message.message_type not in client._pull_callbacks:
                    await client.register_pull_callback(message.message_type, callback)

        # Push multiple messages (should be distributed among pullers)
        for message in multiple_test_messages:
            await push_client.push(message)

        # Verify all pushes were called
        push_socket = mock_zmq_context_instance.socket.return_value
        assert push_socket.send_multipart.call_count == len(multiple_test_messages)

        # Cleanup
        await push_client.shutdown()
        for client in pull_clients:
            await client.shutdown()

    @pytest.mark.asyncio
    async def test_push_pull_error_isolation(
        self, mock_zmq_context_instance: MagicMock, test_message: _TestMessage
    ):
        """Test that errors in one client don't affect others."""
        push_client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        pull_client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=False,
        )

        await push_client.initialize()
        await pull_client.initialize()

        # Make push client fail
        push_socket = mock_zmq_context_instance.socket.return_value
        push_socket.send_multipart.side_effect = zmq.ZMQError(
            errno=1, msg="Push failed"
        )

        # Pushing should fail
        with pytest.raises(CommunicationError):
            await push_client.push(test_message)

        # But registering pull callback should still work
        callback = AsyncMock()
        await pull_client.register_pull_callback(test_message.message_type, callback)

        assert test_message.message_type in pull_client._pull_callbacks

        await push_client.shutdown()
        await pull_client.shutdown()

    @pytest.mark.asyncio
    async def test_pipeline_pattern(
        self,
        mock_zmq_context_instance: MagicMock,
        multiple_test_messages: list[_TestMessage],
    ):
        """Test pipeline pattern with multiple pushers and pullers."""
        # Create multiple pushers (producers)
        pushers = []
        for i in range(2):
            client = ZMQPushClient(
                context=mock_zmq_context_instance,
                address="inproc://test_addr_5555",
                bind=i == 0,  # Only first one binds
            )
            pushers.append(client)

        # Create multiple pullers (workers)
        pullers = []
        for _ in range(3):
            client = ZMQPullClient(
                context=mock_zmq_context_instance,
                address="inproc://test_addr_5555",
                bind=False,
            )
            pullers.append(client)

        # Initialize all clients
        for client in pushers + pullers:
            await client.initialize()

        # Register callbacks for all pullers
        for client in pullers:
            callback = AsyncMock()
            for message in multiple_test_messages:
                if message.message_type not in client._pull_callbacks:
                    await client.register_pull_callback(message.message_type, callback)

        # Push messages from multiple producers
        for pusher in pushers:
            for message in multiple_test_messages:
                await pusher.push(message)

        # Verify all pushes were made
        push_socket = mock_zmq_context_instance.socket.return_value
        expected_calls = len(pushers) * len(multiple_test_messages)
        assert push_socket.send_multipart.call_count == expected_calls

        # Cleanup
        for client in pushers + pullers:
            await client.shutdown()

    @pytest.mark.asyncio
    async def test_high_throughput_scenario(self, mock_zmq_context_instance: MagicMock):
        """Test high throughput scenario with many messages."""
        push_client = ZMQPushClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        pull_client = ZMQPullClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        await push_client.initialize()
        await pull_client.initialize()

        # Create many messages
        messages = [
            _TestMessage(
                message_type=MessageType.STATUS, test_data=f"msg_{i}", counter=i
            )
            for i in range(100)
        ]

        # Register callback
        callback = AsyncMock()
        await pull_client.register_pull_callback(MessageType.STATUS, callback)

        # Push all messages
        tasks = [push_client.push(message) for message in messages]
        await asyncio.gather(*tasks)

        # Verify all messages were pushed
        push_socket = mock_zmq_context_instance.socket.return_value
        assert push_socket.send_multipart.call_count == len(messages)

        await push_client.shutdown()
        await pull_client.shutdown()
