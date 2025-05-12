"""
Tests for the worker manager service.
"""

import pytest

from aiperf.common.enums import ServiceType, Topic
from aiperf.services.worker_manager.main import WorkerManager
from aiperf.tests.base_test_service import BaseServiceTest, async_fixture
from aiperf.tests.utils.message_mocks import MessageTestUtils


@pytest.mark.asyncio
class TestWorkerManager(BaseServiceTest):
    """Tests for the worker manager service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return WorkerManager

    async def test_worker_manager_initialization(self, properly_initialized_service):
        """Test that the worker manager initializes correctly."""
        service = properly_initialized_service
        assert service.service_type == ServiceType.WORKER_MANAGER
        # Add worker manager specific assertions here

    async def test_handle_command_message(
        self, properly_initialized_service, mock_communication
    ):
        """Test that the worker manager handles command messages correctly."""
        service = properly_initialized_service

        # Create a command message using the helper method
        command_msg = await self.create_command_message(service, command="start")

        # Send the message to the service
        await MessageTestUtils.simulate_message_receive(
            service, Topic.COMMAND, command_msg
        )

        # TODO: Implement verification when the worker manager is implemented

    async def test_worker_manager_specific_functionality(
        self, properly_initialized_service
    ):
        """Test worker manager specific functionality."""
        service = properly_initialized_service

        # TODO: Implement worker manager specific tests
