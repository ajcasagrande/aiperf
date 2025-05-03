import pytest
import asyncio
from unittest.mock import patch, MagicMock
from typing import Dict, Any, List, Set

from aiperf.common.memory_communication import MemoryCommunication


class TestMemoryCommunication:
    """Tests for the MemoryCommunication class."""
    
    @pytest.fixture
    def reset_memory_communication(self):
        """Reset MemoryCommunication class variables between tests."""
        # Store original values
        original_topics = MemoryCommunication._topics.copy() if hasattr(MemoryCommunication, '_topics') else {}
        original_subscribers = MemoryCommunication._subscribers.copy() if hasattr(MemoryCommunication, '_subscribers') else {}
        original_messages = MemoryCommunication._messages.copy() if hasattr(MemoryCommunication, '_messages') else {}
        original_requests = MemoryCommunication._requests.copy() if hasattr(MemoryCommunication, '_requests') else {}
        original_responses = MemoryCommunication._responses.copy() if hasattr(MemoryCommunication, '_responses') else {}
        
        # Reset class variables
        MemoryCommunication._topics = {}
        MemoryCommunication._subscribers = {}
        MemoryCommunication._messages = {}
        MemoryCommunication._requests = {}
        MemoryCommunication._responses = {}
        
        yield
        
        # Restore original values
        MemoryCommunication._topics = original_topics
        MemoryCommunication._subscribers = original_subscribers
        MemoryCommunication._messages = original_messages
        MemoryCommunication._requests = original_requests
        MemoryCommunication._responses = original_responses
    
    @pytest.mark.asyncio
    async def test_initialize(self, reset_memory_communication):
        """Test initialization of memory communication."""
        # Arrange
        comm = MemoryCommunication(client_id="test_client")
        
        # Act
        result = await comm.initialize()
        
        # Assert
        assert result is True
        assert comm._is_initialized is True
        assert "test_client" in MemoryCommunication._messages
        assert "test_client" in MemoryCommunication._requests
        assert "test_client" in MemoryCommunication._responses
    
    @pytest.mark.asyncio
    async def test_initialize_twice(self, reset_memory_communication):
        """Test initializing memory communication twice."""
        # Arrange
        comm = MemoryCommunication(client_id="test_client")
        await comm.initialize()
        
        # Act
        result = await comm.initialize()
        
        # Assert
        assert result is True  # Should return True for subsequent calls
    
    @pytest.mark.asyncio
    async def test_initialize_error(self, reset_memory_communication):
        """Test error during initialization."""
        # Arrange
        comm = MemoryCommunication(client_id="test_client")
        
        # Create a mock that raises an exception
        with patch.object(asyncio, "create_task", side_effect=Exception("Test error")):
            # Act
            result = await comm.initialize()
            
            # Assert
            assert result is False
            assert comm._is_initialized is False
    
    @pytest.mark.asyncio
    async def test_shutdown(self, reset_memory_communication):
        """Test graceful shutdown of memory communication."""
        # Arrange
        comm = MemoryCommunication(client_id="test_client")
        await comm.initialize()
        
        # Act
        result = await comm.shutdown()
        
        # Assert
        assert result is True
        assert comm._is_shutdown is True
        assert comm._is_initialized is False
        assert "test_client" not in MemoryCommunication._messages
        assert "test_client" not in MemoryCommunication._requests
        assert "test_client" not in MemoryCommunication._responses
    
    @pytest.mark.asyncio
    async def test_shutdown_not_initialized(self, reset_memory_communication):
        """Test shutting down memory communication that wasn't initialized."""
        # Arrange
        comm = MemoryCommunication(client_id="test_client")
        
        # Act
        result = await comm.shutdown()
        
        # Assert
        assert result is True  # Should still return True
        assert comm._is_shutdown is True
    
    @pytest.mark.asyncio
    async def test_shutdown_error(self, reset_memory_communication):
        """Test error during shutdown."""
        # Arrange
        comm = MemoryCommunication(client_id="test_client")
        await comm.initialize()
        
        # Mock pop to raise an exception
        with patch.dict(MemoryCommunication._messages, clear=True), \
             patch.dict("aiperf.common.memory_communication.MemoryCommunication._messages", 
                  {"test_client": MagicMock(side_effect=Exception("Test error"))}):
            # Act
            result = await comm.shutdown()
            
            # Assert
            assert result is False
    
    @pytest.mark.asyncio
    async def test_publish_to_topic(self, reset_memory_communication):
        """Test publishing a message to a topic."""
        # Arrange
        comm1 = MemoryCommunication(client_id="publisher")
        comm2 = MemoryCommunication(client_id="subscriber")
        await comm1.initialize()
        await comm2.initialize()
        
        # Set up topic and subscriber
        MemoryCommunication._topics["test_topic"] = {"subscriber"}
        
        # Act
        result = await comm1.publish("test_topic", {"message": "Hello"})
        
        # Assert
        assert result is True
        # Check that the message was queued for the subscriber
        assert MemoryCommunication._messages["subscriber"].qsize() == 1
        message = await MemoryCommunication._messages["subscriber"].get()
        assert message["topic"] == "test_topic"
        assert message["client_id"] == "publisher"
        assert message["data"] == {"message": "Hello"}
    
    @pytest.mark.asyncio
    async def test_publish_to_nonexistent_topic(self, reset_memory_communication):
        """Test publishing to a topic with no subscribers."""
        # Arrange
        comm = MemoryCommunication(client_id="publisher")
        await comm.initialize()
        
        # Act
        result = await comm.publish("nonexistent_topic", {"message": "Hello"})
        
        # Assert
        assert result is True  # Publishing to a topic with no subscribers is not an error
    
    @pytest.mark.asyncio
    async def test_publish_not_initialized(self, reset_memory_communication):
        """Test publishing when communication is not initialized."""
        # Arrange
        comm = MemoryCommunication(client_id="publisher")
        
        # Act
        result = await comm.publish("test_topic", {"message": "Hello"})
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_subscribe_to_topic(self, reset_memory_communication):
        """Test subscribing to a topic."""
        # Arrange
        comm = MemoryCommunication(client_id="subscriber")
        await comm.initialize()
        callback = MagicMock()
        
        # Act
        result = await comm.subscribe("test_topic", callback)
        
        # Assert
        assert result is True
        assert "test_topic" in MemoryCommunication._topics
        assert "subscriber" in MemoryCommunication._topics["test_topic"]
        assert "test_topic" in MemoryCommunication._subscribers
        assert "subscriber" in MemoryCommunication._subscribers["test_topic"]
        assert callback in MemoryCommunication._subscribers["test_topic"]["subscriber"]
    
    @pytest.mark.asyncio
    async def test_subscribe_not_initialized(self, reset_memory_communication):
        """Test subscribing when communication is not initialized."""
        # Arrange
        comm = MemoryCommunication(client_id="subscriber")
        callback = MagicMock()
        
        # Act
        result = await comm.subscribe("test_topic", callback)
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_request_response(self, reset_memory_communication):
        """Test sending a request and receiving a response."""
        # Arrange
        client = MemoryCommunication(client_id="client")
        server = MemoryCommunication(client_id="server")
        await client.initialize()
        await server.initialize()
        
        # Set up request handler
        async def request_handler():
            request = await MemoryCommunication._requests["server"].get()
            await server.respond(request["client_id"], {
                "request_id": request["request_id"],
                "status": "success",
                "data": {"response": "Hello"}
            })
        
        # Create task for request handler
        handler_task = asyncio.create_task(request_handler())
        
        # Act
        response = await client.request("server", {"message": "Hello"})
        
        # Clean up
        await handler_task
        
        # Assert
        assert response["status"] == "success"
        assert response["data"] == {"response": "Hello"}
    
    @pytest.mark.asyncio
    async def test_request_timeout(self, reset_memory_communication):
        """Test request timeout."""
        # Arrange
        client = MemoryCommunication(client_id="client")
        server = MemoryCommunication(client_id="server")
        await client.initialize()
        await server.initialize()
        
        # Act
        response = await client.request("server", {"message": "Hello"}, timeout=0.1)
        
        # Assert
        assert response["status"] == "error"
        assert "Timeout" in response["message"]
    
    @pytest.mark.asyncio
    async def test_request_nonexistent_target(self, reset_memory_communication):
        """Test requesting from a nonexistent target."""
        # Arrange
        client = MemoryCommunication(client_id="client")
        await client.initialize()
        
        # Act
        response = await client.request("nonexistent", {"message": "Hello"})
        
        # Assert
        assert response["status"] == "error"
        assert "Target component not found" in response["message"]
    
    @pytest.mark.asyncio
    async def test_request_not_initialized(self, reset_memory_communication):
        """Test requesting when communication is not initialized."""
        # Arrange
        client = MemoryCommunication(client_id="client")
        
        # Act
        response = await client.request("server", {"message": "Hello"})
        
        # Assert
        assert response["status"] == "error"
        assert "Communication not initialized" in response["message"]
    
    @pytest.mark.asyncio
    async def test_respond(self, reset_memory_communication):
        """Test responding to a request."""
        # Arrange
        client = MemoryCommunication(client_id="client")
        server = MemoryCommunication(client_id="server")
        await client.initialize()
        await server.initialize()
        
        # Create a mock future
        request_id = "test_request"
        future = asyncio.Future()
        MemoryCommunication._responses["client"][request_id] = future
        
        # Act
        result = await server.respond("client", {
            "request_id": request_id,
            "status": "success",
            "data": {"response": "Hello"}
        })
        
        # Assert
        assert result is True
        assert future.done()
        response = future.result()
        assert response["status"] == "success"
        assert response["data"] == {"response": "Hello"}
    
    @pytest.mark.asyncio
    async def test_respond_nonexistent_target(self, reset_memory_communication):
        """Test responding to a nonexistent target."""
        # Arrange
        server = MemoryCommunication(client_id="server")
        await server.initialize()
        
        # Act
        result = await server.respond("nonexistent", {
            "request_id": "test_request",
            "status": "success",
            "data": {"response": "Hello"}
        })
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_respond_nonexistent_request(self, reset_memory_communication):
        """Test responding to a nonexistent request."""
        # Arrange
        client = MemoryCommunication(client_id="client")
        server = MemoryCommunication(client_id="server")
        await client.initialize()
        await server.initialize()
        
        # Act
        result = await server.respond("client", {
            "request_id": "nonexistent",
            "status": "success",
            "data": {"response": "Hello"}
        })
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_process_messages(self, reset_memory_communication):
        """Test message processing."""
        # Arrange
        comm = MemoryCommunication(client_id="test_client")
        await comm.initialize()
        
        # Create mock callback
        callback = MagicMock()
        topic = "test_topic"
        
        # Set up topic and subscriber with callback
        await comm.subscribe(topic, callback)
        
        # Create test message
        message = {
            "topic": topic,
            "client_id": "other_client",
            "timestamp": 123456789,
            "data": {"message": "Hello"}
        }
        
        # Add message to queue
        await MemoryCommunication._messages["test_client"].put(message)
        
        # Act: Wait a bit for the message to be processed
        await asyncio.sleep(0.1)
        
        # Assert
        callback.assert_called_once_with(message["data"])
    
    @pytest.mark.asyncio
    async def test_integration_publish_subscribe(self, reset_memory_communication):
        """Test integration of publish and subscribe functionality."""
        # Arrange
        publisher = MemoryCommunication(client_id="publisher")
        subscriber = MemoryCommunication(client_id="subscriber")
        await publisher.initialize()
        await subscriber.initialize()
        
        # Create event to signal when message is received
        message_received = asyncio.Event()
        received_message = None
        
        # Define callback
        def on_message(message):
            nonlocal received_message
            received_message = message
            message_received.set()
        
        # Subscribe to topic
        await subscriber.subscribe("test_topic", on_message)
        
        # Act
        await publisher.publish("test_topic", {"message": "Hello from integration test"})
        
        # Wait for message to be received (with timeout)
        try:
            await asyncio.wait_for(message_received.wait(), timeout=1)
        except asyncio.TimeoutError:
            pytest.fail("Message was not received within timeout")
        
        # Assert
        assert received_message == {"message": "Hello from integration test"} 