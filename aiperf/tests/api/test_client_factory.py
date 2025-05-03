import pytest
from unittest.mock import patch, MagicMock

from aiperf.api.client_factory import ClientFactory
from aiperf.api.base_client import BaseClient
from aiperf.api.openai_client import OpenAIClient
from aiperf.config.config_models import EndpointConfig


class TestClientFactory:
    """Tests for the ClientFactory class."""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the client type registry before and after each test."""
        # Save original registry
        original_registry = ClientFactory._client_types.copy()
        
        # Reset to default state
        ClientFactory._client_types = {
            "openai": OpenAIClient,
        }
        
        yield
        
        # Restore original registry
        ClientFactory._client_types = original_registry
    
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
    
    def test_create_openai_client(self, sample_endpoint_config):
        """Test creating an OpenAI client."""
        # Act
        client = ClientFactory.create_client(sample_endpoint_config)
        
        # Assert
        assert isinstance(client, OpenAIClient)
        assert client.config == sample_endpoint_config
        assert client.url == sample_endpoint_config.url
        assert "Authorization" in client.headers
        assert client.headers["Authorization"] == "Bearer test-api-key"
    
    def test_create_unknown_client_type(self):
        """Test creating a client with an unknown API type."""
        # Arrange
        config = EndpointConfig(
            name="test-endpoint",
            url="https://api.example.com/v1/",
            api_type="unknown",
            headers={}
        )
        
        # Act
        client = ClientFactory.create_client(config)
        
        # Assert
        assert client is None
    
    def test_create_client_with_error(self, sample_endpoint_config):
        """Test creating a client that raises an error."""
        # Arrange
        with patch.object(OpenAIClient, "__init__", side_effect=Exception("Test error")):
            # Act
            client = ClientFactory.create_client(sample_endpoint_config)
            
            # Assert
            assert client is None
    
    def test_register_client_type(self, sample_endpoint_config):
        """Test registering a new client type."""
        # Arrange
        class TestClient(BaseClient):
            def __init__(self, config): 
                self.config = config
                
            async def initialize(self): pass
            async def shutdown(self): pass
            async def send_request(self, request_data): pass
            async def health_check(self): pass
        
        # Act
        ClientFactory.register_client_type("test", TestClient)
        
        # Assert
        assert "test" in ClientFactory._client_types
        assert ClientFactory._client_types["test"] == TestClient
        
        # Verify we can create an instance
        config = EndpointConfig(
            name="test-endpoint",
            url="https://api.example.com/v1/",
            api_type="test",
            headers={}
        )
        client = ClientFactory.create_client(config)
        assert isinstance(client, TestClient)
    
    def test_register_duplicate_client_type(self):
        """Test registering a duplicate client type."""
        # Arrange
        class TestClient(BaseClient):
            def __init__(self, config): 
                self.config = config
                
            async def initialize(self): pass
            async def shutdown(self): pass
            async def send_request(self, request_data): pass
            async def health_check(self): pass
        
        # Act
        ClientFactory.register_client_type("openai", TestClient)
        
        # Assert
        assert ClientFactory._client_types["openai"] == TestClient
        assert ClientFactory._client_types["openai"] != OpenAIClient
    
    @pytest.mark.parametrize("api_type,expected_type", [
        ("openai", OpenAIClient),
        ("OPENAI", OpenAIClient),  # Case insensitive
        ("OpenAI", OpenAIClient),  # Mixed case
    ])
    def test_case_insensitive_api_type(self, api_type, expected_type):
        """Test that API type is case insensitive."""
        # Arrange
        config = EndpointConfig(
            name="test-endpoint",
            url="https://api.example.com/v1/",
            api_type=api_type,
            headers={}
        )
        
        # Act
        client = ClientFactory.create_client(config)
        
        # Assert
        assert isinstance(client, expected_type)
    
    def test_create_client_without_auth(self):
        """Test creating a client without authentication."""
        # Arrange
        config = EndpointConfig(
            name="test-endpoint",
            url="https://api.example.com/v1/",
            api_type="openai",
            headers={}
        )
        
        # Act
        client = ClientFactory.create_client(config)
        
        # Assert
        assert isinstance(client, OpenAIClient)
        assert "Authorization" not in client.headers 