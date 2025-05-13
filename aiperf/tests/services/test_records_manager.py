"""
Tests for the records manager service.
"""

import pytest

from aiperf.common.enums import ServiceType, Topic
from aiperf.services.records_manager.records_manager import RecordsManager
from aiperf.tests.base_test_service import BaseServiceTest
from aiperf.tests.utils.message_mocks import MessageTestUtils


@pytest.mark.asyncio
class TestRecordsManager(BaseServiceTest):
    """Tests for the records manager service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return RecordsManager

    async def test_records_manager_initialization(self, properly_initialized_service):
        """Test that the records manager initializes correctly."""
        service = properly_initialized_service
        assert service.service_type == ServiceType.RECORDS_MANAGER
        # Add records manager specific assertions here

    async def test_handle_command_message(
        self, properly_initialized_service, mock_communication
    ):
        """Test that the records manager handles command messages correctly."""
        service = properly_initialized_service

        # Create a command message using the helper method
        command_msg = await self.create_command_message(service, command="start")

        # Send the message to the service
        await MessageTestUtils.simulate_message_receive(
            service, Topic.COMMAND, command_msg
        )

        # TODO: Implement verification when the records manager is implemented

    async def test_records_manager_specific_functionality(
        self, properly_initialized_service
    ):
        """Test records manager specific functionality."""
        service = properly_initialized_service

        # TODO: Implement records manager specific tests
