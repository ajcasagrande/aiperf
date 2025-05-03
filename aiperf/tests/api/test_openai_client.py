import pytest
import json
import time
from unittest.mock import patch, AsyncMock, MagicMock, ANY

from aiperf.api.openai_client import OpenAIClient
from aiperf.config.config_models import EndpointConfig


class TestOpenAIClient:
    """Tests for the OpenAIClient class."""
    
    @pytest.fixture
    def sample_endpoint_config(self):
        """Create a sample endpoint configuration."""
        return EndpointConfig(
            name="test-endpoint",
            url="https://api.example.com/v1/",
            api_type="openai",
            headers={"Content-Type": "application/json"},
            auth={"api_key": "test-api-key"},
            timeout=10.0
        )
    
    @pytest.fixture
    def sample_response_data(self):
        """Create a sample response data structure."""
        return {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "This is a test response."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
    
    @pytest.fixture
    def mock_aiohttp_session(self):
        """Create a mock aiohttp ClientSession."""
        with patch("aiohttp.ClientSession") as mock_session:
            # Create a mock response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock()
            
            # Make post return the mock response
            mock_session.return_value.post.return_value.__aenter__.return_value = mock_response
            
            yield mock_session, mock_response
    
    @pytest.mark.asyncio
    async def test_initialize(self, sample_endpoint_config, mock_aiohttp_session):
        """Test initialization of OpenAI client."""
        # Arrange
        mock_session, _ = mock_aiohttp_session
        client = OpenAIClient(sample_endpoint_config)
        
        # Act
        result = await client.initialize()
        
        # Assert
        assert result is True
        mock_session.assert_called_once_with(
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer test-api-key"
            }
        )
    
    @pytest.mark.asyncio
    async def test_initialize_error(self, sample_endpoint_config):
        """Test error during initialization."""
        # Arrange
        client = OpenAIClient(sample_endpoint_config)
        
        # Mock aiohttp.ClientSession to raise an exception
        with patch("aiohttp.ClientSession", side_effect=Exception("Test error")):
            # Act
            result = await client.initialize()
            
            # Assert
            assert result is False
    
    @pytest.mark.asyncio
    async def test_shutdown(self, sample_endpoint_config, mock_aiohttp_session):
        """Test graceful shutdown of OpenAI client."""
        # Arrange
        mock_session, _ = mock_aiohttp_session
        client = OpenAIClient(sample_endpoint_config)
        await client.initialize()
        
        # Create a mock session.close
        mock_session_instance = mock_session.return_value
        mock_session_instance.close = AsyncMock()
        
        # Act
        result = await client.shutdown()
        
        # Assert
        assert result is True
        mock_session_instance.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown_error(self, sample_endpoint_config, mock_aiohttp_session):
        """Test error during shutdown."""
        # Arrange
        mock_session, _ = mock_aiohttp_session
        client = OpenAIClient(sample_endpoint_config)
        await client.initialize()
        
        # Create a mock session.close that raises an exception
        mock_session_instance = mock_session.return_value
        mock_session_instance.close = AsyncMock(side_effect=Exception("Test error"))
        
        # Act
        result = await client.shutdown()
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_shutdown_not_initialized(self, sample_endpoint_config):
        """Test shutting down a client that wasn't initialized."""
        # Arrange
        client = OpenAIClient(sample_endpoint_config)
        
        # Act
        result = await client.shutdown()
        
        # Assert
        assert result is True  # Should still return True
    
    @pytest.mark.asyncio
    async def test_send_standard_request(self, sample_endpoint_config, mock_aiohttp_session, sample_response_data):
        """Test sending a standard (non-streaming) request."""
        # Arrange
        mock_session, mock_response = mock_aiohttp_session
        client = OpenAIClient(sample_endpoint_config)
        await client.initialize()
        
        # Set up the mock response
        mock_response.json.return_value = sample_response_data
        
        # Act
        request_data = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}]
        }
        result = await client.send_request(request_data)
        
        # Assert
        assert result["success"] is True
        assert result["status_code"] == 200
        assert result["response"] == sample_response_data
        assert "elapsed_time" in result
        
        # Check that the request was made correctly
        mock_session.return_value.post.assert_called_once_with(
            "https://api.example.com/v1/chat/completions",
            json=request_data,
            timeout=ANY
        )
    
    @pytest.mark.asyncio
    async def test_send_request_custom_endpoint(self, sample_endpoint_config, mock_aiohttp_session):
        """Test sending a request to a custom endpoint."""
        # Arrange
        mock_session, mock_response = mock_aiohttp_session
        client = OpenAIClient(sample_endpoint_config)
        await client.initialize()
        
        # Act
        request_data = {
            "endpoint": "embeddings",
            "model": "text-embedding-ada-002",
            "input": "Hello, world!"
        }
        await client.send_request(request_data)
        
        # Assert - Check the URL used
        mock_session.return_value.post.assert_called_once_with(
            "https://api.example.com/v1/embeddings",
            json={"model": "text-embedding-ada-002", "input": "Hello, world!"},
            timeout=ANY
        )
    
    @pytest.mark.asyncio
    async def test_send_request_not_initialized(self, sample_endpoint_config):
        """Test sending a request when the client is not initialized."""
        # Arrange
        client = OpenAIClient(sample_endpoint_config)
        
        # Act / Assert
        with pytest.raises(RuntimeError, match="Client not initialized"):
            await client.send_request({"model": "gpt-4"})
    
    @pytest.mark.asyncio
    async def test_send_request_error(self, sample_endpoint_config, mock_aiohttp_session):
        """Test error handling when sending a request."""
        # Arrange
        mock_session, _ = mock_aiohttp_session
        client = OpenAIClient(sample_endpoint_config)
        await client.initialize()
        
        # Make post raise an exception
        mock_session.return_value.post.side_effect = Exception("Test error")
        
        # Act
        result = await client.send_request({"model": "gpt-4"})
        
        # Assert
        assert result["success"] is False
        assert "error" in result
        assert "Test error" in result["error"]
        assert "elapsed_time" in result
    
    @pytest.mark.asyncio
    async def test_streaming_request(self, sample_endpoint_config, mock_aiohttp_session):
        """Test sending a streaming request."""
        # Arrange
        mock_session, mock_response = mock_aiohttp_session
        client = OpenAIClient(sample_endpoint_config)
        await client.initialize()
        
        # Set up streaming response
        stream_lines = [
            b'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1699000000,"model":"gpt-4","choices":[{"index":0,"delta":{"role":"assistant"},"finish_reason":null}]}\n\n',
            b'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1699000001,"model":"gpt-4","choices":[{"index":0,"delta":{"content":"This"},"finish_reason":null}]}\n\n',
            b'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1699000002,"model":"gpt-4","choices":[{"index":0,"delta":{"content":" is"},"finish_reason":null}]}\n\n',
            b'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1699000003,"model":"gpt-4","choices":[{"index":0,"delta":{"content":" a"},"finish_reason":null}]}\n\n',
            b'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1699000004,"model":"gpt-4","choices":[{"index":0,"delta":{"content":" test"},"finish_reason":null}]}\n\n',
            b'data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1699000005,"model":"gpt-4","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n',
            b'data: [DONE]\n\n'
        ]
        
        # Mock content iterator
        mock_content = AsyncMock()
        mock_content.__aiter__.return_value = stream_lines
        mock_response.content = mock_content
        
        # Act
        request_data = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True
        }
        result = await client.send_request(request_data)
        
        # Assert
        assert result["success"] is True
        assert result["status_code"] == 200
        assert "response" in result
        assert "chunks" in result["response"]
        assert len(result["response"]["chunks"]) == 6  # Number of chunks (excluding [DONE])
        assert "elapsed_time" in result
        assert "time_to_first_token" in result
        
        # Check that stream was set correctly in the request
        _, kwargs = mock_session.return_value.post.call_args
        assert kwargs["json"]["stream"] is True
    
    @pytest.mark.asyncio
    async def test_streaming_request_error_response(self, sample_endpoint_config, mock_aiohttp_session):
        """Test handling error responses in streaming requests."""
        # Arrange
        mock_session, mock_response = mock_aiohttp_session
        client = OpenAIClient(sample_endpoint_config)
        await client.initialize()
        
        # Set up error response
        mock_response.status = 400
        mock_response.text = AsyncMock(return_value="Invalid request")
        
        # Act
        request_data = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True
        }
        result = await client.send_request(request_data)
        
        # Assert
        assert result["success"] is False
        assert result["status_code"] == 400
        assert result["error"] == "Invalid request"
        assert "elapsed_time" in result
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, sample_endpoint_config, mock_aiohttp_session):
        """Test successful health check."""
        # Arrange
        mock_session, mock_response = mock_aiohttp_session
        client = OpenAIClient(sample_endpoint_config)
        await client.initialize()
        
        # Set up mock response for health check
        mock_response.status = 200
        mock_response.json.return_value = {"status": "ok"}
        
        # We need to set up the GET method for health check
        mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
        
        # Act
        result = await client.health_check()
        
        # Assert
        assert result is True
        
    @pytest.mark.asyncio
    async def test_health_check_failure(self, sample_endpoint_config, mock_aiohttp_session):
        """Test failed health check."""
        # Arrange
        mock_session, mock_response = mock_aiohttp_session
        client = OpenAIClient(sample_endpoint_config)
        await client.initialize()
        
        # Set up mock response for health check
        mock_response.status = 500
        
        # We need to set up the GET method for health check
        mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
        
        # Act
        result = await client.health_check()
        
        # Assert
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_error(self, sample_endpoint_config, mock_aiohttp_session):
        """Test error during health check."""
        # Arrange
        mock_session, _ = mock_aiohttp_session
        client = OpenAIClient(sample_endpoint_config)
        await client.initialize()
        
        # Make get raise an exception
        mock_session.return_value.get.side_effect = Exception("Test error")
        
        # Act
        result = await client.health_check()
        
        # Assert
        assert result is False 