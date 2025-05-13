"""
Tests for message models used in the aiperf framework.
"""

import json
import time
import uuid

import pytest
from pydantic import ValidationError

from aiperf.common.enums import (
    ServiceType,
    MessageType,
    CommandType,
    PayloadType,
    ServiceState,
)
from aiperf.common.models.messages import (
    BaseMessage,
    StatusMessage,
    HeartbeatMessage,
    CommandMessage,
    ResponsePayload,
    CreditData,
    ConversationTurn,
    ConversationData,
    ResultData,
)


class TestBaseMessage:
    """Tests for the BaseMessage class."""

    def test_base_message_creation(self):
        """Test that a BaseMessage can be created with required fields."""
        message = BaseMessage(
            service_id="test-service",
            service_type=ServiceType.TEST,
        )

        assert message.service_id == "test-service"
        assert message.service_type == ServiceType.TEST
        assert isinstance(message.timestamp, float)

    def test_base_message_validation(self):
        """Test that validation works for BaseMessage."""
        # Missing required fields should raise ValidationError
        with pytest.raises(ValidationError):
            BaseMessage()

        with pytest.raises(ValidationError):
            BaseMessage(service_id="test-service")

        with pytest.raises(ValidationError):
            BaseMessage(service_type=ServiceType.TEST)

    def test_base_message_from_dict(self):
        """Test creating a BaseMessage from a dictionary."""
        data = {
            "service_id": "test-service",
            "service_type": ServiceType.TEST,
            "timestamp": time.time(),
        }

        message = BaseMessage.model_validate(data)

        assert message.service_id == data["service_id"]
        assert message.service_type == data["service_type"]
        assert message.timestamp == data["timestamp"]

    def test_base_message_to_dict(self):
        """Test converting a BaseMessage to a dictionary."""
        message = BaseMessage(
            service_id="test-service",
            service_type=ServiceType.TEST,
            timestamp=123456789.0,
        )

        data = message.model_dump()

        assert data["service_id"] == "test-service"
        assert data["service_type"] == ServiceType.TEST
        assert data["timestamp"] == 123456789.0


class TestStatusMessage:
    """Tests for the StatusMessage class."""

    def test_status_message_creation(self):
        """Test that a StatusMessage can be created with required fields."""
        message = StatusMessage(
            service_id="test-service",
            service_type=ServiceType.TEST,
            state=ServiceState.RUNNING,
        )

        assert message.service_id == "test-service"
        assert message.service_type == ServiceType.TEST
        assert message.state == ServiceState.RUNNING
        assert message.message_type == MessageType.STATUS

    def test_status_message_inheritance(self):
        """Test that StatusMessage inherits correctly from BaseMessage."""
        message = StatusMessage(
            service_id="test-service",
            service_type=ServiceType.TEST,
            state=ServiceState.RUNNING,
        )

        assert isinstance(message, BaseMessage)


class TestHeartbeatMessage:
    """Tests for the HeartbeatMessage class."""

    def test_heartbeat_message_creation(self):
        """Test that a HeartbeatMessage can be created with required fields."""
        message = HeartbeatMessage(
            service_id="test-service",
            service_type=ServiceType.TEST,
        )

        assert message.service_id == "test-service"
        assert message.service_type == ServiceType.TEST
        assert message.message_type == MessageType.HEARTBEAT
        assert message.state == ServiceState.RUNNING

    def test_heartbeat_message_inheritance(self):
        """Test that HeartbeatMessage inherits correctly from StatusMessage."""
        message = HeartbeatMessage(
            service_id="test-service",
            service_type=ServiceType.TEST,
        )

        assert isinstance(message, StatusMessage)
        assert isinstance(message, BaseMessage)


