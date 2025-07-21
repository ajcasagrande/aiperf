# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for ZMQ REQUEST (DEALER) and REPLY (ROUTER) client implementations.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import zmq

from aiperf.common.comms.zmq import ZMQDealerRequestClient, ZMQRouterReplyClient
from aiperf.common.enums import MessageType
from aiperf.common.exceptions import CommunicationError
from aiperf.common.types import MessageTypeT
from tests.comms.conftest import MockTestMessage


class TestZMQDealerRequestClient:
    """Tests for ZMQDealerRequestClient class."""

    def test_init(self, mock_zmq_context_instance: MagicMock):
        """Test RequestClient initialization."""
        client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        assert client.context == mock_zmq_context_instance
        assert client.socket_type == zmq.DEALER
        assert client.address == "inproc://test_addr_5555"
        assert client.bind is False
        assert client.client_id.startswith("dealer_client_")

    def test_inheritance(self, mock_zmq_context_instance: MagicMock):
        """Test that ZMQDealerRequestClient inherits from BaseZMQClient and AsyncTaskManagerMixin."""
        from aiperf.common.comms.zmq import BaseZMQClient
        from aiperf.common.mixins import AsyncTaskManagerMixin

        client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        assert isinstance(client, BaseZMQClient)
        assert isinstance(client, AsyncTaskManagerMixin)

    def test_factory_registration(self, mock_zmq_context_instance: MagicMock):
        """Test that ZMQDealerRequestClient is properly registered with the factory."""
        from aiperf.common.comms.base_comms import CommunicationClientFactory
        from aiperf.common.enums import CommunicationClientType

        client = CommunicationClientFactory.create_instance(
            CommunicationClientType.REQUEST,
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        assert isinstance(client, ZMQDealerRequestClient)

    def test_pending_requests_initialization(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test that pending requests dict is initialized."""
        client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        assert hasattr(client, "_pending_requests")
        assert client._pending_requests == {}

    @pytest.mark.asyncio
    async def test_request_basic(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test basic request functionality."""
        client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        # Mock the socket to return a response
        mock_socket = mock_zmq_context_instance.socket.return_value
        response_data = test_message.model_dump_json().encode()
        mock_socket.recv_multipart.return_value = [b"request_id", response_data]

        await client.initialize()

        # Mock the _wait_for_response method to return immediately
        with patch.object(
            client, "_wait_for_response", return_value=test_message
        ) as mock_wait:
            result = await client.request(test_message)

            assert result == test_message
            mock_socket.send_multipart.assert_called_once()
            mock_wait.assert_called_once()

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_request_not_initialized(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test request when not initialized."""
        client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        # Mock the _wait_for_response method
        with patch.object(client, "_wait_for_response", return_value=test_message):
            # Should initialize automatically
            result = await client.request(test_message)

            assert client.is_initialized
            assert result == test_message

    @pytest.mark.asyncio
    async def test_request_with_timeout(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test request with custom timeout."""
        client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        await client.initialize()

        with patch.object(
            client, "_wait_for_response", return_value=test_message
        ) as mock_wait:
            result = await client.request(test_message, timeout=5.0)

            assert result == test_message
            # Verify timeout was passed
            mock_wait.assert_called_once()
            args, kwargs = mock_wait.call_args
            assert kwargs.get("timeout") == 5.0 or args[1] == 5.0

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_request_timeout_error(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test request timeout handling."""
        client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        await client.initialize()

        # Mock timeout
        with (
            patch.object(
                client, "_wait_for_response", side_effect=asyncio.TimeoutError()
            ),
            pytest.raises(CommunicationError, match="Request timed out"),
        ):
            await client.request(test_message, timeout=0.1)

    @pytest.mark.asyncio
    async def test_request_async(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test asynchronous request functionality."""
        client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        callback = AsyncMock()

        await client.initialize()

        # Mock response handling
        with patch.object(client, "_handle_async_response"):
            await client.request_async(test_message, callback)

            mock_socket = mock_zmq_context_instance.socket.return_value
            mock_socket.send_multipart.assert_called_once()

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_concurrent_requests(
        self,
        mock_zmq_context_instance: MagicMock,
        multiple_test_messages: list[MockTestMessage],
    ):
        """Test multiple concurrent requests."""
        client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        await client.initialize()

        # Mock responses for each request
        responses = multiple_test_messages[:3]  # Take first 3

        with patch.object(client, "_wait_for_response", side_effect=responses):
            tasks = [client.request(message) for message in responses]
            results = await asyncio.gather(*tasks)

            assert len(results) == len(responses)
            for i, result in enumerate(results):
                assert result == responses[i]

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_request_error_handling(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test error handling during request."""
        client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        await client.initialize()

        # Mock socket to raise an error
        mock_socket = mock_zmq_context_instance.socket.return_value
        mock_socket.send_multipart.side_effect = zmq.ZMQError(
            errno=1, msg="Send failed"
        )

        with pytest.raises(CommunicationError, match="Failed to send request"):
            await client.request(test_message)

    @pytest.mark.asyncio
    async def test_request_context_terminated(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test request when context is terminated."""
        client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        await client.initialize()

        # Mock socket to raise ContextTerminated
        mock_socket = mock_zmq_context_instance.socket.return_value
        mock_socket.send_multipart.side_effect = zmq.ContextTerminated()

        with pytest.raises(CommunicationError):
            await client.request(test_message)

    @pytest.mark.parametrize(
        "message_type",
        [
            MessageType.Status,
            MessageType.Heartbeat,
            MessageType.Error,
        ],
    )
    @pytest.mark.asyncio
    async def test_request_different_message_types(
        self, mock_zmq_context_instance: MagicMock, message_type
    ):
        """Test requesting different message types."""
        client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        message = MockTestMessage(test_data="test")

        await client.initialize()

        with patch.object(client, "_wait_for_response", return_value=message):
            result = await client.request(message)

            assert result == message
            mock_socket = mock_zmq_context_instance.socket.return_value
            mock_socket.send_multipart.assert_called_once()

        await client.shutdown()


class TestZMQRouterReplyClient:
    """Tests for ZMQRouterReplyClient class."""

    def test_init(self, mock_zmq_context_instance: MagicMock):
        """Test ReplyClient initialization."""
        client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        assert client.context == mock_zmq_context_instance
        assert client.socket_type == zmq.ROUTER
        assert client.address == "inproc://test_addr_5556"
        assert client.bind is True
        assert client.client_id.startswith("router_client_")

    def test_inheritance(self, mock_zmq_context_instance: MagicMock):
        """Test that ZMQRouterReplyClient inherits from BaseZMQClient and AsyncTaskManagerMixin."""
        from aiperf.common.comms.zmq import BaseZMQClient
        from aiperf.common.mixins import AsyncTaskManagerMixin

        client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        assert isinstance(client, BaseZMQClient)
        assert isinstance(client, AsyncTaskManagerMixin)

    def test_factory_registration(self, mock_zmq_context_instance: MagicMock):
        """Test that ZMQRouterReplyClient is properly registered with the factory."""
        from aiperf.common.comms.base_comms import CommunicationClientFactory
        from aiperf.common.enums import CommunicationClientType

        client = CommunicationClientFactory.create_instance(
            CommunicationClientType.REPLY,
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        assert isinstance(client, ZMQRouterReplyClient)

    def test_request_handlers_initialization(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test that request handlers dict is initialized."""
        client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        assert hasattr(client, "_request_handlers")
        assert client._request_handlers == {}

    def test_register_request_handler(
        self, mock_zmq_context_instance: MagicMock, mock_async_callback: AsyncMock
    ):
        """Test registering a request handler."""
        client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        service_id = "test_service"
        message_type: MessageTypeT = MessageType.Status

        client.register_request_handler(service_id, message_type, mock_async_callback)

        key = (service_id, message_type)
        assert key in client._request_handlers
        assert client._request_handlers[key] == mock_async_callback

    def test_register_multiple_request_handlers(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test registering multiple request handlers."""
        client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        handlers = {
            ("service1", MessageType.Status): AsyncMock(),
            ("service1", MessageType.Heartbeat): AsyncMock(),
        }

        for (service_id, message_type), handler in handlers.items():
            client.register_request_handler(service_id, message_type, handler)

        # All handlers should be registered
        for key, handler in handlers.items():
            assert key in client._request_handlers
            assert client._request_handlers[key] == handler

    def test_register_duplicate_handler(
        self, mock_zmq_context_instance: MagicMock, mock_async_callback: AsyncMock
    ):
        """Test registering duplicate request handler."""
        client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        service_id = "test_service"
        message_type: MessageTypeT = MessageType.Status

        client.register_request_handler(service_id, message_type, mock_async_callback)

        # Registering again should raise an error
        new_handler = AsyncMock()
        with pytest.raises(ValueError, match="Handler already registered"):
            client.register_request_handler(service_id, message_type, new_handler)

    @pytest.mark.asyncio
    async def test_reply_receiving_task(
        self, mock_zmq_context_instance: MagicMock, mock_async_callback: AsyncMock
    ):
        """Test that reply receiving task is started."""
        client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        await client.initialize()
        client.register_request_handler(
            "test_service", MessageType.Status, mock_async_callback
        )

        # Should have started a receiving task
        assert hasattr(client, "_tasks")
        # In a real implementation, there should be tasks for receiving requests

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_on_stop_hook(self, mock_zmq_context_instance: MagicMock):
        """Test that the on_stop hook cancels all tasks."""
        client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        await client.initialize()

        # Mock the cancel_all_tasks method
        with patch.object(client, "cancel_all_tasks", new_callable=AsyncMock):
            await client.shutdown()
            # The on_stop hook should have been called

    @pytest.mark.parametrize(
        "message_type",
        [
            MessageType.Status,
            MessageType.Heartbeat,
            MessageType.Error,
        ],
    )
    def test_register_different_message_types(
        self,
        mock_zmq_context_instance: MagicMock,
        message_type,
        mock_async_callback: AsyncMock,
    ):
        """Test registering handlers for different message types."""
        client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        service_id = "test_service"
        client.register_request_handler(service_id, message_type, mock_async_callback)

        key = (service_id, message_type)
        assert key in client._request_handlers
        assert client._request_handlers[key] == mock_async_callback

    def test_register_handlers_multiple_services(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test registering handlers for multiple services."""
        client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        services = ["service1", "service2", "service3"]
        handlers = {}

        for service_id in services:
            handler = AsyncMock()
            client.register_request_handler(service_id, MessageType.Status, handler)
            handlers[(service_id, MessageType.Status)] = handler

        # All handlers should be registered
        for key, handler in handlers.items():
            assert key in client._request_handlers
            assert client._request_handlers[key] == handler

    @pytest.mark.asyncio
    async def test_request_handler_with_response(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test request handler that returns a response."""
        client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        # Create a handler that returns a response
        response_message = MockTestMessage(test_data="response")

        async def handler(request):
            return response_message

        service_id = "test_service"
        client.register_request_handler(service_id, MessageType.Status, handler)

        await client.initialize()

        # Mock receiving a request and test handler invocation
        # This would normally be done by the receiving task
        key = (service_id, MessageType.Status)
        assert key in client._request_handlers

        result = await client._request_handlers[key](test_message)
        assert result == response_message

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_request_handler_no_response(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test request handler that returns no response."""
        client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        # Create a handler that returns None
        async def handler(request):
            return None

        service_id = "test_service"
        client.register_request_handler(service_id, MessageType.Status, handler)

        await client.initialize()

        key = (service_id, MessageType.Status)
        result = await client._request_handlers[key](test_message)
        assert result is None

        await client.shutdown()

    @pytest.mark.asyncio
    async def test_request_handler_error(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test request handler that raises an error."""
        client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        # Create a handler that raises an error
        async def handler(request):
            raise ValueError("Handler error")

        service_id = "test_service"
        client.register_request_handler(service_id, MessageType.Status, handler)

        await client.initialize()

        key = (service_id, MessageType.Status)
        with pytest.raises(ValueError, match="Handler error"):
            await client._request_handlers[key](test_message)

        await client.shutdown()


class TestRequestReplyIntegration:
    """Integration tests for REQUEST/REPLY clients."""

    @pytest.mark.asyncio
    async def test_request_reply_message_flow(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test message flow from REQUEST to REPLY."""
        request_client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        reply_client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        # Create a handler that echoes the request
        async def echo_handler(request):
            return request

        await request_client.initialize()
        await reply_client.initialize()

        reply_client.register_request_handler(
            "test_service", test_message.message_type, echo_handler
        )

        # Mock the request-reply flow
        with patch.object(
            request_client, "_wait_for_response", return_value=test_message
        ):
            result = await request_client.request(test_message)

            assert result == test_message

        await request_client.shutdown()
        await reply_client.shutdown()

    @pytest.mark.asyncio
    async def test_multiple_clients_single_server(
        self,
        mock_zmq_context_instance: MagicMock,
        multiple_test_messages: list[MockTestMessage],
    ):
        """Test multiple request clients connecting to a single reply server."""
        request_clients = []
        for _ in range(3):
            client = ZMQDealerRequestClient(
                context=mock_zmq_context_instance,
                address="inproc://test_addr_5555",
                bind=False,
            )
            request_clients.append(client)

        reply_client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        # Create handlers for different message types
        handlers = {}
        for message in multiple_test_messages:

            async def create_handler(msg_type):
                async def _handler(request):
                    return MockTestMessage(test_data="response")

                return _handler

            handler = await create_handler(message.message_type)
            handlers[message.message_type] = handler
            reply_client.register_request_handler(
                "test_service", message.message_type, handler
            )

        # Initialize all clients
        for client in request_clients:
            await client.initialize()
        await reply_client.initialize()

        # Make requests from different clients
        with patch.object(ZMQDealerRequestClient, "_wait_for_response") as mock_wait:
            mock_wait.side_effect = lambda *args: multiple_test_messages[
                0
            ]  # Return first message

            tasks = [
                client.request(multiple_test_messages[i % len(multiple_test_messages)])
                for i, client in enumerate(request_clients)
            ]

            results = await asyncio.gather(*tasks)
            assert len(results) == len(request_clients)

        # Cleanup
        for client in request_clients:
            await client.shutdown()
        await reply_client.shutdown()

    @pytest.mark.asyncio
    async def test_request_reply_timeout_handling(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test timeout handling in request-reply flow."""
        request_client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        reply_client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        # Create a slow handler
        async def slow_handler(request):
            await asyncio.sleep(2.0)  # Longer than timeout
            return request

        await request_client.initialize()
        await reply_client.initialize()

        reply_client.register_request_handler(
            "test_service", test_message.message_type, slow_handler
        )

        # Mock timeout
        with (
            patch.object(
                request_client, "_wait_for_response", side_effect=asyncio.TimeoutError()
            ),
            pytest.raises(CommunicationError, match="Request timed out"),
        ):
            await request_client.request(test_message, timeout=0.1)

        await request_client.shutdown()
        await reply_client.shutdown()

    @pytest.mark.asyncio
    async def test_request_reply_error_isolation(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test that errors in one request don't affect others."""
        request_client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        reply_client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5556",
            bind=True,
        )

        await request_client.initialize()
        await reply_client.initialize()

        # Make request client fail
        request_socket = mock_zmq_context_instance.socket.return_value
        request_socket.send_multipart.side_effect = zmq.ZMQError(
            errno=1, msg="Request failed"
        )

        # Request should fail
        with pytest.raises(CommunicationError):
            await request_client.request(test_message)

        # But registering reply handler should still work
        async def handler(request):
            return request

        reply_client.register_request_handler(
            "test_service", test_message.message_type, handler
        )

        key = ("test_service", test_message.message_type)
        assert key in reply_client._request_handlers

        await request_client.shutdown()
        await reply_client.shutdown()

    @pytest.mark.asyncio
    async def test_async_request_callback(
        self, mock_zmq_context_instance: MagicMock, test_message: MockTestMessage
    ):
        """Test asynchronous request with callback."""
        request_client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        reply_client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        callback = AsyncMock()

        await request_client.initialize()
        await reply_client.initialize()

        # Register handler
        async def echo_handler(request):
            return request

        reply_client.register_request_handler(
            "test_service", test_message.message_type, echo_handler
        )

        # Make async request
        with patch.object(request_client, "_handle_async_response"):
            await request_client.request_async(test_message, callback)

            # Verify request was sent
            request_socket = mock_zmq_context_instance.socket.return_value
            request_socket.send_multipart.assert_called_once()

        await request_client.shutdown()
        await reply_client.shutdown()

    @pytest.mark.asyncio
    async def test_high_concurrency_requests(
        self, mock_zmq_context_instance: MagicMock
    ):
        """Test high concurrency request-reply scenario."""
        request_client = ZMQDealerRequestClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=False,
        )

        reply_client = ZMQRouterReplyClient(
            context=mock_zmq_context_instance,
            address="inproc://test_addr_5555",
            bind=True,
        )

        await request_client.initialize()
        await reply_client.initialize()

        # Create many messages
        messages = [
            MockTestMessage(
                message_type=MessageType.Status, test_data=f"msg_{i}", counter=i
            )
            for i in range(50)
        ]

        # Register handler
        async def echo_handler(request):
            return request

        reply_client.register_request_handler(
            "test_service", MessageType.Status, echo_handler
        )

        # Make many concurrent requests
        with patch.object(request_client, "_wait_for_response", side_effect=messages):
            tasks = [request_client.request(message) for message in messages]
            results = await asyncio.gather(*tasks)

            assert len(results) == len(messages)
            for i, result in enumerate(results):
                assert result == messages[i]

        await request_client.shutdown()
        await reply_client.shutdown()
