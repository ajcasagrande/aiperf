import pytest
from unittest.mock import patch, MagicMock

from aiperf.common.communication_factory import CommunicationFactory
from aiperf.common.communication import Communication
from aiperf.common.memory_communication import MemoryCommunication
from aiperf.common.zmq_communication import ZMQCommunication


class TestCommunicationFactory:
    """Tests for the CommunicationFactory class."""
    
    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset the communication type registry before and after each test."""
        # Save original registry
        original_registry = CommunicationFactory._comm_types.copy()
        
        # Reset to default state
        CommunicationFactory._comm_types = {
            "memory": MemoryCommunication,
            "zmq": ZMQCommunication,
        }
        
        yield
        
        # Restore original registry
        CommunicationFactory._comm_types = original_registry
    
    def test_create_memory_communication(self):
        """Test creating a memory communication instance."""
        # Act
        comm = CommunicationFactory.create_communication("memory", client_id="test_client")
        
        # Assert
        assert isinstance(comm, MemoryCommunication)
        assert comm.client_id == "test_client"
    
    def test_create_zmq_communication(self):
        """Test creating a ZMQ communication instance."""
        # Act
        comm = CommunicationFactory.create_communication(
            "zmq",
            client_id="test_client",
            pub_address="tcp://localhost:5555",
            sub_address="tcp://localhost:5556"
        )
        
        # Assert
        assert isinstance(comm, ZMQCommunication)
        assert comm.client_id == "test_client"
        assert comm.pub_address == "tcp://localhost:5555"
        assert comm.sub_address == "tcp://localhost:5556"
    
    def test_create_unknown_communication_type(self):
        """Test creating an unknown communication type."""
        # Act
        comm = CommunicationFactory.create_communication("unknown")
        
        # Assert
        assert comm is None
    
    def test_create_communication_with_error(self):
        """Test creating a communication instance that raises an error."""
        # Arrange
        with patch.object(MemoryCommunication, "__init__", side_effect=Exception("Test error")):
            # Act
            comm = CommunicationFactory.create_communication("memory")
            
            # Assert
            assert comm is None
    
    def test_register_comm_type(self):
        """Test registering a new communication type."""
        # Arrange
        class TestCommunication(Communication):
            async def initialize(self): pass
            async def shutdown(self): pass
            async def publish(self, topic, message): pass
            async def subscribe(self, topic, callback): pass
            async def request(self, target, request, timeout=5.0): pass
            async def respond(self, target, response): pass
        
        # Act
        CommunicationFactory.register_comm_type("test", TestCommunication)
        
        # Assert
        assert "test" in CommunicationFactory._comm_types
        assert CommunicationFactory._comm_types["test"] == TestCommunication
        
        # Verify we can create an instance
        comm = CommunicationFactory.create_communication("test")
        assert isinstance(comm, TestCommunication)
    
    def test_register_duplicate_comm_type(self):
        """Test registering a duplicate communication type."""
        # Arrange
        class TestCommunication(Communication):
            async def initialize(self): pass
            async def shutdown(self): pass
            async def publish(self, topic, message): pass
            async def subscribe(self, topic, callback): pass
            async def request(self, target, request, timeout=5.0): pass
            async def respond(self, target, response): pass
        
        # Act
        CommunicationFactory.register_comm_type("memory", TestCommunication)
        
        # Assert
        assert CommunicationFactory._comm_types["memory"] == TestCommunication
        assert CommunicationFactory._comm_types["memory"] != MemoryCommunication
    
    @pytest.mark.parametrize("comm_type,expected_class", [
        ("memory", MemoryCommunication),
        ("zmq", ZMQCommunication),
    ])
    def test_create_different_communication_types(self, comm_type, expected_class):
        """Test creating different communication types."""
        # Act
        comm = CommunicationFactory.create_communication(comm_type)
        
        # Assert
        assert isinstance(comm, expected_class)
    
    def test_create_communication_with_kwargs(self):
        """Test creating a communication instance with different kwargs."""
        # Arrange
        kwargs = {
            "client_id": "test_client",
            "pub_address": "tcp://localhost:5555",
            "sub_address": "tcp://localhost:5556",
            "req_address": "tcp://localhost:5557",
            "rep_address": "tcp://localhost:5558"
        }
        
        # Act
        comm = CommunicationFactory.create_communication("zmq", **kwargs)
        
        # Assert
        assert isinstance(comm, ZMQCommunication)
        assert comm.client_id == kwargs["client_id"]
        assert comm.pub_address == kwargs["pub_address"]
        assert comm.sub_address == kwargs["sub_address"]
        assert comm.req_address == kwargs["req_address"]
        assert comm.rep_address == kwargs["rep_address"] 