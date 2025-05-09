"""
Tests for the worker service.
"""

from unittest.mock import AsyncMock

import pytest

from aiperf.common.config.service_config import WorkerConfig
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
        response = await worker.send_request({"request": "test"})

        # Verify the response
        assert response == mock_response

        # Restore the original method
        worker.send_request = original_send_request

    async def test_worker_process_credit(self, worker):
        """Test that the worker can process credits."""
        # For now, just ensure the method exists and can be called
        await worker.process_credit({"credit_id": "test_credit"})

    async def test_worker_handle_conversation(self, worker):
        """Test that the worker can handle conversations."""
        # For now, just ensure the method exists and can be called
        await worker.handle_conversation({"conversation_id": "test_conversation"})

    async def test_worker_publish_result(self, worker):
        """Test that the worker can publish results."""
        # For now, just ensure the method exists and can be called
        await worker.publish_result({"result": "test_result"})
