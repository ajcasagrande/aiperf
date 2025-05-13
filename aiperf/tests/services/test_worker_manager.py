"""
Tests for the worker manager service.
"""

import asyncio
from unittest.mock import patch, MagicMock

import pytest

from aiperf.common.enums import ServiceType, Topic
from aiperf.services.worker_manager.worker_manager import WorkerManager, WorkerProcess
from aiperf.tests.base_test_service import BaseServiceTest
from aiperf.tests.utils.message_mocks import MessageTestUtils


@pytest.mark.asyncio
class TestWorkerManager(BaseServiceTest):
    """Tests for the worker manager service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return WorkerManager

    async def test_worker_manager_initialization(self, initialized_service):
        """Test that the worker manager initializes correctly."""
        service = initialized_service
        assert service.service_type == ServiceType.WORKER_MANAGER
        assert hasattr(service, "workers")
        assert hasattr(service, "cpu_count")
        assert service.cpu_count > 0

    async def test_handle_command_message(
        self, initialized_service, mock_communication
    ):
        """Test that the worker manager handles command messages correctly."""
        service = initialized_service

        # Create a command message using the helper method
        command_msg = await self.create_command_message(service, command="start")

        # Use patch to mock _process_command_message for cleaner testing
        with patch.object(
            service, "_process_command_message", autospec=True
        ) as mock_process:
            # Set up the mock to return successfully
            mock_process.return_value = None

            # Send the message to the service
            await MessageTestUtils.simulate_message_receive(
                service, Topic.COMMAND, command_msg
            )

            # Verify the method was called with our message
            mock_process.assert_called_once_with(command_msg)

    async def test_worker_spawn_methods_exist(self, initialized_service):
        """Test that worker spawn methods exist and are callable."""
        service = initialized_service

        # Verify the required worker management methods exist
        assert hasattr(service, "_spawn_multiprocessing_workers")
        assert callable(service._spawn_multiprocessing_workers)
        assert hasattr(service, "_stop_multiprocessing_workers")
        assert callable(service._stop_multiprocessing_workers)

    async def test_spawn_multiprocessing_workers(self, initialized_service):
        """Test spawning multiprocessing workers."""
        service = initialized_service

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
            worker_id = f"worker_0"
            assert worker_id in service.workers
            assert isinstance(service.workers[worker_id], WorkerProcess)
            assert service.workers[worker_id].worker_id == worker_id

            # Verify process was started
            mock_process.start.assert_called()

    async def test_stop_multiprocessing_workers(self, initialized_service):
        """Test stopping multiprocessing workers."""
        service = initialized_service

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

        # Mock asyncio.to_thread and wait_for to prevent actual waiting
        future = asyncio.Future()
        future.set_result(None)

        with (
            patch("asyncio.to_thread", return_value=future),
            patch("asyncio.wait_for", side_effect=asyncio.TimeoutError),
        ):
            # Stop the workers - this should now handle the TimeoutError case
            await service._stop_multiprocessing_workers()

            # Verify workers were terminated and one was killed due to timeout
            assert mock_process.terminate.call_count == 2
            assert mock_process.kill.call_count > 0

    async def test_worker_manager_specific_functionality(
        self, initialized_service
    ):
        """Test worker manager specific functionality."""
        service = initialized_service

        # Use a normal dict without mocks to avoid async issues
        service.workers = {"worker_1": {"some_data": "test"}}

        # Test that the cleanup method clears workers
        await service._cleanup()
        assert len(service.workers) == 0
