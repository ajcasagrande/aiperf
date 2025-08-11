# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import AsyncMock, patch

import pytest

from aiperf.common.config import EndpointConfig, LoadGeneratorConfig
from aiperf.common.enums import ServiceType
from aiperf.common.messages import ShutdownWorkersCommand, SpawnWorkersCommand
from aiperf.workers.worker_manager import WorkerManager
from tests.workers.conftest import WorkerTestBase


class TestWorkerManager(WorkerTestBase):
    """Test the WorkerManager service functionality."""

    @pytest.fixture
    def worker_manager_service(
        self,
        worker_service_config,
        mock_communication_factory,
    ):
        """Create a WorkerManager instance with mocked dependencies."""
        from aiperf.common.config import UserConfig

        user_config = UserConfig(
            loadgen=LoadGeneratorConfig(concurrency=1),
            endpoint=EndpointConfig(model_names=["test-model"]),
        )

        with patch("multiprocessing.cpu_count", return_value=8):
            manager = WorkerManager(
                service_config=worker_service_config,
                user_config=user_config,
                service_id="test-worker-manager",
            )

            # Mock communication methods
            manager.send_command_and_wait_for_response = AsyncMock()
            manager.publish = AsyncMock()

            return manager

    def test_worker_manager_service_type_registration(self):
        """Test that WorkerManager is properly registered with ServiceFactory."""
        from aiperf.common.factories import ServiceFactory

        service_class = ServiceFactory.get_class_from_type(ServiceType.WORKER_MANAGER)
        assert service_class == WorkerManager

    def test_worker_manager_initialization(self, worker_manager_service):
        """Test worker manager initializes with correct attributes."""
        manager = worker_manager_service

        self.assert_service_initialized(manager)
        self.assert_communication_setup(manager)

        # Test WorkerManager-specific attributes
        assert manager.service_id == "test-worker-manager"
        assert isinstance(manager.workers, dict)
        assert isinstance(manager.worker_health, dict)
        assert manager.cpu_count == 8
        assert manager.max_workers >= 1

    def test_worker_count_calculation(self, mock_communication_factory):
        """Test worker count calculation with different configurations."""
        from aiperf.common.config import ServiceConfig, UserConfig, WorkersConfig

        service_config = ServiceConfig(
            workers=WorkersConfig(health_check_interval=1.0, max=4, min=1)
        )
        user_config = UserConfig(
            loadgen=LoadGeneratorConfig(concurrency=10),
            endpoint=EndpointConfig(model_names=["test-model"]),
        )

        with patch("multiprocessing.cpu_count", return_value=8):
            manager = WorkerManager(
                service_config=service_config,
                user_config=user_config,
                service_id="test-manager",
            )

            assert manager.max_workers == 4  # Limited by config max

    @pytest.mark.asyncio
    async def test_start_spawns_workers(self, worker_manager_service):
        """Test that start method spawns initial workers."""
        manager = worker_manager_service

        await manager.initialize()
        await manager.start()

        manager.send_command_and_wait_for_response.assert_called_once()
        call_args = manager.send_command_and_wait_for_response.call_args[0][0]

        assert isinstance(call_args, SpawnWorkersCommand)
        assert call_args.service_id == "test-worker-manager"

    @pytest.mark.asyncio
    async def test_stop_shuts_down_workers(self, worker_manager_service):
        """Test that stop method shuts down all workers."""
        manager = worker_manager_service

        await manager.stop()

        manager.publish.assert_called_once()
        call_args = manager.publish.call_args[0][0]

        assert isinstance(call_args, ShutdownWorkersCommand)
        assert call_args.service_id == "test-worker-manager"
        assert call_args.all_workers is True

    @pytest.mark.asyncio
    async def test_worker_health_message_handling(
        self,
        worker_manager_service,
        sample_worker_health_message,
    ):
        """Test that worker health messages are properly stored."""
        manager = worker_manager_service

        await manager._on_worker_health(sample_worker_health_message)

        assert "worker-123" in manager.worker_health
        assert manager.worker_health["worker-123"] == sample_worker_health_message
