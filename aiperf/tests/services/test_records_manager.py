"""
Tests for the records manager service.
"""

import pytest

from aiperf.common.enums import ServiceType
from aiperf.services.records_manager.records_manager import RecordsManager
from aiperf.tests.base_test_service import BaseServiceTest, async_fixture


@pytest.mark.asyncio
class TestRecordsManager(BaseServiceTest):
    """Tests for the records manager service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return RecordsManager

    async def test_records_manager_initialization(self, service_under_test):
        """Test that the records manager initializes correctly."""
        service = await async_fixture(service_under_test)

        assert service.service_type == ServiceType.RECORDS_MANAGER
        # Add records manager specific assertions here
