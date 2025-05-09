"""
Tests for the timing manager service.
"""

import pytest

from aiperf.common.enums import ServiceType, Topic
from aiperf.services.timing_manager.main import TimingManager
from aiperf.tests.base_test_service import BaseServiceTest
from aiperf.tests.utils.message_mocks import MessageTestUtils


@pytest.mark.asyncio
class TestTimingManager(BaseServiceTest):
    """Tests for the timing manager service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return TimingManager

    async def test_timing_manager_initialization(self, service_under_test):
        """Test that the timing manager initializes correctly."""
        service = service_under_test
        assert service.service_type == ServiceType.TIMING_MANAGER
        # Add timing manager specific assertions here

    async def test_handle_command_message(
        self, properly_initialized_service, mock_communication
    ):
        """Test that the timing manager handles command messages correctly."""
        service = properly_initialized_service

        # Create a command message using the helper method
        command_msg = await self.create_command_message(service, command="start")

        # Send the message to the service
        await MessageTestUtils.simulate_message_receive(
            service, Topic.COMMAND, command_msg
        )

        # TODO: Implement verification when the timing manager is implemented

    async def test_timing_manager_specific_functionality(
        self, properly_initialized_service
    ):
        """Test timing manager specific functionality."""
        service = properly_initialized_service

        # TODO: Implement timing manager specific tests
