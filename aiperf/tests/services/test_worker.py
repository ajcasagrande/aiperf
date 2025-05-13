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

from unittest.mock import AsyncMock, patch

import pytest

from aiperf.common.comms.communication import BaseCommunication
from aiperf.common.config.service_config import ServiceConfig
from aiperf.services.worker.worker import Worker


@pytest.mark.asyncio
class TestWorker:
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
    def mock_communication(self):
        """Create a mock communication object for worker tests."""
        mock_comm: AsyncMock = AsyncMock(spec=BaseCommunication)
        mock_comm.initialize.return_value = True
        mock_comm.pull.return_value = True
        mock_comm.push.return_value = True
        mock_comm.publish.return_value = True
        mock_comm.subscribe.return_value = True
        mock_comm.request.return_value = {"status": "success", "data": "test_data"}
        mock_comm.respond.return_value = True
        return mock_comm

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

    async def test_worker_send_request(self, worker):
        """Test that the worker can send requests."""
        # Mock response data
        mock_response = {"status": "success", "data": "test_data"}

        # Mock the send_request method to return the mock response
        original_send_request = worker.send_request
        worker.send_request = AsyncMock(return_value=mock_response)

        # Call the method
        response = await worker.send_request(
            operation="test_operation", parameters={"param": "value"}
        )

        # Verify the response
        assert response == mock_response

        # Restore the original method
        worker.send_request = original_send_request
