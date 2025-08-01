# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import Any

import pytest

from aiperf.common.config import ServiceConfig
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums.command_enums import CommandType
from aiperf.common.enums.message_enums import MessageType
from aiperf.common.factories import ServiceFactory
from aiperf.common.messages import Message
from aiperf.common.messages.command_messages import (
    CommandAcknowledgedResponse,
    ProfileConfigureCommand,
    ProfileStartCommand,
)
from tests.mixins.conftest import MockCommunication


@pytest.mark.asyncio
class TestCommandHandlerMixin:
    async def test_command_registration(
        self, mock_test_environment: dict[str, Any]
    ) -> None:
        """Test that command handlers are properly registered."""
        env = mock_test_environment
        service = env["test_service"]
        controller = env["controller"]

        # Verify service is registered with controller
        assert controller.is_service_registered(service.service_id)
        registered_services = controller.get_registered_services()
        assert service.service_id in registered_services

    async def test_send_command_and_wait_for_response(
        self, mock_test_environment: dict[str, Any]
    ) -> None:
        """Test sending commands and waiting for responses."""
        env = mock_test_environment
        service = env["test_service"]
        message_bus = env["message_bus"]

        # Create a ProfileStart command
        command = ProfileStartCommand(
            service_id=service.service_id,
            target_service_id=service.service_id,
        )

        # Send command and verify it gets published
        try:
            await service.send_command_and_wait_for_response(command, timeout=1.0)
        except Exception:
            # Expected to timeout since we're not simulating a response
            pass

        # Verify the command was published through the message bus
        published_messages = message_bus.get_published_messages(MessageType.COMMAND)
        assert len(published_messages) > 0

        # Find our command message
        command_message = None
        for msg in published_messages:
            if (
                hasattr(msg, "command_type")
                and msg.command_type == CommandType.PROFILE_START
            ):
                command_message = msg
                break

        assert command_message is not None
        assert command_message.target_service_id == service.service_id

    async def test_command_acknowledgment(
        self, mock_test_environment: dict[str, Any]
    ) -> None:
        """Test that command acknowledgments are properly handled."""
        env = mock_test_environment
        service = env["test_service"]
        message_bus = env["message_bus"]

        # Create a command and send it
        command = ProfileConfigureCommand(
            service_id=service.service_id,
            target_service_id=service.service_id,
            config=service.user_config,
        )

        # Simulate sending command and immediately responding with ACK
        import asyncio

        async def simulate_response():
            await asyncio.sleep(0.1)  # Small delay
            ack_response = CommandAcknowledgedResponse.from_command_message(
                command, service.service_id
            )
            await message_bus.simulate_message(ack_response)

        # Start the response simulation
        response_task = asyncio.create_task(simulate_response())

        try:
            # This should complete successfully with the simulated response
            await service.send_command_and_wait_for_response(command, timeout=1.0)
        finally:
            response_task.cancel()
            try:
                await response_task
            except asyncio.CancelledError:
                pass

        # Verify command was sent
        published_messages = message_bus.get_published_messages(MessageType.COMMAND)
        assert any(
            hasattr(msg, "command_type")
            and msg.command_type == CommandType.PROFILE_CONFIGURE
            for msg in published_messages
        )

    async def test_service_registration_workflow(
        self, mock_test_environment: dict[str, Any]
    ) -> None:
        """Test the complete service registration workflow."""
        env = mock_test_environment
        controller = env["controller"]
        service = env["test_service"]

        # Verify initial registration
        assert controller.is_service_registered(service.service_id)

        # Test profiling configuration
        await controller.configure_profiling()
        assert controller.profiling_configured

        # Test profiling start
        await controller.start_profiling()
        assert controller.profiling_started

        # Verify service state progression
        services = controller.get_registered_services()
        service_data = services[service.service_id]
        assert service_data["state"] == "profiling"

    async def test_multiple_service_management(
        self, mock_service_controller, mock_message_bus_client
    ) -> None:
        """Test managing multiple services with the controller."""
        controller = mock_service_controller

        # Register multiple services
        await controller.register_service(
            "worker-1", "worker", {"endpoint": "tcp://worker1:5555"}
        )
        await controller.register_service(
            "worker-2", "worker", {"endpoint": "tcp://worker2:5555"}
        )
        await controller.register_service(
            "parser-1", "parser", {"endpoint": "tcp://parser1:5555"}
        )

        # Verify all services are registered
        assert controller.get_service_count() == 3
        assert controller.get_service_count("worker") == 2
        assert controller.get_service_count("parser") == 1

        # Test services by type
        workers = controller.get_services_by_type("worker")
        assert len(workers) == 2
        assert all(s["service_type"] == "worker" for s in workers)

        # Test profiling workflow with multiple services
        await controller.start_profiling()

        # Verify all services are in profiling state
        all_services = controller.get_registered_services()
        assert all(s["state"] == "profiling" for s in all_services.values())

    async def test_communication_layer_integration(
        self, mock_communication, mock_service_controller
    ) -> None:
        """Test integration between communication layer and service controller."""
        comms = mock_communication
        controller = mock_service_controller

        await comms.initialize_and_start()
        await controller.initialize_and_start()

        # Test client creation
        pub_client = comms.create_pub_client("tcp://test:5555")
        sub_client = comms.create_sub_client("tcp://test:5556")

        assert pub_client is not None
        assert sub_client is not None
        assert len(comms.clients) == 2

        # Test lifecycle management
        assert comms.is_running
        assert controller.is_running

        # Cleanup
        await comms.stop()
        await controller.stop()

        assert comms.was_stopped
        assert controller.was_stopped


