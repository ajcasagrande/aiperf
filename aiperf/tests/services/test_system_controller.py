# #  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# #  SPDX-License-Identifier: Apache-2.0
# #
# #  Licensed under the Apache License, Version 2.0 (the "License");
# #  you may not use this file except in compliance with the License.
# #  You may obtain a copy of the License at
# #
# #  http://www.apache.org/licenses/LICENSE-2.0
# #
# #  Unless required by applicable law or agreed to in writing, software
# #  distributed under the License is distributed on an "AS IS" BASIS,
# #  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# #  See the License for the specific language governing permissions and
# #  limitations under the License.
# """
# Tests for the system controller service.
# """

# import time
# from typing import Dict, List, Optional, Type
# from unittest.mock import AsyncMock, patch

# import pytest
# from pydantic import BaseModel, Field

# from aiperf.app.services.service_manager.base_service_manager import BaseServiceManager
# from aiperf.app.services.service_manager.kubernetes_service_manager import (
#     KubernetesServiceManager,
# )
# from aiperf.app.services.service_manager.multiprocess_service_manager import (
#     MultiProcessServiceManager,
# )
# from aiperf.app.services.system_controller.system_controller import SystemController
# from aiperf.common.config.service_config import ServiceConfig
# from aiperf.common.enums import (
#     CommandType,
#     ServiceState,
#     ServiceType,
#     Topic,
# )
# from aiperf.common.models.message_models import BaseMessage
# from aiperf.common.models.payload_models import (
#     HeartbeatPayload,
#     RegistrationPayload,
#     StatusPayload,
# )
# from aiperf.common.service.base_service import BaseService
# from aiperf.tests.base_test_controller_service import BaseTestControllerService
# from aiperf.tests.base_test_service import async_fixture


# class SystemControllerTestConfig(BaseModel):
#     """Configuration model for system controller tests."""
#     # TODO: Replace this with the actual configuration model once available
#     pass


# @pytest.mark.asyncio
# class TestSystemController(BaseTestControllerService):
#     """
#     Tests for the system controller service.

#     This test class extends BaseTestControllerService to leverage common
#     controller service tests while adding system controller specific tests.
#     Tests include service lifecycle management, message handling, and coordination.
#     """

#     @pytest.fixture
#     def service_class(self) -> Type[BaseService]:
#         """
#         Return the system controller service class for testing.

#         Returns:
#             The SystemController class
#         """
#         return SystemController

#     @pytest.fixture
#     def service_config(self) -> ServiceConfig:
#         """
#         Return a system controller specific configuration for testing.

#         Returns:
#             ServiceConfig configured for system controller tests
#         """
#         return ServiceConfig(
#         )

#     @pytest.fixture
#     def controller_config(self) -> SystemControllerTestConfig:
#         """
#         Return a test configuration for the system controller.

#         Returns:
#             SystemControllerTestConfig with test parameters
#         """
#         return SystemControllerTestConfig()

#     @pytest.fixture
#     def test_service_id(self) -> str:
#         """
#         Return the service ID of a test service.

#         Returns:
#             A test service ID string
#         """
#         return "test-id"

#     @pytest.fixture
#     def mock_service_manager(self, service_config) -> BaseServiceManager:
#         """
#         Return a test service manager.

#         Returns:
#             A BaseServiceManager instance configured for testing
#         """
#         return BaseServiceManager(
#             required_service_types=[ServiceType.TEST],
#             config=service_config,
#         )

#     @pytest.fixture
#     def test_service_manager_with_multiprocess(self, monkeypatch, service_config) -> MultiProcessServiceManager:
#         """
#         Return a test service manager with multiprocess support.

#         This fixture mocks the initialization methods to avoid actual process creation.

#         Args:
#             monkeypatch: Pytest monkeypatch fixture for patching functions

#         Returns:
#             A MultiProcessServiceManager instance configured for testing
#         """
#         # Create a proper async mock for the service methods
#         async_mock = AsyncMock(return_value=None)

#         monkeypatch.setattr(
#             MultiProcessServiceManager, "wait_for_all_services_registration", async_mock
#         )

#         monkeypatch.setattr(
#             MultiProcessServiceManager, "wait_for_all_services_start", async_mock
#         )

#         # Create the service manager with test configuration
#         multiprocess_manager = MultiProcessServiceManager(
#             required_service_types=[ServiceType.TEST],
#             config=service_config,
#         )

#         return multiprocess_manager

#     @pytest.fixture
#     def test_service_manager_with_kubernetes(self) -> KubernetesServiceManager:
#         """
#         Return a test service manager with kubernetes support.

