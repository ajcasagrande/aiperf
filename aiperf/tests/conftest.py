"""
This module contains shared fixtures for testing aiperf services.
"""

import asyncio
import uuid
from typing import Any, Callable, Dict, List, Type
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import BaseModel

from aiperf.common.comms.communication import Communication
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import (
    ServiceRunType,
    ServiceState,
    ServiceType,
    Topic,
    CommBackend,
    ClientType,
)
from aiperf.common.models.messages import BaseMessage
from aiperf.common.service.base import ServiceBase

# Configure pytest-asyncio to run all async tests
pytestmark = pytest.mark.asyncio


@pytest.fixture
def service_id() -> str:
    """Generate a unique service ID for testing."""
    return uuid.uuid4().hex


@pytest.fixture
def service_config() -> ServiceConfig:
    """Create a service configuration for testing."""
    return ServiceConfig(
        service_run_type=ServiceRunType.MULTIPROCESSING,
        comm_backend=CommBackend.ZMQ_TCP,
    )


@pytest.fixture
def mock_communication() -> AsyncMock:
    """Create a mock communication object with publishing and subscription tracking."""
    mock_comm = AsyncMock(spec=Communication)

    # Configure basic returns for methods
    mock_comm.initialize.return_value = True
    mock_comm.subscribe.return_value = True
    mock_comm.publish.return_value = True
    mock_comm.create_clients.return_value = True
    mock_comm.pull.return_value = True
    mock_comm.push.return_value = True

    # Store published messages for verification
    mock_comm.published_messages: Dict[Any, List[BaseMessage]] = {}

    async def mock_publish(
        client_type: ClientType, topic: Any, message: BaseMessage
    ) -> bool:
        # Use the topic as the key, whether it's an enum or string
        topic_key = topic

        # Initialize list for this topic if needed
        if topic_key not in mock_comm.published_messages:
            mock_comm.published_messages[topic_key] = []

        # Store the message
        mock_comm.published_messages[topic_key].append(message)
        return True

    mock_comm.publish.side_effect = mock_publish

    # Store subscription callbacks
    mock_comm.subscriptions: Dict[str, Callable] = {}

    async def mock_subscribe(
        client_type: ClientType, topic: str, callback: Callable
    ) -> bool:
        mock_comm.subscriptions[topic] = callback
        return True

    mock_comm.subscribe.side_effect = mock_subscribe

    return mock_comm


@pytest.fixture
async def mock_service_base(service_id, service_config, mock_communication):
    """Create a mock service base for testing."""

    # Create a concrete implementation of the abstract ServiceBase
    class ConcreteService(ServiceBase):
        async def _initialize(self) -> None:
            pass

        async def _on_start(self) -> None:
            pass

        async def _on_stop(self) -> None:
            pass

        async def _cleanup(self) -> None:
            pass

        async def _process_message(self, topic: Topic, message: BaseMessage) -> None:
            pass

    with patch(
        "aiperf.common.comms.communication_factory.CommunicationFactory.create_communication",
        return_value=mock_communication,
    ):
        service = ConcreteService(service_type=ServiceType.TEST, config=service_config)
        service.service_id = service_id

        # Initialize but don't run
        await service._initialize()

        try:
            yield service
        finally:
            # Clean up heartbeat task
            if service.heartbeat_task and not service.heartbeat_task.done():
                service.heartbeat_task.cancel()


@pytest.fixture
def mock_message_factory():
    """Factory for creating mock messages of different types."""

    def _create_message(message_type: Type[BaseModel], **kwargs) -> Any:
        return message_type(**kwargs)

    return _create_message


@pytest.fixture
def mock_event_loop():
    """Create an isolated event loop for testing asynchronous code."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def parametrize_services():
    """Decorator for parameterizing test functions with service classes."""

    def _parametrize_services(*service_classes):
        return pytest.mark.parametrize("service_class", service_classes)

    return _parametrize_services


@pytest.fixture
def mock_dependent_services():
    """
    Mock all dependent services that a service might interact with.
    Returns a dictionary of mock services keyed by service type.
    """
    mock_services = {}

    for service_type in ServiceType:
        # Skip abstract types
        if service_type in [ServiceType.UNKNOWN, ServiceType.TEST]:
            continue

        mock_service = AsyncMock()
        mock_service.service_id = uuid.uuid4().hex
        mock_service.service_type = service_type
        mock_service.state = ServiceState.RUNNING
        mock_services[service_type.value] = mock_service

    return mock_services


@pytest.fixture
async def simulate_message_flow():
    """
    Fixture that provides a function to simulate message flow between services.
    This allows testing complex interactions without actually running the services.
    """

    async def _simulate_message(service, topic: Topic, message_data: Dict[str, Any]):
        """Simulate receiving a message on a specific topic."""
        message = BaseMessage.model_validate(message_data)
        await service._process_message(topic, message)

    yield _simulate_message
