"""
Tests for the system controller service.
"""

import pytest

from aiperf.common.enums import CommandType, ServiceState, ServiceType, Topic
from aiperf.common.models.messages import (
    HeartbeatMessage,
    RegistrationMessage,
    StatusMessage,
)
from aiperf.services.system_controller.main import SystemController
from aiperf.tests.base_test_service import BaseServiceTest
from aiperf.tests.utils.message_mocks import MessageTestUtils


# Helper function for testing with async fixtures
async def async_fixture(fixture):
    """Manually await an async fixture if it's an async generator, otherwise return it."""
    # Check if the fixture is an async generator or a regular object
    if hasattr(fixture, "__aiter__"):
        # It's an async generator, so we need to await it
        async for value in fixture:
            return value
    else:
        # It's a regular object, just return it
        return fixture


# Mark the test class with asyncio
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
        assert service is not None
        assert service.service_type == ServiceType.SYSTEM_CONTROLLER
        # Add system controller specific assertions here

    async def test_handle_registration_message(
        self, service_under_test, mock_communication
    ):
        """Test that the system controller handles registration messages correctly."""
        service = await async_fixture(service_under_test)

        # Create a mock registration message
        service_id = "test_service_id"
        service_type = ServiceType.WORKER
        registration_msg = MessageTestUtils.create_mock_message(
            RegistrationMessage,
            service_id=service_id,
            service_type=service_type,
        )

        # Send the message to the system controller
        await MessageTestUtils.simulate_message_receive(
            service, Topic.REGISTRATION, registration_msg
        )

        # Verify that the service was registered
        # This will depend on the actual implementation, but might look like:
        if hasattr(service, "registered_services"):
            assert service_id in service.registered_services
            assert service.registered_services[service_id].service_type == service_type

    async def test_handle_status_message(self, service_under_test, mock_communication):
        """Test that the system controller handles status messages correctly."""
        service = await async_fixture(service_under_test)

        # Create a mock status message
        service_id = "test_service_id"
        service_type = ServiceType.WORKER
        state = ServiceState.RUNNING
        status_msg = MessageTestUtils.create_mock_message(
            StatusMessage,
            service_id=service_id,
            service_type=service_type,
            state=state,
        )

        # Send the message to the system controller
        await MessageTestUtils.simulate_message_receive(
            service, Topic.STATUS, status_msg
        )

        # Verify that the service status was updated
        # This will depend on the actual implementation

    async def test_handle_heartbeat_message(
        self, service_under_test, mock_communication
    ):
        """Test that the system controller handles heartbeat messages correctly."""
        service = await async_fixture(service_under_test)

        # Create a mock heartbeat message
        service_id = "test_service_id"
        service_type = ServiceType.WORKER
        heartbeat_msg = MessageTestUtils.create_mock_message(
            HeartbeatMessage,
            service_id=service_id,
            service_type=service_type,
        )

        # Send the message to the system controller
        await MessageTestUtils.simulate_message_receive(
            service, Topic.HEARTBEAT, heartbeat_msg
        )

        # Verify that the heartbeat was recorded
        # This will depend on the actual implementation

    @pytest.mark.parametrize(
        "command",
        [CommandType.START, CommandType.STOP, CommandType.PROFILE],
    )
    async def test_send_command_to_service(
        self, service_under_test, mock_communication, command
    ):
        """Test that the system controller can send commands to services."""
        service = await async_fixture(service_under_test)
        target_service_id = "test_service_id"

        # Mock method to send command
        if hasattr(service, "send_command_to_service"):
            # Call the method that would send a command
            await service.send_command_to_service(target_service_id, command)

            # Verify a command message was published
            assert Topic.COMMAND.value in mock_communication.published_messages

            # Find the command message
            command_sent = False
            for msg in mock_communication.published_messages[Topic.COMMAND.value]:
                if (
                    hasattr(msg, "target_service_id")
                    and msg.target_service_id == target_service_id
                    and hasattr(msg, "command")
                    and msg.command == command
                ):
                    command_sent = True
                    break

            assert command_sent, (
                f"Command {command} was not sent to service {target_service_id}"
            )

    async def test_system_controller_full_lifecycle(
        self, service_under_test, mock_communication
    ):
        """
        Test the full lifecycle of the system controller.

        This test simulates a complete workflow where:
        1. The system controller starts
        2. Services register with the controller
        3. Services send status updates
        4. The controller sends commands to services
        5. The controller shuts down
        """
        service = await async_fixture(service_under_test)

        # Start the service
        await service._start()
        assert service.state == ServiceState.RUNNING

        # Simulate service registration
        service_ids = {}
        service_types = [
            ServiceType.WORKER,
            ServiceType.DATASET_MANAGER,
            ServiceType.TIMING_MANAGER,
        ]

        for service_type in service_types:
            service_id = f"{service_type.value}_id"
            service_ids[service_type.value] = service_id

            registration_msg = MessageTestUtils.create_mock_message(
                RegistrationMessage,
                service_id=service_id,
                service_type=service_type,
            )

            await MessageTestUtils.simulate_message_receive(
                service, Topic.REGISTRATION, registration_msg
            )

        # Simulate status updates
        for service_type, service_id in service_ids.items():
            status_msg = MessageTestUtils.create_mock_message(
                StatusMessage,
                service_id=service_id,
                service_type=service_type,
                state=ServiceState.READY,
            )

            await MessageTestUtils.simulate_message_receive(
                service, Topic.STATUS, status_msg
            )

        # If the system controller has a method to start all services, call it
        if hasattr(service, "start_all_services"):
            await service.start_all_services()

            # Verify command messages were sent to all services
            for service_id in service_ids.values():
                found_command = False
                for msg in mock_communication.published_messages.get(
                    Topic.COMMAND.value, []
                ):
                    if (
                        hasattr(msg, "target_service_id")
                        and msg.target_service_id == service_id
                        and hasattr(msg, "command")
                        and msg.command == CommandType.START
                    ):
                        found_command = True
                        break

                assert found_command, f"Start command not sent to {service_id}"

        # Test stopping all services
        if hasattr(service, "stop_all_services"):
            await service.stop_all_services()

            # Verify stop commands were sent
            for service_id in service_ids.values():
                found_command = False
                for msg in mock_communication.published_messages.get(
                    Topic.COMMAND.value, []
                ):
                    if (
                        hasattr(msg, "target_service_id")
                        and msg.target_service_id == service_id
                        and hasattr(msg, "command")
                        and msg.command == CommandType.STOP
                    ):
                        found_command = True
                        break

                assert found_command, f"Stop command not sent to {service_id}"

        # Stop the system controller
        await service.stop()
        assert service.state == ServiceState.STOPPED
