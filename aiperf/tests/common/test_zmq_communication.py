import pytest
import asyncio
import json
import time
import uuid
from unittest.mock import MagicMock, patch, AsyncMock, call, ANY

from aiperf.common.zmq_communication import ZMQCommunication


class TestZMQCommunication:
    """Tests for the ZMQCommunication class."""
    
    @pytest.fixture
    def mock_zmq_context(self):
        """Create a mock ZMQ context."""
        with patch("zmq.asyncio.Context") as mock_context:
            # Create mock sockets
            mock_pub_socket = AsyncMock()
            mock_sub_socket = AsyncMock()
            mock_req_socket = AsyncMock()
            mock_rep_socket = AsyncMock()
            
            # Set up context to return mock sockets
            mock_context.return_value.socket.side_effect = [
                mock_pub_socket,
                mock_sub_socket,
                mock_req_socket,
                mock_rep_socket
            ]
            
            yield mock_context, mock_pub_socket, mock_sub_socket, mock_req_socket, mock_rep_socket
    
    @pytest.mark.asyncio
    async def test_initialize(self, mock_zmq_context):
        """Test initialization of ZMQ communication."""
        # Arrange
        mock_context, mock_pub_socket, mock_sub_socket, mock_req_socket, mock_rep_socket = mock_zmq_context
        
        with patch("asyncio.create_task") as mock_create_task:
            # Act
            comm = ZMQCommunication(client_id="test_client")
            result = await comm.initialize()
            
            # Assert
            assert result is True
            assert comm._is_initialized is True
            
            # Check socket initialization
            mock_pub_socket.connect.assert_called_once_with("tcp://127.0.0.1:5555")
            mock_sub_socket.connect.assert_called_once_with("tcp://127.0.0.1:5555")
            mock_req_socket.connect.assert_called_once_with("tcp://127.0.0.1:5556")
            mock_rep_socket.bind.assert_called_once_with("tcp://127.0.0.1:5556")
            
            # Check background tasks
            assert mock_create_task.call_count == 2
    
    @pytest.mark.asyncio
    async def test_initialize_with_custom_addresses(self, mock_zmq_context):
        """Test initialization with custom addresses."""
        # Arrange
        mock_context, mock_pub_socket, mock_sub_socket, mock_req_socket, mock_rep_socket = mock_zmq_context
        
        with patch("asyncio.create_task"):
            # Act
            comm = ZMQCommunication(
                pub_address="tcp://publisher:5557",
                sub_address="tcp://subscriber:5558",
                req_address="tcp://requester:5559",
                rep_address="tcp://responder:5560",
                client_id="test_client"
            )
            result = await comm.initialize()
            
            # Assert
            assert result is True
            
            # Check socket initialization with custom addresses
            mock_pub_socket.connect.assert_called_once_with("tcp://publisher:5557")
            mock_sub_socket.connect.assert_called_once_with("tcp://subscriber:5558")
            mock_req_socket.connect.assert_called_once_with("tcp://requester:5559")
            mock_rep_socket.bind.assert_called_once_with("tcp://responder:5560")
    
    @pytest.mark.asyncio
    async def test_initialize_twice(self, mock_zmq_context):
        """Test initializing ZMQ communication twice."""
        # Arrange
        mock_context, *_ = mock_zmq_context
        
        with patch("asyncio.create_task"):
            comm = ZMQCommunication(client_id="test_client")
            await comm.initialize()
            
            # Act
            result = await comm.initialize()
            
            # Assert
            assert result is True  # Should return True for subsequent calls
    
    @pytest.mark.asyncio
    async def test_initialize_error(self, mock_zmq_context):
        """Test error during initialization."""
        # Arrange
        mock_context, mock_pub_socket, *_ = mock_zmq_context
        mock_pub_socket.connect.side_effect = Exception("Connection error")
        
        # Act
        comm = ZMQCommunication(client_id="test_client")
        result = await comm.initialize()
        
        # Assert
        assert result is False
        assert comm._is_initialized is False
    
    @pytest.mark.asyncio
    async def test_shutdown(self, mock_zmq_context):
        """Test graceful shutdown of ZMQ communication."""
        # Arrange
        mock_context, mock_pub_socket, mock_sub_socket, mock_req_socket, mock_rep_socket = mock_zmq_context
        
        with patch("asyncio.create_task"):
            comm = ZMQCommunication(client_id="test_client")
            await comm.initialize()
            
            # Act
            result = await comm.shutdown()
            
            # Assert
            assert result is True
            assert comm._is_shutdown is True
            assert comm._is_initialized is False
            
            # Check socket cleanup
            mock_pub_socket.close.assert_called_once()
            mock_sub_socket.close.assert_called_once()
            mock_req_socket.close.assert_called_once()
            mock_rep_socket.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown_not_initialized(self, mock_zmq_context):
        """Test shutting down ZMQ communication that wasn't initialized."""
        # Arrange
        mock_context, *_ = mock_zmq_context
        comm = ZMQCommunication(client_id="test_client")
        
        # Act
        result = await comm.shutdown()
        
        # Assert
        assert result is True  # Should still return True
        assert comm._is_shutdown is True
    
    @pytest.mark.asyncio
    async def test_shutdown_error(self, mock_zmq_context):
        """Test error during shutdown."""
        # Arrange
        mock_context, mock_pub_socket, *_ = mock_zmq_context
        mock_pub_socket.close.side_effect = Exception("Close error")
        
        with patch("asyncio.create_task"):
            comm = ZMQCommunication(client_id="test_client")
            await comm.initialize()
            
            # Act
            result = await comm.shutdown()
            
            # Assert
            assert result is False
    
    @pytest.mark.asyncio
    async def test_publish(self, mock_zmq_context):
        """Test publishing a message to a topic."""
        # Arrange
        mock_context, mock_pub_socket, *_ = mock_zmq_context
        
        with patch("asyncio.create_task"):
            comm = ZMQCommunication(client_id="test_client")
            await comm.initialize()
            
            # Act
            result = await comm.publish("test_topic", {"message": "Hello"})
            
            # Assert
            assert result is True
            
            # Check message was sent correctly
            mock_pub_socket.send_multipart.assert_called_once()
            call_args = mock_pub_socket.send_multipart.call_args[0][0]
            assert call_args[0] == b"test_topic"
            
            # Decode and parse the JSON message
            message_json = call_args[1].decode()
            message = json.loads(message_json)
            assert message["client_id"] == "test_client"
            assert "timestamp" in message
            assert message["data"] == {"message": "Hello"}
    
    @pytest.mark.asyncio
    async def test_publish_not_initialized(self, mock_zmq_context):
        """Test publishing when communication is not initialized."""
        # Arrange
        mock_context, *_ = mock_zmq_context
        comm = ZMQCommunication(client_id="test_client")
        
        # Act
        result = await comm.publish("test_topic", {"message": "Hello"})
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_subscribe(self, mock_zmq_context):
        """Test subscribing to a topic."""
        # Arrange
        mock_context, _, mock_sub_socket, *_ = mock_zmq_context
        
        with patch("asyncio.create_task"):
            comm = ZMQCommunication(client_id="test_client")
            await comm.initialize()
            callback = MagicMock()
            
            # Act
            result = await comm.subscribe("test_topic", callback)
            
            # Assert
            assert result is True
            mock_sub_socket.subscribe.assert_called_once_with(b"test_topic")
            assert "test_topic" in comm._subscribers
            assert callback in comm._subscribers["test_topic"]
    
    @pytest.mark.asyncio
    async def test_subscribe_not_initialized(self, mock_zmq_context):
        """Test subscribing when communication is not initialized."""
        # Arrange
        mock_context, *_ = mock_zmq_context
        comm = ZMQCommunication(client_id="test_client")
        callback = MagicMock()
        
        # Act
        result = await comm.subscribe("test_topic", callback)
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_request_response(self, mock_zmq_context):
        """Test sending a request and receiving a response."""
        # Arrange
        mock_context, _, _, mock_req_socket, _ = mock_zmq_context
        
        # Set up mock response
        response_data = {
            "status": "success",
            "request_id": ANY,  # We'll capture this later
            "data": {"response": "Hello"}
        }
        
        # Mock req_socket.send_json to capture the request_id
        original_send_json = mock_req_socket.send_json
        captured_request_id = None
        
        async def mock_send_json(data):
            nonlocal captured_request_id
            captured_request_id = data.get("request_id")
            await original_send_json(data)
        
        mock_req_socket.send_json = mock_send_json
        
        # Mock req_socket.recv_json to return response with captured request_id
        async def mock_recv_json():
            response = response_data.copy()
            response["request_id"] = captured_request_id
            return response
        
        mock_req_socket.recv_json = mock_recv_json
        
        with patch("asyncio.create_task"):
            comm = ZMQCommunication(client_id="test_client")
            await comm.initialize()
            
            # Act
            response = await comm.request("server", {"message": "Hello"})
            
            # Assert
            assert response["status"] == "success"
            assert response["data"] == {"response": "Hello"}
            
            # Check that send_json was called with correct parameters
            mock_req_socket.send_json.assert_called_once()
            sent_data = mock_req_socket.send_json.call_args[0][0]
            assert sent_data["client_id"] == "test_client"
            assert sent_data["target"] == "server"
            assert sent_data["data"] == {"message": "Hello"}
            assert "request_id" in sent_data
            assert "timestamp" in sent_data
    
    @pytest.mark.asyncio
    async def test_request_not_initialized(self, mock_zmq_context):
        """Test requesting when communication is not initialized."""
        # Arrange
        mock_context, *_ = mock_zmq_context
        comm = ZMQCommunication(client_id="test_client")
        
        # Act
        response = await comm.request("server", {"message": "Hello"})
        
        # Assert
        assert response["status"] == "error"
        assert "not initialized" in response["message"]
    
    @pytest.mark.asyncio
    async def test_respond(self, mock_zmq_context):
        """Test responding to a request."""
        # Arrange
        mock_context, _, _, _, mock_rep_socket = mock_zmq_context
        
        with patch("asyncio.create_task"):
            comm = ZMQCommunication(client_id="test_client")
            await comm.initialize()
            
            # Act
            result = await comm.respond("client", {
                "request_id": "test_request",
                "status": "success",
                "data": {"response": "Hello"}
            })
            
            # Assert
            assert result is True
            mock_rep_socket.send_json.assert_called_once()
            sent_data = mock_rep_socket.send_json.call_args[0][0]
            assert sent_data["request_id"] == "test_request"
            assert sent_data["status"] == "success"
            assert sent_data["data"] == {"response": "Hello"}
    
    @pytest.mark.asyncio
    async def test_respond_not_initialized(self, mock_zmq_context):
        """Test responding when communication is not initialized."""
        # Arrange
        mock_context, *_ = mock_zmq_context
        comm = ZMQCommunication(client_id="test_client")
        
        # Act
        result = await comm.respond("client", {
            "request_id": "test_request",
            "status": "success",
            "data": {"response": "Hello"}
        })
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_sub_receiver(self, mock_zmq_context):
        """Test the subscription receiver background task."""
        # Arrange
        mock_context, _, mock_sub_socket, *_ = mock_zmq_context
        
        # Create a queue of messages to process
        message_queue = asyncio.Queue()
        await message_queue.put((b"test_topic", b'{"client_id":"other_client","timestamp":123456789,"data":{"message":"Hello"}}'))
        await message_queue.put((b"invalid_topic", b"invalid json"))  # Add an invalid message to test error handling
        # Add None to signal end of queue
        await message_queue.put(None)
        
        # Mock recv_multipart to get messages from queue
        async def mock_recv_multipart():
            msg = await message_queue.get()
            if msg is None:
                # Raise an exception to exit the loop
                raise asyncio.CancelledError()
            return msg
        
        mock_sub_socket.recv_multipart.side_effect = mock_recv_multipart
        
        # Create mock callback
        callback = MagicMock()
        
        with patch("asyncio.create_task") as mock_create_task:
            # Make create_task actually execute the coroutine
            mock_create_task.side_effect = lambda coro: asyncio.create_task(coro)
            
            comm = ZMQCommunication(client_id="test_client")
            await comm.initialize()
            
            # Add callback
            comm._subscribers["test_topic"] = [callback]
            
            # Wait for all messages to be processed
            try:
                await asyncio.wait_for(comm._sub_receiver(), timeout=1)
            except asyncio.CancelledError:
                pass  # Expected
            
            # Assert
            callback.assert_called_once_with({"message": "Hello"})
    
    @pytest.mark.asyncio
    async def test_rep_receiver(self, mock_zmq_context):
        """Test the reply receiver background task."""
        # Arrange
        mock_context, _, _, _, mock_rep_socket = mock_zmq_context
        
        # Create a queue of messages to process
        message_queue = asyncio.Queue()
        await message_queue.put({
            "client_id": "other_client", 
            "target": "test_client",
            "request_id": "123",
            "timestamp": 123456789,
            "data": {"message": "Hello"}
        })
        # Add None to signal end of queue
        await message_queue.put(None)
        
        # Mock recv_json to get messages from queue
        async def mock_recv_json():
            msg = await message_queue.get()
            if msg is None:
                # Raise an exception to exit the loop
                raise asyncio.CancelledError()
            return msg
        
        mock_rep_socket.recv_json.side_effect = mock_recv_json
        
        with patch("asyncio.create_task") as mock_create_task:
            # Make create_task actually execute the coroutine
            mock_create_task.side_effect = lambda coro: asyncio.create_task(coro)
            
            comm = ZMQCommunication(client_id="test_client")
            await comm.initialize()
            
            # Wait for all messages to be processed
            try:
                await asyncio.wait_for(comm._rep_receiver(), timeout=1)
            except asyncio.CancelledError:
                pass  # Expected
            
            # Assert
            mock_rep_socket.send_json.assert_called_once()
            sent_data = mock_rep_socket.send_json.call_args[0][0]
            assert sent_data["status"] == "success"
            assert sent_data["request_id"] == "123" 