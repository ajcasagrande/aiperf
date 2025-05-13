"""
Tests for the post processor manager service.
"""

import pytest

from aiperf.common.enums import ServiceType
from aiperf.services.post_processor_manager.post_processor_manager import (
    PostProcessorManager,
)
from aiperf.tests.base_test_service import BaseServiceTest


@pytest.mark.asyncio
class TestPostProcessorManager(BaseServiceTest):
    """Tests for the post processor manager service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return PostProcessorManager

    async def test_post_processor_manager_initialization(
        self, initialized_service
    ):
        """Test that the post processor manager initializes correctly."""
        service = initialized_service
        assert service.service_type == ServiceType.POST_PROCESSOR_MANAGER
        # Add post processor manager specific assertions here
