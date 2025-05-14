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

from unittest.mock import patch

import pytest

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceState
from aiperf.services.worker.worker import Worker
from aiperf.tests.base_test_service import BaseServiceTest


@pytest.mark.asyncio
class TestWorker(BaseServiceTest):
    """Tests for the worker service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class for testing."""
        return Worker

    @pytest.fixture
    def service_config(self):
        """Return a service configuration for testing."""
        return ServiceConfig()

    @pytest.fixture
    def worker(self, service_config, mock_communication):
        """Return a worker instance for testing."""
        with patch(
            "aiperf.common.comms.communication_factory.CommunicationFactory.create_communication",
            return_value=mock_communication,
        ):
            worker = Worker(service_config=service_config)
            worker.communication = mock_communication
            return worker

    async def test_service_status_update(self, worker, **kwargs):
        """Test that the worker service status is correct."""
        # Check the initial status
        assert worker.state == ServiceState.UNKNOWN

        # Start the worker
        await worker._start()

        # Check the status after starting
        assert worker.state == ServiceState.RUNNING

        # Stop the worker
        await worker.stop()

        # Check the status after stopping
        assert worker.state == ServiceState.STOPPED

    async def test_worker_initialization(self, worker):
        """Test that the worker initializes correctly."""
        # Basic existence checks
        assert worker is not None
        assert worker.service_config is not None

    async def test_worker_start_stop(self, worker):
        """Test that the worker can start and stop."""
        # Start the worker
        await worker._start()

        # Stop the worker
        await worker.stop()
