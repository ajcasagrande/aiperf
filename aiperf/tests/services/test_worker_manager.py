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
from unittest.mock import MagicMock, patch

import pytest

from aiperf.app.services.worker_manager.worker_manager import (
    WorkerManager,
    WorkerProcess,
)
from aiperf.common.enums import ServiceType
from aiperf.tests.base_test_component_service import BaseTestComponentService
from aiperf.tests.utils.async_test_utils import async_fixture, async_noop


@pytest.mark.asyncio
class TestWorkerManager(BaseTestComponentService):
    """Tests for the worker manager service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return WorkerManager

    async def test_worker_manager_initialization(self, service_under_test):
        """Test that the worker manager initializes correctly."""
        service = await async_fixture(service_under_test)
        assert service.service_type == ServiceType.WORKER_MANAGER
        assert hasattr(service, "workers")
        assert hasattr(service, "cpu_count")
        assert service.cpu_count > 0

    async def test_spawn_multiprocessing_workers(self, service_under_test):
        """Test spawning multiprocessing workers."""
        service = await async_fixture(service_under_test)

        # Mock the multiprocessing.Process
        mock_process = self.create_safe_mock()
        mock_process.start.return_value = None
        mock_process.pid = 12345

        with patch("multiprocessing.Process", return_value=mock_process):
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
            mock_process.start.assert_called()

    async def test_stop_multiprocessing_workers(self, service_under_test):
        """Test stopping multiprocessing workers."""
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

        with (
            patch("asyncio.to_thread", return_value=async_noop),
            patch("asyncio.wait_for", side_effect=asyncio.TimeoutError),
        ):
            # Stop the workers - this should now handle the TimeoutError case
            await service._stop_multiprocessing_workers()

            # Verify workers were terminated and one was killed due to timeout
            assert mock_process.terminate.call_count == 2
            assert mock_process.kill.call_count > 0

    async def test_worker_manager_specific_functionality(self, service_under_test):
        """Test worker manager specific functionality."""
        service = await async_fixture(service_under_test)

        # Use a normal dict without mocks to avoid async issues
        service.workers = {"worker_1": {"some_data": "test"}}

        # Test that the cleanup method clears workers
        await service._cleanup()
        assert len(service.workers) == 0
