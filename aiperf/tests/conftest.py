"""
This module contains shared fixtures for testing aiperf services.
"""

import uuid
from typing import Any, Callable, Dict, List
from unittest.mock import AsyncMock, patch

import pytest

from aiperf.common.comms.communication import BaseCommunication
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import (
    ServiceRunType,
    CommBackend,
    ClientType,
)
from aiperf.common.models.messages import BaseMessage
from aiperf.tests.utils.async_test_utils import async_noop


@pytest.fixture
def no_sleep(self):
    """Fixture to replace asyncio.sleep with a no-op."""
    with patch("asyncio.sleep", returns=async_noop):
        yield


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
    mock_comm = AsyncMock(spec=BaseCommunication)

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
