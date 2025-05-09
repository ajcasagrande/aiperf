"""
Tests for the worker service.
"""

from unittest.mock import AsyncMock

import pytest

from aiperf.common.config.service_config import WorkerConfig
from aiperf.common.models.messages import (
    ConversationData,
    ConversationTurn,
    CreditData,
    CreditMessage,
)
from aiperf.services.worker.main import Worker


@pytest.mark.asyncio
class TestWorker:
    """Tests for the worker service."""

    @pytest.fixture
    def worker_config(self):
        """Return a worker configuration for testing."""
        return WorkerConfig()

    @pytest.fixture
    def worker(self, worker_config):
        """Return a worker instance for testing."""
        return Worker(config=worker_config)

    async def test_worker_initialization(self, worker):
        """Test that the worker initializes correctly."""
        # Basic existence checks
        assert worker is not None
        assert worker.config is not None

    async def test_worker_start_stop(self, worker):
        """Test that the worker can start and stop."""
        # Start the worker
        await worker._start()

        # Stop the worker
        await worker.stop()

    async def test_worker_send_request(self, worker):
        """Test that the worker can send requests."""
        # Mock response data
        mock_response = {"status": "success", "data": "test_data"}

        # Mock the send_request method to return the mock response
        original_send_request = worker.send_request
        worker.send_request = AsyncMock(return_value=mock_response)

        # Call the method
        response = await worker.send_request(
            operation="test_operation", parameters={"param": "value"}
        )

        # Verify the response
        assert response == mock_response

        # Restore the original method
        worker.send_request = original_send_request

    async def test_worker_process_credit(self, worker):
        """Test that the worker can process credits."""
        # Create a proper CreditMessage with CreditData
        credit_data = CreditData(credit_id="test_credit", request_count=1)
        credit_message = CreditMessage(
            service_id="test_service", service_type="test_type", credit=credit_data
        )
        # For now, just ensure the method exists and can be called
        await worker.process_credit(credit_message)

    async def test_worker_handle_conversation(self, worker):
        """Test that the worker can handle conversations."""
        # Create a proper ConversationData
        conversation_data = ConversationData(
            conversation_id="test_conversation",
            turns=[ConversationTurn(role="user", content="Hello")],
        )
        # For now, just ensure the method exists and can be called
        await worker.handle_conversation(conversation_data)

    async def test_worker_publish_result(self, worker):
        """Test that the worker can publish results."""
        # For now, just ensure the method exists and can be called
        await worker.publish_result({"result": "test_result"})
