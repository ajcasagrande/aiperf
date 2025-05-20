#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
"""
Tests for the worker manager service.
"""

import asyncio
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from aiperf.app.services.worker_manager.worker_manager import (
    WorkerManager,
    WorkerProcess,
)
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceType
from aiperf.common.service.base_service import BaseService
from aiperf.tests.base_test_component_service import BaseTestComponentService
from aiperf.tests.utils.async_test_utils import async_fixture, async_noop


class WorkerManagerTestConfig(BaseModel):
    """Configuration model for worker manager tests."""

    # TODO: Replace this with the actual configuration model once available
    pass


@pytest.mark.asyncio
class TestWorkerManager(BaseTestComponentService):
    """
    Tests for the worker manager service.

    This test class extends BaseTestComponentService to leverage common
    component service tests while adding worker manager specific tests.
    """

    @pytest.fixture
    def service_class(self) -> type[BaseService]:
        """
        Return the worker manager service class for testing.

        Returns:
            The WorkerManager class
        """
        return WorkerManager

    @pytest.fixture
    def service_config(self) -> ServiceConfig:
        """
        Return a worker manager specific configuration for testing.

        Returns:
            ServiceConfig configured for worker manager tests
        """
        return ServiceConfig(
            # Add any worker manager specific configuration here
        )

    @pytest.fixture
    def worker_manager_config(self) -> WorkerManagerTestConfig:
        """
        Return a test configuration for the worker manager.

        Returns:
            WorkerManagerTestConfig with test parameters
        """
        return WorkerManagerTestConfig()

    async def test_worker_manager_initialization(
        self, service_under_test: WorkerManager
    ) -> None:
        """
        Test that the worker manager initializes with the correct attributes.

        Verifies:
        1. The service has the correct service type
        2. The service has the required worker management attributes
        """
        service = await async_fixture(service_under_test)
        assert service.service_type == ServiceType.WORKER_MANAGER
        assert hasattr(service, "workers")
        assert hasattr(service, "cpu_count")
        assert service.cpu_count > 0

    async def test_spawn_multiprocessing_workers(
        self, service_under_test: WorkerManager
    ) -> None:
        """
        Test spawning multiprocessing workers.

        Verifies:
        1. The worker manager creates the correct number of worker processes
        2. The workers are properly configured and started
        """
        service = await async_fixture(service_under_test)

        # Get a reference to the mocked Process class
        from multiprocessing import Process

        # Configure our mock
        mock_process = self.create_safe_mock()
        mock_process.start.return_value = None
        mock_process.pid = 12345

        # Update the mock Process to return our configured mock
        Process.return_value = mock_process

        # Call the worker spawn method
        await service._spawn_multiprocessing_workers()

        # Check that workers were created based on CPU count
        assert len(service.workers) == service.cpu_count

        # Verify the first worker was started correctly
        worker_id = "worker_0"
        assert worker_id in service.workers
        assert isinstance(service.workers[worker_id], WorkerProcess)
        assert service.workers[worker_id].worker_id == worker_id

        # Verify process was started
        assert Process.call_count > 0
        mock_process.start.assert_called()

    async def test_stop_multiprocessing_workers(
        self, service_under_test: WorkerManager
    ) -> None:
        """
        Test stopping multiprocessing workers.

        Verifies:
        1. The worker manager attempts to gracefully terminate workers
        2. Workers that don't terminate in time are forcefully killed
        """
        service = await async_fixture(service_under_test)

        # Create mock workers
        mock_process = self.create_safe_mock()
        mock_process.is_alive.return_value = True
        mock_process.terminate.return_value = None
        mock_process.pid = 12345
        mock_process.kill = MagicMock()

        # Add mock workers to the service
        for i in range(2):
            worker_id = f"worker_{i}"
            service.workers[worker_id] = WorkerProcess(
                worker_id=worker_id, process=mock_process
            )

        # Patch asyncio.to_thread and asyncio.wait_for at the module level
        # to avoid issues with context managers and async code
        original_to_thread = asyncio.to_thread
        original_wait_for = asyncio.wait_for

        asyncio.to_thread = lambda func, *args, **kwargs: async_noop()

        # Make wait_for raise TimeoutError
        async def mock_wait_for(*args, **kwargs):
            raise asyncio.TimeoutError()

        asyncio.wait_for = mock_wait_for

        try:
            # Stop the workers - this should now handle the TimeoutError case
            await service._stop_multiprocessing_workers()

            # Verify workers were terminated and one was killed due to timeout
            assert mock_process.terminate.call_count == 2
            assert mock_process.kill.call_count > 0
        finally:
            # Restore original functions
            asyncio.to_thread = original_to_thread
            asyncio.wait_for = original_wait_for

    async def test_worker_manager_cleanup(
        self, service_under_test: WorkerManager
    ) -> None:
        """
        Test worker manager cleanup functionality.

        Verifies that the cleanup method properly clears the worker registry.
        """
        service = await async_fixture(service_under_test)

        # Use a normal dict without mocks to avoid async issues
        service.workers = {"worker_1": {"some_data": "test"}}

        # Test that the cleanup method clears workers
        await service._cleanup()
        assert len(service.workers) == 0
