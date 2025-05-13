"""
Tests for the dataset manager service.
"""

import pytest

from aiperf.common.enums import ServiceType
from aiperf.services.dataset_manager.dataset_manager import DatasetManager
from aiperf.tests.base_test_service import BaseServiceTest


@pytest.mark.asyncio
class TestDatasetManager(BaseServiceTest):
    """Tests for the dataset manager service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return DatasetManager

    async def test_dataset_manager_initialization(self, initialized_service):
        """Test that the dataset manager initializes correctly."""
        service = initialized_service
        assert service.service_type == ServiceType.DATASET_MANAGER
        # Add dataset manager specific assertions here
