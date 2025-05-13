"""
Tests for the records manager service.
"""

import pytest

from aiperf.common.enums import ServiceType
from aiperf.services.records_manager.records_manager import RecordsManager
from aiperf.tests.base_test_service import BaseServiceTest


@pytest.mark.asyncio
class TestRecordsManager(BaseServiceTest):
    """Tests for the records manager service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return RecordsManager

    async def test_records_manager_initialization(self, initialized_service):
        """Test that the records manager initializes correctly."""
        service = initialized_service
        assert service.service_type == ServiceType.RECORDS_MANAGER
        # Add records manager specific assertions here