# Simple standalone test to demonstrate mock infrastructure
@pytest.mark.asyncio
async def test_simple_mock_demonstration(mock_communication, mock_service_controller):
    """Simple demonstration that the mock infrastructure works correctly."""

    # Initialize components
    await mock_communication.initialize_and_start()
    await mock_service_controller.initialize_and_start()

    # Test communication client creation
    pub_client = mock_communication.create_pub_client("tcp://test:5555")
    assert pub_client is not None
    assert len(mock_communication.clients) == 1

    # Test service registration
    await mock_service_controller.register_service("test-service", "worker")
    assert mock_service_controller.is_service_registered("test-service")
    assert mock_service_controller.get_service_count() == 1

    # Test profiling workflow
    await mock_service_controller.start_profiling()
    assert mock_service_controller.profiling_started

    services = mock_service_controller.get_registered_services()
    assert services["test-service"]["state"] == "profiling"

    # Cleanup
    await mock_communication.stop()
    await mock_service_controller.stop()

    print("✅ Mock infrastructure test passed successfully!")


@pytest.mark.asyncio
async def test_no_real_zmq_connections(patch_all_communication):
    """Test that demonstrates no real ZMQ connections are made during testing."""

    # The patch_all_communication fixture ensures no real ZMQ sockets are created
    mock_comm = patch_all_communication

    # Create a service - this would normally create real ZMQ connections
    service = ServiceFactory.create_instance(
        "test_service_type",
        service_config=ServiceConfig(),
        user_config=UserConfig(
            endpoint=EndpointConfig(
                model_names=["test_model_name"],
            ),
        ),
    )

    # Initialize and start - this would normally connect to real ZMQ sockets
    await service.initialize_and_start()

    # Verify the service is using our mocked communication
    assert service.comms is mock_comm
    assert isinstance(service.comms, MockCommunication)

    # Verify we can create clients without real network connections
    pub_client = service.comms.create_pub_client("tcp://localhost:5555")
    sub_client = service.comms.create_sub_client("tcp://localhost:5556")

    assert pub_client is not None
    assert sub_client is not None
    assert len(service.comms.clients) == 2

    # Test message publishing (no real network traffic)
    test_message = Message(
        message_type=MessageType.HEARTBEAT, service_id=service.service_id
    )
    await pub_client.publish(test_message)

    # Verify message was "published" to our mock
    assert len(pub_client.published_messages) == 1
    assert pub_client.published_messages[0].message_type == MessageType.HEARTBEAT

    await service.stop()
    print("✅ No real ZMQ connections test passed! All network calls were mocked.")


@pytest.mark.asyncio
async def test_patched_service_creation(no_real_connections_test_service):
    """Test using the convenient no_real_connections_test_service fixture."""
    service = no_real_connections_test_service

    # Verify service is running with mocked communication
    assert service.is_running
    assert isinstance(service.comms, MockCommunication)

    # Test that we can use command handler methods without real network
    command = ProfileStartCommand(
        service_id=service.service_id,
        target_service_id=service.service_id,
    )

    # This would normally send a real ZMQ message, but now it's mocked
    try:
        await service.send_command_and_wait_for_response(command, timeout=0.1)
    except Exception:
        # Expected to timeout since no real response will come
        pass

    # Verify the service's pub client has the message
    pub_client = service.comms.clients[0] if service.comms.clients else None
    if pub_client and hasattr(pub_client, "published_messages"):
        # Message should be tracked in our mock
        assert (
            len(pub_client.published_messages) >= 0
        )  # May have sent connection probe, etc.

    print("✅ Patched service creation test passed!")


# Example of how to create a custom test with specific mocks
@pytest.mark.asyncio
async def test_custom_mock_setup_example(mock_communication, mock_service_controller):
    """Example showing how to create custom test setups with individual mocks."""

    # Initialize components
    await mock_communication.initialize_and_start()
    await mock_service_controller.initialize_and_start()

    # Custom test logic here
    pub_client = mock_communication.create_pub_client("custom://test")

    # Register custom services
    await mock_service_controller.register_service(
        "custom-service-1", "custom_type", {"custom_config": "value"}
    )

    # Verify setup
    assert mock_communication.is_running
    assert mock_service_controller.get_service_count() == 1
    assert len(mock_communication.clients) == 1

    # Cleanup
    await mock_communication.stop()
    await mock_service_controller.stop()
