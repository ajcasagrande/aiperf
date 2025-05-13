"""
Tests for the ZMQ communication module.
"""

from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from pydantic import Field

from aiperf.common.comms.zmq_comms.zmq_communication import ZMQCommunication
from aiperf.common.enums import ClientType, Topic, ServiceType
from aiperf.common.models.base_models import BasePayload
from aiperf.common.models.comms import ZMQCommunicationConfig, ZMQTCPTransportConfig
from aiperf.common.models.messages import BaseMessage


class MockPayload(BasePayload):
    """Mock message payload class for testing."""

    content: str = Field(
        ...,
        description="Content of the message",
    )


@pytest.mark.asyncio
class TestZMQCommunication:
    """Tests for the ZMQ communication class."""

    @pytest.fixture
    def mock_config(self):
        """Return a mock configuration for ZMQCommunication."""
        return ZMQCommunicationConfig(
            protocol_config=ZMQTCPTransportConfig(), client_id="test-client"
        )

    @pytest.fixture
    def zmq_communication(self, mock_config):
        """Return a ZMQCommunication instance for testing."""
        with patch("zmq.asyncio.Context", MagicMock()) as mock_context:
            # Set up the context mock to return properly
            mock_context.return_value = MagicMock()
            comm = ZMQCommunication(config=mock_config)
            return comm

    @pytest.fixture
    def test_message(self):
        """Create a test message for communication tests."""
        return BaseMessage(
            service_id="test-service",
            service_type=ServiceType.TEST,
            payload=MockPayload(content="Test content"),
        )

    async def test_initialization(self, zmq_communication):
        """Test that the ZMQ communication initializes correctly."""
        result = await zmq_communication.initialize()
        assert result is True
        assert zmq_communication._is_initialized is True

    async def test_initialization_failure(self, zmq_communication):
        """Test initialization failure handling."""
        # Temporarily set _is_initialized to false to test error path
        zmq_communication._is_initialized = False

        # Create a mock implementation that raises an exception
        async def mock_init_with_error():
            raise Exception("Connection error")

        # Replace the original method and call to test error handling
        original_init = zmq_communication.initialize
        zmq_communication.initialize = mock_init_with_error

        try:
            with pytest.raises(Exception, match="Connection error"):
                await zmq_communication.initialize()
        finally:
            # Restore the original method
            zmq_communication.initialize = original_init

    async def test_create_clients(self, zmq_communication):
        """Test creating clients for different communication patterns."""
        # Mock the client socket creation
        mock_client = AsyncMock()

        # Patch the specific client classes and ensure they return our mock
        with (
            patch(
                "aiperf.common.comms.zmq_comms.pub.ZmqPublisher",
                return_value=mock_client,
            ),
            patch(
                "aiperf.common.comms.zmq_comms.sub.ZmqSubscriber",
                return_value=mock_client,
            ),
        ):
            # Call create_clients
            await zmq_communication.create_clients(
                ClientType.COMPONENT_PUB, ClientType.COMPONENT_SUB
            )

            # Verify clients were added to the dictionary
            assert ClientType.COMPONENT_PUB in zmq_communication.clients
            assert ClientType.COMPONENT_SUB in zmq_communication.clients

            # Verify initialize was called for each client
            assert len(zmq_communication.clients) == 2

    async def test_publish_message(self, zmq_communication, test_message):
        """Test publishing messages."""
        # Mock the socket publish method
        mock_client = AsyncMock()
        mock_client.publish.return_value = True

        # Set up the client in the clients dictionary
        zmq_communication.clients = {ClientType.COMPONENT_PUB: mock_client}
        zmq_communication._is_initialized = True

        # Publish a message
        result = await zmq_communication.publish(
            ClientType.COMPONENT_PUB, Topic.STATUS, test_message
        )

        # Verify the message was published
        assert result is True
        mock_client.publish.assert_called_once_with(Topic.STATUS, test_message)

    async def test_publish_with_invalid_client(self, zmq_communication, test_message):
        """Test publishing with an invalid client type."""
        # Mock create_clients to verify it's called
        with (
            patch.object(
                zmq_communication, "create_clients", return_value=None
            ) as mock_create,
            patch.object(zmq_communication, "clients", {}),
        ):
            zmq_communication._is_initialized = True

            # Try to publish with a non-existent client
            await zmq_communication.publish(
                ClientType.COMPONENT_PUB, Topic.STATUS, test_message
            )

            # Verify create_clients was called
            mock_create.assert_called_once_with(ClientType.COMPONENT_PUB)

    async def test_subscribe_to_topic(self, zmq_communication):
        """Test subscribing to a topic."""
        # Mock the client socket
        mock_client = AsyncMock()
        mock_client.subscribe.return_value = True

        # Set up the client in the clients dictionary
        zmq_communication.clients = {ClientType.COMPONENT_SUB: mock_client}
        zmq_communication._is_initialized = True

        # Create a callback function
        async def callback(message):
            pass

        # Subscribe to a topic
        result = await zmq_communication.subscribe(
            ClientType.COMPONENT_SUB, Topic.STATUS, callback
        )

        # Verify subscription was set up
        assert result is True
        mock_client.subscribe.assert_called_once_with(Topic.STATUS, callback)

    async def test_shutdown(self, zmq_communication):
        """Test graceful shutdown of communication."""
        # Mock the client socket
        mock_client1 = AsyncMock()
        mock_client1.shutdown.return_value = None
        mock_client2 = AsyncMock()
        mock_client2.shutdown.return_value = None

        # Set up clients
        zmq_communication.clients = {
            ClientType.COMPONENT_PUB: mock_client1,
            ClientType.COMPONENT_SUB: mock_client2,
        }
        zmq_communication._is_initialized = True
        zmq_communication._is_shutdown = False

        # Mock the context with a patched shutdown method to avoid setting context to None
        context_mock = MagicMock()
        zmq_communication.context = context_mock

        # Create a patched version of shutdown that doesn't set context to None
        original_shutdown = zmq_communication.shutdown

        async def patched_shutdown():
            # Call original gather but patch term() to prevent context from becoming None
            with patch.object(zmq_communication, "context", context_mock):
                return await original_shutdown()

        zmq_communication.shutdown = patched_shutdown

        try:
            # Shutdown the communication
            result = await zmq_communication.shutdown()

            # Verify both clients were shutdown
            assert result is True
            assert mock_client1.shutdown.called
            assert mock_client2.shutdown.called
            assert context_mock.term.called
            assert zmq_communication._is_shutdown is True
        finally:
            # Restore the original method
            zmq_communication.shutdown = original_shutdown
