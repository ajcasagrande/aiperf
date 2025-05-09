"""
Tests for the post processor manager service.
"""

import pytest

from aiperf.common.enums import ServiceType, Topic
from aiperf.services.post_processor_manager.main import PostProcessorManager
from aiperf.tests.base_test_service import BaseServiceTest, async_fixture
from aiperf.tests.utils.message_mocks import MessageTestUtils


@pytest.mark.asyncio
class TestPostProcessorManager(BaseServiceTest):
    """Tests for the post processor manager service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return PostProcessorManager

    async def test_post_processor_manager_initialization(self, service_under_test):
        """Test that the post processor manager initializes correctly."""
        service = await async_fixture(service_under_test)
        assert service.service_type == ServiceType.POST_PROCESSOR_MANAGER
        # Add post processor manager specific assertions here

    async def test_handle_command_message(
        self, properly_initialized_service, mock_communication
    ):
        """Test that the post processor manager handles command messages correctly."""
        service = properly_initialized_service

        # Create a command message using the helper method
        command_msg = await self.create_command_message(service, command="start")

        # Send the message to the service
        await MessageTestUtils.simulate_message_receive(
            service, Topic.COMMAND, command_msg
        )

        # TODO: Implement verification when the post processor manager is implemented

    async def test_post_processor_manager_specific_functionality(
        self, properly_initialized_service
    ):
        """Test post processor manager specific functionality."""
        service = properly_initialized_service

        # TODO: Implement post processor manager specific tests
