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
Base test class for testing AIPerf services.
"""

from abc import ABC, abstractmethod
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import ServiceState
from aiperf.common.enums.comm_enums import CommunicationBackend
from aiperf.common.enums.service_enums import ServiceRunType
from aiperf.common.service.base_service import BaseService
from aiperf.tests.utils.async_test_utils import async_fixture


@pytest.mark.asyncio
class BaseTestService(ABC):
    """
    Base test class for all service tests.

    This class provides common test methods and fixtures for testing
    AIPerf services. Specific service test classes should inherit from
    this class and implement service-specific fixtures and tests.
    """

    @pytest.fixture(autouse=True)
    def no_sleep(self, monkeypatch) -> None:
        """
        Patch asyncio.sleep with a no-op to prevent test delays.

        This ensures tests don't need to wait for real sleep calls.
        """
        import asyncio

        from aiperf.tests.utils.async_test_utils import async_noop

        monkeypatch.setattr(asyncio, "sleep", async_noop)

    @pytest.fixture(autouse=True)
    def patch_communication_factory(self, mock_communication: AsyncMock) -> None:
        """
        Patch the communication factory to always return our mock communication.

        This ensures no real communication is attempted during tests.
        """
        with (
            patch(
                "aiperf.common.comms.communication_factory.CommunicationFactory.create_communication",
                return_value=mock_communication,
            ),
            patch(
                "aiperf.common.comms.zmq_comms.zmq_communication.ZMQCommunication",
                side_effect=Exception(
                    "ZMQCommunication should not be instantiated directly in tests"
                ),
            ),
        ):
            yield

    @pytest.fixture(autouse=True)
    def patch_process_creation(self) -> None:
        """
        Patch process creation methods to prevent spawning actual processes.
        """
        # Mock both multiprocessing Process and threading Thread
        with patch("multiprocessing.Process"), patch("threading.Thread"):
            yield

    @abstractmethod
    @pytest.fixture
    def service_class(self) -> type[BaseService]:
        """
        Return the service class to test.

        Must be implemented by subclasses to specify which service is being tested.
        """
        pass

    @pytest.fixture
    def service_config(self) -> ServiceConfig:
        """
        Create a service configuration for testing.

        Returns:
            A ServiceConfig instance with test settings
        """
        return ServiceConfig(
            service_run_type=ServiceRunType.MULTIPROCESSING,
            comm_backend=CommunicationBackend.ZMQ_TCP,
        )

    @pytest.fixture
    async def uninitialized_service(
        self,
        service_class: type[BaseService],
        service_config: ServiceConfig,
        mock_communication: AsyncMock,
    ) -> BaseService:
        """
        Create an uninitialized instance of the service under test.

        This provides a service instance before initialize() has been called,
        allowing tests to verify initialization behavior.

        Returns:
            An uninitialized instance of the service
        """
        service = service_class(service_config=service_config)
        service._comms = mock_communication
        return service

    @pytest.fixture
    async def service_under_test(
        self,
        service_class: type[BaseService],
        service_config: ServiceConfig,
        mock_communication: AsyncMock,
    ) -> BaseService:
        """
        Create and initialize the service under test.

        This fixture sets up a complete service instance ready for testing,
        with the communication layer mocked.

        Returns:
            An initialized instance of the service
        """
        service = service_class(service_config=service_config)

        # Manually set up the mock communication
        service._comms = mock_communication

        await service.initialize()

        try:
            yield service
        finally:
            # Clean up
            if service._state != ServiceState.STOPPED:
                await service.stop()

    async def test_service_initialization(
        self, uninitialized_service: BaseService
    ) -> None:
        """
        Test that the service initializes correctly.

        This verifies:
        1. The service has a valid ID and type
        2. The service transitions to the correct state during initialization
        3. The service's internal initialization method is called
        """
        service = await async_fixture(uninitialized_service)

        # Check that the service has an ID and type
        assert service.service_id is not None
        assert service.service_type is not None

        # Check that the service is not initialized
        assert service.state == ServiceState.UNKNOWN

        # Initialize the service
        await service.initialize()

        # Check that the service is initialized and in the READY state
        assert service.is_initialized
        assert service.state == ServiceState.READY

    async def test_service_start_stop(self, service_under_test: BaseService) -> None:
        """
        Test that the service can start and stop correctly.

        This verifies:
        1. The service transitions to the RUNNING state when started
        2. The service transitions to the STOPPED state when stopped
        """
        service = await async_fixture(service_under_test)

        # Start the service
        await service.start()
        assert service.state == ServiceState.RUNNING

        # Stop the service
        await service.stop()
        assert service.state == ServiceState.STOPPED

    @pytest.mark.parametrize(
        "state",
        [state for state in ServiceState],
    )
    async def test_service_state_transitions(
        self, service_under_test: BaseService, state: ServiceState
    ) -> None:
        """
        Test that the service can transition to all possible states.

        Args:
            service_under_test: The service instance to test
            state: The state to test transitioning to
        """
        service = await async_fixture(service_under_test)

        # Update the service state
        await service.set_state(state)

        # Check that the service state was updated
        assert service.state == state

    @staticmethod
    def create_safe_mock() -> MagicMock:
        """
        Create a mock object that's safe to use with async code.

        This prevents "coroutine was never awaited" warnings by ensuring
        any async methods on the mock don't actually return coroutines
        that would need to be awaited.

        Returns:
            A mock object that's safe to use with async code
        """
        # Create a mock with no return_value for methods
        mock = MagicMock()

        # Set all attributes that might be coroutines to return None
        for attr_name in dir(mock):
            if callable(getattr(mock, attr_name)) and not attr_name.startswith("_"):
                method = getattr(mock, attr_name)
                if hasattr(method, "return_value") and hasattr(
                    method.return_value, "_is_coroutine"
                ):
                    method.return_value = None

        return mock
