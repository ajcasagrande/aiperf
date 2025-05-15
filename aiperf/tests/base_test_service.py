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
Base test class for testing aiperf services.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from aiperf.common.enums import CommandType, ServiceState
from aiperf.common.models.messages import BaseMessage
from aiperf.tests.utils.async_test_utils import async_fixture, async_noop


@pytest.mark.asyncio
class BaseTestService:
    """
    Base test class for all service tests.

    This class provides common test methods and utilities for testing
    different aiperf services. Specific service test classes should
    inherit from this class and implement service-specific tests.
    """

    @pytest.fixture
    def no_sleep(self):
        """Fixture to replace asyncio.sleep with a no-op."""
        with patch("asyncio.sleep", returns=async_noop):
            yield

    @pytest.fixture
    def service_class(self) -> type[Any]:
        """Return the service class to test. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement service_class fixture")

    @pytest.fixture
    async def service_under_test(
        self, service_class, service_config, mock_communication, no_sleep
    ):
        """
        Fixture that creates and initializes the service under test.

        Returns:
            An initialized instance of the service
        """
        with patch(
            "aiperf.common.comms.communication_factory.CommunicationFactory.create_communication",
            return_value=mock_communication,
        ):
            service = service_class(service_config=service_config)

            # Manually set up the mock communication
            service.communication = mock_communication
            service.communication.initialized = True

            # Reset the published messages tracking
            mock_communication.published_messages = {}

            await service.initialize()

            try:
                yield service
            finally:
                # Clean up
                if service.state != ServiceState.STOPPED:
                    await service.stop()

    async def test_service_initialization(self, service_under_test):
        """Test that the service initializes correctly."""
        service = await async_fixture(service_under_test)
        assert service.service_id is not None
        assert service.service_type is not None

        # After initialization, service should be in one of these states
        assert service.state in [
            ServiceState.INITIALIZING,
            ServiceState.READY,
            ServiceState.UNKNOWN,
        ]

    async def test_service_start_stop(self, service_under_test, no_sleep):
        """Test that the service can start and stop correctly."""
        service = await async_fixture(service_under_test)

        # Start the service
        await service.start()
        assert service.state == ServiceState.RUNNING

        # Stop the service
        await service.stop()
        assert service.state == ServiceState.STOPPED

    @pytest.mark.parametrize(
        "state",
        [
            ServiceState.INITIALIZING,
            ServiceState.READY,
            ServiceState.STARTING,
            ServiceState.RUNNING,
            ServiceState.STOPPING,
            ServiceState.STOPPED,
            ServiceState.ERROR,
        ],
    )
    async def test_service_all_states(self, service_under_test, state):
        """Test that the service can transition to all possible states."""
        service = await async_fixture(service_under_test)

        # Update the service status
        await service.set_state(state)

        # Check that the service state was updated
        assert service.state == state

    def create_command_message(
        self, service, command: CommandType, target_service_id: str
    ) -> BaseMessage:
        """
        Helper method to create a properly formed command response for testing.

        Args:
            service: The service that will receive the command
            command: The command to execute (default: "start")

        Returns:
            A BaseMessage instance with all required fields
        """
        return service.create_command_message(
            command=command, target_service_id=target_service_id
        )

    @staticmethod
    def create_safe_mock() -> MagicMock:
        """Create a mock object that's safe to use with async code.

        This helps prevent "coroutine was never awaited" warnings by ensuring
        any async methods on the mock don't actually return coroutines that go
        unwaited.

        Returns:
            MagicMock: A mock object that's safe to use with async code
        """
        # Create a mock with no return_value for methods
        mock = MagicMock()

        # Set all attributes that might be coroutines to return None instead of
        # other AsyncMocks
        for attr_name in dir(mock):
            if callable(getattr(mock, attr_name)) and not attr_name.startswith("_"):
                method = getattr(mock, attr_name)
                if hasattr(method, "return_value") and hasattr(
                    method.return_value, "_is_coroutine"
                ):
                    method.return_value = None

        return mock
