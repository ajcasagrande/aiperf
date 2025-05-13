"""
Tests for the post processor manager service.
"""

import pytest

from aiperf.common.enums import ServiceType
from aiperf.services.post_processor_manager.post_processor_manager import (
    PostProcessorManager,
)
from aiperf.tests.base_test_service import BaseServiceTest, async_fixture


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