#         Returns:
#             A KubernetesServiceManager instance configured for testing
#         """
#         kubernetes_manager = KubernetesServiceManager(
#             required_service_types=[ServiceType.TEST],
#             config=ServiceConfig(
#                 service_type=ServiceType.SYSTEM_CONTROLLER,
#             ),
#         )
#         return kubernetes_manager

#     @pytest.fixture
#     async def test_system_controller_multiprocess(
#         self, service_under_test: SystemController,
#         test_service_manager_with_multiprocess: MultiProcessServiceManager
#     ) -> SystemController:
#         """
#         Return a test system controller with multiprocess service manager.

#         This fixture provides a fully configured SystemController instance
#         that uses a MultiProcessServiceManager for tests.

#         Args:
#             service_under_test: The base service instance
#             test_service_manager_with_multiprocess: The multiprocess service manager

#         Returns:
#             A SystemController instance with multiprocess manager
#         """
#         service = await async_fixture(service_under_test)
#         service.service_manager = test_service_manager_with_multiprocess
#         return service

#     async def test_system_controller_initialization(
#         self, test_system_controller_multiprocess: SystemController
#     ) -> None:
#         """
#         Test that the system controller initializes with the correct attributes.

#         Verifies:
#         1. The service has the correct service type
#         2. The service manager is properly configured
#         """
#         service = await async_fixture(test_system_controller_multiprocess)
#         assert service.service_type == ServiceType.SYSTEM_CONTROLLER
#         assert hasattr(service, "service_manager")
#         assert hasattr(service.service_manager, "service_id_map")
#         assert isinstance(service.service_manager.service_id_map, dict)

#     async def test_service_start_stop(
#         self, test_system_controller_multiprocess: SystemController, no_sleep
#     ) -> None:
#         """
#         Test that the system controller can start and stop.

#         Verifies:
#         1. The service transitions to RUNNING state when started
#         2. The service transitions to STOPPED state when stopped
#         """
#         service = await async_fixture(test_system_controller_multiprocess)
#         await service.start()
#         assert service.state == ServiceState.RUNNING
#         await service.stop()
#         assert service.state == ServiceState.STOPPED

#     async def test_handle_registration_message(
#         self, test_system_controller_multiprocess: SystemController
#     ) -> None:
#         """
#         Test handling of registration messages.

#         Verifies:
#         1. The system controller properly processes registration messages
#         2. The service is correctly registered in the service manager
#         """
#         service = await async_fixture(test_system_controller_multiprocess)

#     async def test_handle_status_message(
#         self, test_system_controller_multiprocess: SystemController, test_service_id: str
#     ) -> None:
#         """
#         Test handling of status messages.

#         Verifies:
#         1. The system controller properly processes status update messages
#         2. The service status is correctly updated in the service manager

#         Steps:
#         1. Register a test service
#         2. Send a status update for the service
#         3. Verify the status was updated in the service manager
#         """
#         service = await async_fixture(test_system_controller_multiprocess)

#     async def test_handle_heartbeat_message(
#         self, test_system_controller_multiprocess, test_service_id
#     ):
#         """Test handling of heartbeat messages."""
#         service = await async_fixture(test_system_controller_multiprocess)

#     @pytest.mark.parametrize(
#         "command", [CommandType.START, CommandType.STOP, CommandType.CONFIGURE]
#     )
#     async def test_send_command_to_service(
#         self,
#         test_system_controller_multiprocess,
#         test_service_id,
#         mock_communication,
#         command,
#     ):
#         """Test sending commands to services."""
#         service = await async_fixture(test_system_controller_multiprocess)

#     async def test_system_controller_full_lifecycle(
#         self, test_system_controller_multiprocess, mock_communication
#     ):
#         """Test the full lifecycle of the system controller."""
#         service = await async_fixture(test_system_controller_multiprocess)

#     async def test_handle_unknown_service_heartbeat(
#         self, test_system_controller_multiprocess, mock_communication
#     ):
#         """Test handling heartbeat from an unknown service."""
#         service = await async_fixture(test_system_controller_multiprocess)

#     async def test_handle_unknown_service_status(
#         self, test_system_controller_multiprocess, mock_communication
#     ):
#         """Test handling status from an unknown service."""
#         service = await async_fixture(test_system_controller_multiprocess)


#     async def test_service_required_registration(
#         self, test_system_controller_multiprocess, mock_communication
#     ):
#         """Test that required services are properly tracked."""
#         service = await async_fixture(test_system_controller_multiprocess)
