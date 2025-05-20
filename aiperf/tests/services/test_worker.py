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
Tests for the worker service.
"""

from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from aiperf.app.services.worker.worker import Worker
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceState
from aiperf.common.service.base_service import BaseService
from aiperf.tests.base_test_service import BaseTestService
from aiperf.tests.utils.async_test_utils import async_fixture


class WorkerTestConfig(BaseModel):
    """
    Test configuration for the workers.
    """

    # TODO: Replace this with the actual configuration model once available
    pass


@pytest.mark.asyncio
class TestWorker(BaseTestService):
    """
    Tests for the worker service.

    This test class extends BaseTestService since Worker is a direct subclass
    of BaseService, not a BaseComponentService.
    """

    @pytest.fixture
    def service_class(self) -> type[BaseService]:
        """
        Return the worker service class for testing.

        Returns:
            The Worker class
        """
        return Worker

    @pytest.fixture
    def service_config(self) -> ServiceConfig:
        """
        Return a worker-specific service configuration for testing.

        Returns:
            ServiceConfig configured for worker tests
        """
        return ServiceConfig(
            # Add any worker-specific configuration here
        )

    @pytest.fixture
    def worker_config(self) -> WorkerTestConfig:
        """
        Return a test configuration for the worker.

        Returns:
            WorkerTestConfig with test parameters
        """
        return WorkerTestConfig()

    @pytest.fixture
    def worker_instance(
        self, service_config: ServiceConfig, mock_communication: AsyncMock
    ) -> Worker:
        """
        Return a worker instance for testing that hasn't been initialized.

        This is separate from the fixtures provided by the base class to allow
        for worker-specific setup.

        Returns:
            An uninitialized Worker instance
        """
        worker = Worker(service_config=service_config)
        worker._comms = mock_communication
        return worker

    async def test_worker_specific_state_transitions(
        self, initialized_service: Worker
    ) -> None:
        """
        Test worker-specific state transitions beyond the base service tests.

        Verifies the worker service correctly transitions through its lifecycle states.
        """
        worker = await async_fixture(initialized_service)

        # Start the worker
        await worker.start()

        # Check the status after starting
        assert worker.state == ServiceState.RUNNING

        # Stop the worker
        await worker.stop()

        # Check the status after stopping
        assert worker.state == ServiceState.STOPPED

    async def test_worker_initialization(self, worker_instance: Worker) -> None:
        """
        Test that the worker initializes with the correct configuration.

        Verifies the worker service is properly instantiated with its configuration.
        """
        # Basic existence checks
        assert worker_instance is not None
        assert worker_instance.service_config is not None
        assert worker_instance.service_type is not None

        # Initialize the worker
        await worker_instance.initialize()

        # Check the worker is properly initialized
        assert worker_instance.is_initialized
        assert worker_instance.state == ServiceState.READY