class TestCommandMessage:
    """Tests for the CommandMessage class."""

    def test_command_message_creation(self):
        """Test that a CommandMessage can be created with required fields."""
        command_id = str(uuid.uuid4())
        message = CommandMessage(
            service_id="test-service",
            service_type=ServiceType.TEST,
            command_id=command_id,
            command=CommandType.START,
            target_service_id="target-service",
        )

        assert message.service_id == "test-service"
        assert message.service_type == ServiceType.TEST
        assert message.command_id == command_id
        assert message.command == CommandType.START
        assert message.target_service_id == "target-service"
        assert message.message_type == MessageType.COMMAND
        assert message.require_response is False
        assert message.payload is None

    def test_command_message_factory_method(self):
        """Test the factory method for creating CommandMessages."""
        command_id = "test-command-id"
        message = CommandMessage.create(
            service_id="test-service",
            service_type=ServiceType.TEST,
            command_id=command_id,
            command_type=CommandType.START,
            target_service_id="target-service",
            require_response=True,
        )

        assert message.service_id == "test-service"
        assert message.service_type == ServiceType.TEST
        assert message.command_id == command_id
        assert message.command == CommandType.START
        assert message.target_service_id == "target-service"
        assert message.require_response is True


class TestPayloadModels:
    """Tests for various payload models."""

    def test_response_payload(self):
        """Test the ResponsePayload model."""
        payload = ResponsePayload(
            status="ok",
            message="Success",
            data={"result": 42},
        )

        assert payload.payload_type == PayloadType.RESPONSE
        assert payload.status == "ok"
        assert payload.message == "Success"
        assert payload.data == {"result": 42}

    def test_credit_data(self):
        """Test the CreditData model."""
        payload = CreditData(
            credit_id="credit-123",
            request_count=5,
            expiry_time=time.time() + 3600,
            parameters={"limit": 100},
        )

        assert payload.payload_type == PayloadType.CREDIT
        assert payload.credit_id == "credit-123"
        assert payload.request_count == 5
        assert payload.parameters == {"limit": 100}

    def test_conversation_data(self):
        """Test the ConversationData model."""
        turns = [
            ConversationTurn(role="user", content="Hello"),
            ConversationTurn(role="assistant", content="Hi there"),
        ]

        payload = ConversationData(
            conversation_id="conv-123",
            turns=turns,
        )

        assert payload.payload_type == PayloadType.CONVERSATION
        assert payload.conversation_id == "conv-123"
        assert len(payload.turns) == 2
        assert payload.turns[0].role == "user"
        assert payload.turns[1].role == "assistant"

    def test_result_data(self):
        """Test the ResultData model."""
        payload = ResultData(
            result_id="result-123",
            metrics={"accuracy": 0.95, "latency": 25.5},
            tags=["test", "evaluation"],
        )

        assert payload.payload_type == PayloadType.RESULT
        assert payload.result_id == "result-123"
        assert payload.metrics["accuracy"] == 0.95
        assert payload.metrics["latency"] == 25.5
        assert "test" in payload.tags
        assert "evaluation" in payload.tags


class TestMessageSerialization:
    """Tests for message serialization/deserialization."""

    def test_message_to_json(self):
        """Test converting messages to JSON."""
        message = StatusMessage(
            service_id="test-service",
            service_type=ServiceType.TEST,
            state=ServiceState.RUNNING,
            timestamp=123456789.0,
        )

        json_str = message.model_dump_json()
        data = json.loads(json_str)

        assert data["service_id"] == "test-service"
        assert data["service_type"] == "test_service"  # enum serializes to its value
        assert data["state"] == "running"  # enum serializes to its value
        assert data["timestamp"] == 123456789.0
        assert data["message_type"] == "status"

    def test_message_from_json(self):
        """Test creating messages from JSON."""
        json_str = """
        {
            "service_id": "test-service",
            "service_type": "test_service",
            "state": "running",
            "timestamp": 123456789.0,
            "message_type": "status"
        }
        """

        message = StatusMessage.model_validate_json(json_str)

        assert message.service_id == "test-service"
        assert message.service_type == ServiceType.TEST
        assert message.state == ServiceState.RUNNING
        assert message.timestamp == 123456789.0
        assert message.message_type == MessageType.STATUS
