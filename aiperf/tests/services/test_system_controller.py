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
Tests for the system controller service.
"""

import time
from unittest.mock import AsyncMock

import pytest

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import (
    CommandType,
    ServiceState,
    ServiceType,
    Topic,
)
from aiperf.common.models.message_models import BaseMessage
from aiperf.common.models.payload_models import (
    HeartbeatPayload,
    RegistrationPayload,
    StatusPayload,
)
from aiperf.services.system_controller.base_service_manager import BaseServiceManager
from aiperf.services.system_controller.kubernetes_service_manager import (
    KubernetesServiceManager,
)
from aiperf.services.system_controller.multiprocess_manager import (
    MultiProcessServiceManager,
)
from aiperf.services.system_controller.system_controller import SystemController
from aiperf.tests.base_test_controller_service import BaseTestControllerService
from aiperf.tests.base_test_service import async_fixture
from aiperf.tests.utils.message_mocks import MessageTestUtils


@pytest.mark.asyncio
class TestSystemController(BaseTestControllerService):
    """Tests for the system controller service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return SystemController

    @pytest.fixture
    def test_service_id(self):
        """Return the service ID of a test service."""
        return "test-id"

    @pytest.fixture
    def test_service_manager(self):
        """Return a test service manager."""
        return BaseServiceManager(
            required_service_types=[ServiceType.TEST],
            config=ServiceConfig(
                service_type=ServiceType.SYSTEM_CONTROLLER,
            ),
        )

    @pytest.fixture
    def test_service_manager_with_multiprocess(self, monkeypatch):
        """Return a test service manager with multiprocess."""
        # Create a proper async mock for the initialize_all_services method
        async_mock = AsyncMock(return_value=None)

        monkeypatch.setattr(
            MultiProcessServiceManager, "wait_for_all_services_registration", async_mock
        )

        monkeypatch.setattr(
            MultiProcessServiceManager, "wait_for_all_services_start", async_mock
        )

        # Create the service manager with test configuration
        multiprocess_manager = MultiProcessServiceManager(
            required_service_types=[ServiceType.TEST],
            config=ServiceConfig(
                service_type=ServiceType.SYSTEM_CONTROLLER,
            ),
        )

        return multiprocess_manager

    @pytest.fixture
    def test_service_manager_with_kubernetes(self):
        """Return a test service manager with kubernetes."""
        kubernetes_manager = KubernetesServiceManager(
            required_service_types=[ServiceType.TEST],
            config=ServiceConfig(
                service_type=ServiceType.SYSTEM_CONTROLLER,
            ),
        )
        return kubernetes_manager

    @pytest.fixture
    async def test_system_controller_multiprocess(
        self, service_under_test, test_service_manager_with_multiprocess
    ):
        """Return a test system controller with multiprocess."""
        service = await async_fixture(service_under_test)
        service.service_manager = test_service_manager_with_multiprocess
        return service

    async def test_system_controller_initialization(
        self, test_system_controller_multiprocess
    ):
        """Test that the system controller initializes correctly."""
        service = await async_fixture(test_system_controller_multiprocess)
        assert service.service_type == ServiceType.SYSTEM_CONTROLLER
        assert hasattr(service, "service_manager")
        assert hasattr(service.service_manager, "service_id_map")
        assert isinstance(service.service_manager.service_id_map, dict)

    async def test_service_start_stop(
        self, test_system_controller_multiprocess, no_sleep
    ):
        """Test that the service can start and stop."""
        service = await async_fixture(test_system_controller_multiprocess)
        await service.start()
        assert service.state == ServiceState.RUNNING
        await service.stop()
        assert service.state == ServiceState.STOPPED

    async def test_handle_registration_message(
        self, test_system_controller_multiprocess
    ):
        """Test handling of registration messages."""
        service = await async_fixture(test_system_controller_multiprocess)
        registration_message = BaseMessage(
            service_id="test-id",
            payload=RegistrationPayload(
                service_type=ServiceType.TEST,
            ),
        )

        # Send the response to the service
        await MessageTestUtils.simulate_message_receive(
            service,
            Topic.REGISTRATION,
            registration_message,
        )

        # Check that the component was registered in the service manager
        assert registration_message.service_id in service.service_manager.service_id_map
        assert (
            service.service_manager.service_id_map[
                registration_message.service_id
            ].service_type
            == registration_message.payload.service_type
        )

    async def test_handle_status_message(
        self, test_system_controller_multiprocess, test_service_id
    ):
        """Test handling of status messages."""
        service = await async_fixture(test_system_controller_multiprocess)
        registration_message = BaseMessage(
            service_id=test_service_id,
            payload=RegistrationPayload(
                service_type=ServiceType.TEST,
            ),
        )

        # First register a service
        await MessageTestUtils.simulate_message_receive(
            service,
            Topic.REGISTRATION,
            registration_message,
        )

        # Now send a status update
        status_message = BaseMessage(
            service_id=test_service_id,
            payload=StatusPayload(
                state=ServiceState.RUNNING,
                service_type=ServiceType.TEST,
            ),
        )
        await MessageTestUtils.simulate_message_receive(
            service, Topic.STATUS, status_message
        )

        # Check that the component status was updated
        assert (
            service.service_manager.service_id_map[test_service_id].state
            == ServiceState.RUNNING
        )

    async def test_handle_heartbeat_message(
        self, test_system_controller_multiprocess, test_service_id
    ):
        """Test handling of heartbeat messages."""
        service = await async_fixture(test_system_controller_multiprocess)
        registration_message = BaseMessage(
            service_id=test_service_id,
            payload=RegistrationPayload(
                service_type=ServiceType.TEST,
            ),
        )
        timestamp = time.time_ns() - 5

        # First register a service
        await MessageTestUtils.simulate_message_receive(
            service,
            Topic.REGISTRATION,
            registration_message,
        )

        # Now send a heartbeat
        heartbeat_message = BaseMessage(
            service_id=test_service_id,
            payload=HeartbeatPayload(
                service_type=ServiceType.TEST,
            ),
        )
        await MessageTestUtils.simulate_message_receive(
            service, Topic.HEARTBEAT, heartbeat_message
        )

        # Check that the last heartbeat was updated
        assert (
            service.service_manager.service_id_map[test_service_id].last_seen
            >= timestamp
        )

    @pytest.mark.parametrize(
        "command", [CommandType.START, CommandType.STOP, CommandType.CONFIGURE]
    )
    async def test_send_command_to_service(
        self,
        test_system_controller_multiprocess,
        test_service_id,
        mock_communication,
        command,
    ):
        """Test sending commands to services."""
        service = await async_fixture(test_system_controller_multiprocess)
        registration_message = BaseMessage(
            service_id=test_service_id,
            payload=RegistrationPayload(
                service_type=ServiceType.TEST,
            ),
        )

        # First register a service
        await MessageTestUtils.simulate_message_receive(
            service,
            Topic.REGISTRATION,
            registration_message,
        )

        # Clear any registration-related messages
        mock_communication.published_messages = {}

        # Send the command
        await service.send_command_to_service(
            target_service_id=test_service_id,
            command=command,
        )

        # Verify the command was published with correct fields
        assert Topic.COMMAND in mock_communication.published_messages
        command_message = mock_communication.published_messages[Topic.COMMAND][0]
        assert command_message.payload.target_service_id == test_service_id
        assert command_message.payload.command == command

    async def test_system_controller_full_lifecycle(
        self, test_system_controller_multiprocess, mock_communication
    ):
        """Test the full lifecycle of the system controller."""
        service = await async_fixture(test_system_controller_multiprocess)

        # Start the service by directly setting state to RUNNING
        await service.set_state(ServiceState.RUNNING)
        assert service.state == ServiceState.RUNNING

        # Register several components
        component_types = [
            ServiceType.WORKER,
            ServiceType.DATASET_MANAGER,
            ServiceType.TIMING_MANAGER,
        ]

        # Register services and verify
        for i, component_type in enumerate(component_types):
            service_id = f"test-id-{i}"
            await MessageTestUtils.simulate_message_receive(
                service,
                Topic.REGISTRATION,
                BaseMessage(
                    service_id=service_id,
                    payload=RegistrationPayload(
                        service_type=component_type,
                        state=ServiceState.READY,
                    ),
                ),
            )
            assert service_id in service.service_manager.service_id_map

        # Verify all components were registered
        assert len(service.service_manager.service_id_map) == len(component_types)

        # Stop the service
        await service.stop()
        assert service.state == ServiceState.STOPPED

    async def test_handle_unknown_service_heartbeat(
        self, test_system_controller_multiprocess, mock_communication
    ):
        """Test handling heartbeat from an unknown service."""
        service = await async_fixture(test_system_controller_multiprocess)
        unknown_id = "unknown-service-id"

        # Send heartbeat from unknown service
        heartbeat_message = BaseMessage(
            service_id=unknown_id,
            payload=HeartbeatPayload(
                service_type=ServiceType.WORKER,
            ),
        )

        # This should not raise an exception
        await MessageTestUtils.simulate_message_receive(
            service, Topic.HEARTBEAT, heartbeat_message
        )

        # Verify service wasn't registered just by heartbeat
        assert unknown_id not in service.service_manager.service_id_map

    async def test_handle_unknown_service_status(
        self, test_system_controller_multiprocess, mock_communication
    ):
        """Test handling status from an unknown service."""
        service = await async_fixture(test_system_controller_multiprocess)
        unknown_id = "unknown-service-id"

        # Send status from unknown service
        status_message = BaseMessage(
            service_id=unknown_id,
            payload=StatusPayload(
                state=ServiceState.RUNNING,
                service_type=ServiceType.WORKER,
            ),
        )

        # This should not raise an exception
        await MessageTestUtils.simulate_message_receive(
            service, Topic.STATUS, status_message
        )

        # Verify service wasn't registered just by status update
        assert unknown_id not in service.service_manager.service_id_map

    async def test_service_required_registration(
        self, test_system_controller_multiprocess, mock_communication
    ):
        """Test that required services are properly tracked."""
        service = await async_fixture(test_system_controller_multiprocess)

        # Get required service types from the service
        required_services = service.required_service_types

        # Verify that we have at least one required service
        assert len(required_services) > 0

        # Register one of the required services
        service_type = required_services[0]
        service_id = f"test-required-{service_type.value}"
        registration_message = BaseMessage(
            service_id=service_id,
            payload=RegistrationPayload(
                service_type=service_type,
            ),
        )

        await MessageTestUtils.simulate_message_receive(
            service,
            Topic.REGISTRATION,
            registration_message,
        )

        # Verify service was registered
        assert service_id in service.service_manager.service_id_map
        assert (
            service.service_manager.service_id_map[service_id].service_type
            == service_type
        )
