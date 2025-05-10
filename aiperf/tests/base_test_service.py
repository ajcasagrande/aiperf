"""
Base test class for testing aiperf services.
"""

import asyncio
import uuid
from unittest.mock import patch

import pytest

from aiperf.common.enums import ServiceState, ServiceType, Topic
from aiperf.common.models.messages import CommandMessage


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


# Apply asyncio marker to all tests in this class
@pytest.mark.asyncio
class BaseServiceTest:
    """
    Base test class for all service tests.

    This class provides common test methods and utilities for testing
    different aiperf services. Specific service test classes should
    inherit from this class and implement service-specific tests.
    """

    @pytest.fixture
    async def service_under_test(
        self, service_class, service_config, mock_communication
    ):
        """
        Fixture that creates and initializes the service under test.

        Args:
            service_class: The class of the service to be tested
            service_config: The service configuration
            mock_communication: Mocked communication object

        Returns:
            An initialized instance of the service
        """
        with patch(
            "aiperf.common.comms.communication_factory.CommunicationFactory.create_communication",
            return_value=mock_communication,
        ):
            service = service_class(config=service_config)

            # Initialize but don't run
            await service._initialize()

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
        """
        Fixture that provides a service with properly initialized communication.

        This solves the issue where the communication component isn't fully initialized
        in the service, causing tests to fail when trying to publish messages.

        Args:
            service_under_test: The service to initialize
            mock_communication: The mock communication object

        Returns:
            A service with properly initialized communication
        """
        service = await async_fixture(service_under_test)

        # Manually set up the mock communication
        service.communication = mock_communication
        service.communication.initialized = True

        # Reset the published messages tracking
        mock_communication.published_messages = {}

        return service

    async def test_service_initialization(self, service_under_test):
        """Test that the service initializes correctly."""
        service = await async_fixture(service_under_test)
        assert service.service_id is not None
        assert service.service_type is not None

        # After initialization, service will be in READY state rather than INITIALIZING
        # because the service_under_test fixture calls _initialize()
        assert service.state in [
            ServiceState.INITIALIZING,
            ServiceState.READY,
            ServiceState.UNKNOWN,
        ]

    async def test_service_start_stop(self, service_under_test):
        """Test that the service can start and stop correctly."""
        service = await async_fixture(service_under_test)

        # Start the service
        await service._start()
        assert service.state == ServiceState.RUNNING

        # Stop the service
        await service.stop()
        assert service.state == ServiceState.STOPPED

    async def test_service_heartbeat(
        self, properly_initialized_service, mock_communication
    ):
        """Test that the service sends heartbeat messages."""
        service = properly_initialized_service

        # Start the heartbeat task
        await service._start_heartbeat_task()

        # Wait for at least one heartbeat
        await asyncio.sleep(0.1)

        # Check that a heartbeat message was published
        assert Topic.HEARTBEAT.value in mock_communication.published_messages
        assert len(mock_communication.published_messages[Topic.HEARTBEAT.value]) > 0

        # Cleanup
        if service.heartbeat_task and not service.heartbeat_task.done():
            service.heartbeat_task.cancel()

    async def test_service_registration(
        self, properly_initialized_service, mock_communication
    ):
        """Test that the service registers with the system controller."""
        service = properly_initialized_service

        # Register the service
        await service._register()

        # Check that a registration message was published
        assert Topic.REGISTRATION in mock_communication.published_messages
        assert len(mock_communication.published_messages[Topic.REGISTRATION]) > 0

        # Verify registration message
        registration_msg = mock_communication.published_messages[Topic.REGISTRATION][0]
        assert registration_msg.service_id == service.service_id

        # Compare service_type values to handle both enum and string
        msg_service_type = getattr(
            registration_msg.service_type, "value", registration_msg.service_type
        )
        service_service_type = getattr(
            service.service_type, "value", service.service_type
        )
        assert msg_service_type == service_service_type

    async def test_service_status_update(
        self, properly_initialized_service, mock_communication
    ):
        """Test that the service updates its status."""
        service = properly_initialized_service

        # Update the service status
        await service._set_service_status(ServiceState.READY)

        # Check that a status message was published
        assert Topic.STATUS in mock_communication.published_messages
        assert len(mock_communication.published_messages[Topic.STATUS]) > 0

        # Verify status message
        status_msg = mock_communication.published_messages[Topic.STATUS][0]
        assert status_msg.service_id == service.service_id

        # Compare service_type values to handle both enum and string
        msg_service_type = getattr(
            status_msg.service_type, "value", status_msg.service_type
        )
        service_service_type = getattr(
            service.service_type, "value", service.service_type
        )
        assert msg_service_type == service_service_type

        # Check status state - compare values to handle both enum and string
        msg_state = getattr(status_msg.state, "value", status_msg.state)
        expected_state = getattr(ServiceState.READY, "value", ServiceState.READY)
        assert msg_state == expected_state

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
    async def test_service_all_states(
        self, properly_initialized_service, mock_communication, state
    ):
        """Test that the service can transition to all possible states."""
        service = properly_initialized_service

        # Update the service status
        await service._set_service_status(state)

        # Check that the service state was updated
        assert service.state == state

    async def create_command_message(self, service, command="start"):
        """
        Helper method to create a properly formed command message for testing.

        Args:
            service: The service that will receive the command
            command: The command to execute (default: "start")

        Returns:
            A CommandMessage instance with all required fields
        """
        return CommandMessage(
            service_id="test_sender_id",
            service_type=ServiceType.SYSTEM_CONTROLLER,
            command_id=str(uuid.uuid4()),
            command=command,
            target_service_id=service.service_id,
        )
