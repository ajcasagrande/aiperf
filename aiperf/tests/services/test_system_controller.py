"""
Tests for the system controller service.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from aiperf.common.enums import (
    ClientType,
    CommandType,
    ServiceState,
    ServiceType,
    Topic,
)
from aiperf.common.models.messages import (
    HeartbeatMessage,
    RegistrationMessage,
    StatusMessage,
)
from aiperf.services.system_controller.system_controller import SystemController
from aiperf.tests.base_test_service import BaseServiceTest, async_fixture
from aiperf.tests.utils.message_mocks import MessageTestUtils


@pytest.mark.asyncio
class TestSystemController(BaseServiceTest):
    """Tests for the system controller service."""

    @pytest.fixture
    def service_class(self):
        """Return the service class to test."""
        return SystemController

    async def test_system_controller_initialization(self, service_under_test):
        """Test that the system controller initializes correctly."""
        service = await async_fixture(service_under_test)
        assert service.service_type == ServiceType.SYSTEM_CONTROLLER
        assert hasattr(service, "service_manager")
        assert hasattr(service.service_manager, "service_id_map")
        assert isinstance(service.service_manager.service_id_map, dict)

    async def test_service_status_update(self, service_under_test, mock_communication):
        """Override to test that the service updates its status correctly for SystemController."""
        service = await async_fixture(service_under_test)

        # Directly create and publish a status message for testing
        status_message = service.wrap_message(StatusMessage(state=ServiceState.READY))
        await service._publish_message(
            ClientType.COMPONENT_PUB, Topic.STATUS, status_message
        )

        # Verify the message was published with correct fields
        assert Topic.STATUS in mock_communication.published_messages
        status_msg = mock_communication.published_messages[Topic.STATUS][0]
        assert status_msg.service_id == service.service_id
        assert status_msg.service_type == ServiceType.SYSTEM_CONTROLLER
        assert status_msg.state == ServiceState.READY

    @pytest.fixture
    def test_worker_registration(self, service_under_test) -> RegistrationMessage:
        """Fixture providing test data for worker registration."""
        return service_under_test.wrap_message(RegistrationMessage())

    async def test_handle_registration_message(
        self, service_under_test, mock_communication, test_worker_registration
    ):
        """Test handling of registration messages."""
        service = await async_fixture(service_under_test)
        worker_data = test_worker_registration

        # Send the message to the service
        await MessageTestUtils.simulate_message_receive(
            service,
            Topic.REGISTRATION,
            service.wrap_message(RegistrationMessage()),
        )

        # Check that the component was registered in the service manager
        assert worker_data.service_id in service.service_manager.service_id_map
        assert (
            service.service_manager.service_id_map[worker_data.service_id].service_type
            == worker_data.service_type
        )

    async def test_handle_status_message(
        self, service_under_test, mock_communication, test_worker_registration
    ):
        """Test handling of status messages."""
        service = await async_fixture(service_under_test)
        worker_data = test_worker_registration

        # First register a service
        await MessageTestUtils.simulate_message_receive(
            service,
            Topic.REGISTRATION,
            service.wrap_message(RegistrationMessage()),
        )

        # Now send a status update
        status_message = service.wrap_message(StatusMessage(state=ServiceState.RUNNING))
        await MessageTestUtils.simulate_message_receive(
            service, Topic.STATUS, status_message
        )

        # Check that the component status was updated
        assert (
            service.service_manager.service_id_map[worker_data.service_id].state
            == ServiceState.RUNNING
        )

    async def test_handle_heartbeat_message(
        self, service_under_test, mock_communication, test_worker_registration
    ):
        """Test handling of heartbeat messages."""
        service = await async_fixture(service_under_test)
        worker_data = test_worker_registration
        timestamp = datetime.now() + timedelta(seconds=-5)

        # First register a service
        await MessageTestUtils.simulate_message_receive(
            service,
            Topic.REGISTRATION,
            service.wrap_message(RegistrationMessage()),
        )

        # Now send a heartbeat
        heartbeat_message = HeartbeatMessage(
            service_id=worker_data.service_id,
            service_type=worker_data.service_type,
        )
        await MessageTestUtils.simulate_message_receive(
            service, Topic.HEARTBEAT, heartbeat_message
        )

        # Check that the last heartbeat was updated
        assert (
            service.service_manager.service_id_map[worker_data.service_id].last_seen
            >= timestamp
        )

    async def test_service_start_stop(self, service_under_test):
        """Override the base test to handle SystemController special needs."""
        service = await async_fixture(service_under_test)

        # Patch the _on_start method to avoid blocking operations
        with patch.object(service, "_on_start", return_value=asyncio.Future()):
            service._on_start.return_value.set_result(None)

            # Start the service
            await service._start()
            assert service.state == ServiceState.RUNNING

            # Stop the service
            await service.stop()
            assert service.state == ServiceState.STOPPED

    @pytest.mark.parametrize(
        "command", [CommandType.START, CommandType.STOP, CommandType.CONFIGURE]
    )
    async def test_send_command_to_service(
        self,
        service_under_test,
        mock_communication,
        test_worker_registration,
        command,
    ):
        """Test sending commands to services."""
        service = await async_fixture(service_under_test)
        worker_data = test_worker_registration

        # First register a service
        await MessageTestUtils.simulate_message_receive(
            service,
            Topic.REGISTRATION,
            service.wrap_message(RegistrationMessage()),
        )

        # Clear any registration-related messages
        mock_communication.published_messages = {}

        # Send the command
        await service.send_command_to_service(
            target_service_id=worker_data.service_id,
            command=command,
        )

        # Verify the command was published with correct fields
        assert Topic.COMMAND in mock_communication.published_messages
        command_message = mock_communication.published_messages[Topic.COMMAND][0]
        assert command_message.target_service_id == worker_data.service_id
        assert command_message.command == command

    async def test_system_controller_full_lifecycle(
        self, service_under_test, mock_communication
    ):
        """Test the full lifecycle of the system controller."""
        service = await async_fixture(service_under_test)

        # Start the service by directly setting state to RUNNING
        await service._set_service_status(ServiceState.RUNNING)
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
                RegistrationMessage(
                    service_id=service_id,
                    service_type=component_type,
                ),
            )
            assert service_id in service.service_manager.service_id_map

        # Verify all components were registered
        assert len(service.service_manager.service_id_map) == len(component_types)

        # Stop the service
        await service.stop()
        assert service.state == ServiceState.STOPPED

    async def test_handle_unknown_service_heartbeat(
        self, service_under_test, mock_communication
    ):
        """Test handling heartbeat from an unknown service."""
        service = await async_fixture(service_under_test)
        unknown_id = "unknown-service-id"

        # Send heartbeat from unknown service
        heartbeat_message = HeartbeatMessage(
            service_id=unknown_id,
            service_type=ServiceType.WORKER,
        )

        # This should not raise an exception
        await MessageTestUtils.simulate_message_receive(
            service, Topic.HEARTBEAT, heartbeat_message
        )

        # Verify service wasn't registered just by heartbeat
        assert unknown_id not in service.service_manager.service_id_map

    async def test_handle_unknown_service_status(
        self, service_under_test, mock_communication
    ):
        """Test handling status from an unknown service."""
        service = await async_fixture(service_under_test)
        unknown_id = "unknown-service-id"

        # Send status from unknown service
        status_message = StatusMessage(
            service_id=unknown_id,
            service_type=ServiceType.WORKER,
            state=ServiceState.RUNNING,
        )

        # This should not raise an exception
        await MessageTestUtils.simulate_message_receive(
            service, Topic.STATUS, status_message
        )

        # Verify service wasn't registered just by status update
        assert unknown_id not in service.service_manager.service_id_map

    async def test_service_required_registration(
        self, service_under_test, mock_communication
    ):
        """Test that required services are properly tracked."""
        service = await async_fixture(service_under_test)

        # Get required service types from the service
        required_services = service.required_service_types

        # Verify that we have at least one required service
        assert len(required_services) > 0

        # Register one of the required services
        service_type = required_services[0]
        service_id = f"test-required-{service_type.value}"
        registration_message = RegistrationMessage(
            service_id=service_id,
            service_type=service_type,
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
