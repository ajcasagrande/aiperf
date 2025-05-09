"""
Tests for the dataset manager service.
"""

import pytest

from aiperf.common.enums import ServiceType, Topic
from aiperf.services.dataset_manager.main import DatasetManager
from aiperf.tests.base_test_service import BaseServiceTest
from aiperf.tests.utils.message_mocks import MessageTestUtils


@pytest.mark.asyncio
class TestDatasetManager(BaseServiceTest):
    """Tests for the dataset manager service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return DatasetManager

    async def test_dataset_manager_initialization(self, service_under_test):
        """Test that the dataset manager initializes correctly."""
        service = service_under_test
        assert service.service_type == ServiceType.DATASET_MANAGER
        # Add dataset manager specific assertions here

    async def test_handle_command_message(
        self, properly_initialized_service, mock_communication
    ):
        """Test that the dataset manager handles command messages correctly."""
        service = properly_initialized_service

        # Create a command message using the helper method
        command_msg = await self.create_command_message(service, command="start")

        # Send the message to the service
        await MessageTestUtils.simulate_message_receive(
            service, Topic.COMMAND, command_msg
        )

        # TODO: Implement verification when the dataset manager is implemented

    async def test_dataset_manager_specific_functionality(
        self, properly_initialized_service
    ):
        """Test dataset manager specific functionality."""
        service = properly_initialized_service

        # TODO: Implement dataset manager specific tests
