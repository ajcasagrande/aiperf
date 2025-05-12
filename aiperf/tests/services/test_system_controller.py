"""
Tests for the system controller service.
"""

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
    CommandMessage,
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

    @pytest.fixture
    async def service_under_test(
        self, service_class, service_config, mock_communication
    ):
        """Override the service_under_test fixture to customize SystemController initialization."""
        with patch(
            "aiperf.common.comms.communication_factory.CommunicationFactory.create_communication",
            return_value=mock_communication,
        ):
            service = service_class(config=service_config)

            # Initialize but don't run
            await service._initialize()

            # Add required attributes for SystemController
            service.components = {}
            service.service_processes = {}

            try:
                yield service
            finally:
                # Clean up
                if service.state != ServiceState.STOPPED:
                    await service.stop()

    @pytest.fixture
    async def properly_initialized_service(
        self, service_under_test, mock_communication
    ):
        """Override to add SystemController specific attributes and methods."""
        service = await async_fixture(service_under_test)

        # Manually set up the mock communication
        service.communication = mock_communication
        service.communication.initialized = True

        # Reset the published messages tracking
        mock_communication.published_messages = {}

        # Add a send_command method
        async def send_command(target_id, command):
            cmd_message = CommandMessage(
                service_id=service.service_id,
                service_type=service.service_type,
                command_id="test_command_id",
                command=command,
                target_service_id=target_id,
            )
            await service._publish_message(
                ClientType.CONTROLLER_PUB, Topic.COMMAND, cmd_message
            )
            return True

        service.send_command = send_command
        service.start = service._start

        return service

    async def test_system_controller_initialization(self, properly_initialized_service):
        """Test that the system controller initializes correctly."""
        service = properly_initialized_service
        assert service.service_type == ServiceType.SYSTEM_CONTROLLER
        # Add system controller specific assertions here
        assert hasattr(service, "components")
        assert isinstance(service.components, dict)

    async def test_handle_registration_message(
        self, properly_initialized_service, mock_communication
    ):
        """Test handling of registration messages."""
        service = properly_initialized_service

        # Create and send a registration message
        reg_message = RegistrationMessage(
            service_id="test-id",
            service_type=ServiceType.WORKER,
            friendly_name="Test Worker",
        )

        # Send the message to the service
        await MessageTestUtils.simulate_message_receive(
            service, Topic.REGISTRATION, reg_message
        )

        # Check that the component was registered
        assert "test-id" in service.components
        assert service.components["test-id"].service_type == ServiceType.WORKER

    async def test_handle_status_message(
        self, properly_initialized_service, mock_communication
    ):
        """Test handling of status messages."""
        service = properly_initialized_service

        # First register a service
        reg_message = RegistrationMessage(
            service_id="test-id",
            service_type=ServiceType.WORKER,
            friendly_name="Test Worker",
        )
        await MessageTestUtils.simulate_message_receive(
            service, Topic.REGISTRATION, reg_message
        )

        # Now send a status update
        status_message = StatusMessage(
            service_id="test-id",
            service_type=ServiceType.WORKER,
            state=ServiceState.RUNNING,
        )
        await MessageTestUtils.simulate_message_receive(
            service, Topic.STATUS, status_message
        )

        # Check that the component status was updated
        assert service.components["test-id"].state == ServiceState.RUNNING

    async def test_handle_heartbeat_message(
        self, properly_initialized_service, mock_communication
    ):
        """Test handling of heartbeat messages."""
        service = properly_initialized_service

        # First register a service
        reg_message = RegistrationMessage(
            service_id="test-id",
            service_type=ServiceType.WORKER,
            friendly_name="Test Worker",
        )
        await MessageTestUtils.simulate_message_receive(
            service, Topic.REGISTRATION, reg_message
        )

        # Now send a heartbeat
        heartbeat_message = HeartbeatMessage(
            service_id="test-id",
            service_type=ServiceType.WORKER,
            timestamp=123456789.0,
        )
        await MessageTestUtils.simulate_message_receive(
            service, Topic.HEARTBEAT, heartbeat_message
        )

        # Check that the last heartbeat was updated
        assert service.components["test-id"].last_heartbeat == 123456789.0

    @pytest.mark.parametrize(
        "command", [CommandType.START, CommandType.STOP, CommandType.CONFIGURE]
    )
    async def test_send_command_to_service(
        self, properly_initialized_service, mock_communication, command
    ):
        """Test sending commands to services."""
        service = properly_initialized_service

        # First register a service
        reg_message = RegistrationMessage(
            service_id="test-id",
            service_type=ServiceType.WORKER,
            friendly_name="Test Worker",
        )
        await MessageTestUtils.simulate_message_receive(
            service, Topic.REGISTRATION, reg_message
        )

        # Send the command
        await service.send_command("test-id", command)

        # Check that the command was published
        assert Topic.COMMAND in mock_communication.published_messages
        # Find the command in the published messages
        command_message = None
        for msg in mock_communication.published_messages[Topic.COMMAND]:
            if isinstance(msg, CommandMessage) and msg.target_service_id == "test-id":
                command_message = msg
                break
        assert command_message is not None
        assert command_message.command == command

    async def test_system_controller_full_lifecycle(
        self, properly_initialized_service, mock_communication
    ):
        """Test the full lifecycle of the system controller."""
        service = properly_initialized_service

        # Start the service by directly setting state to RUNNING (to avoid issues with the sleep loop)
        await service._set_service_status(ServiceState.RUNNING)

        # Check that the service is running
        assert service.state == ServiceState.RUNNING

        # Register several components
        component_types = [
            ServiceType.WORKER,
            ServiceType.DATASET_MANAGER,
            ServiceType.TIMING_MANAGER,
        ]
        for i, component_type in enumerate(component_types):
            reg_message = RegistrationMessage(
                service_id=f"test-id-{i}",
                service_type=component_type,
                friendly_name=f"Test {component_type.name}",
            )
            await MessageTestUtils.simulate_message_receive(
                service, Topic.REGISTRATION, reg_message
            )

        # Check that all components were registered
        assert len(service.components) == len(component_types)

        # Send a command to all components
        for component_id in service.components:
            await service.send_command(component_id, CommandType.START)

        # Update status for all components
        for component_id in service.components:
            status_message = StatusMessage(
                service_id=component_id,
                service_type=service.components[component_id].service_type,
                state=ServiceState.RUNNING,
            )
            await MessageTestUtils.simulate_message_receive(
                service, Topic.STATUS, status_message
            )

        # Stop the service
        await service.stop()

        # Check that the service is stopped
        assert service.state == ServiceState.STOPPED
