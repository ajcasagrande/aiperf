# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Shared fixtures for testing AIPerf communication components.

This file contains fixtures that are automatically discovered by pytest
and made available to test functions in the comms test directory and subdirectories.
"""

import asyncio
import contextlib
import tempfile
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import zmq
import zmq.asyncio
from pydantic import Field

from aiperf.common.comms.base_comms import (
    BaseCommunication,
    CommunicationClientProtocol,
)
from aiperf.common.comms.zmq import (
    BaseZMQClient,
    ZMQIPCCommunication,
    ZMQTCPCommunication,
)
from aiperf.common.config.zmq_config import ZMQIPCConfig, ZMQTCPConfig
from aiperf.common.enums import (
    CommunicationClientAddressType,
    CommunicationClientType,
    MessageType,
    ServiceState,
    ServiceType,
)
from aiperf.common.messages import Message, StatusMessage
from aiperf.common.models import AIPerfBaseModel
from aiperf.common.types import MessageTypeT


class MockTestMessage(Message):
    """Test message for communication testing."""

    message_type: MessageTypeT = MessageType.TEST
    test_data: str = Field(default="test")
    counter: int = Field(default=0)


class MockCommunicationData(AIPerfBaseModel):
    """Data structure to hold state information for mock communication objects."""

    published_messages: dict[MessageType, list[Message]] = Field(default_factory=dict)
    subscriptions: dict[MessageType, list] = Field(default_factory=dict)
    pull_callbacks: dict[MessageType, list] = Field(default_factory=dict)
    push_messages: dict[MessageType, list[Message]] = Field(default_factory=dict)
    requests: dict[str, Message] = Field(default_factory=dict)
    responses: dict[str, Message] = Field(default_factory=dict)
    request_handlers: dict[MessageType, list] = Field(default_factory=dict)

    def clear(self) -> None:
        """Clear all stored data."""
        self.published_messages.clear()
        self.subscriptions.clear()
        self.pull_callbacks.clear()
        self.push_messages.clear()
        self.requests.clear()
        self.responses.clear()
        self.request_handlers.clear()


@pytest.fixture
def mock_zmq_context() -> Generator[MagicMock, None, None]:
    """Fixture to provide a mock ZMQ context."""
    with patch("zmq.asyncio.Context") as mock_context_class:
        mock_context = MagicMock()
        mock_context_class.instance.return_value = mock_context

        # Mock socket creation
        mock_socket = MagicMock()
        mock_socket.bind = AsyncMock()
        mock_socket.connect = AsyncMock()
        mock_socket.send_multipart = AsyncMock()
        mock_socket.recv_multipart = AsyncMock()
        mock_socket.subscribe = MagicMock()
        mock_socket.setsockopt = MagicMock()
        mock_socket.close = AsyncMock()
        mock_context.socket.return_value = mock_socket

        yield mock_context


@pytest.fixture
def mock_zmq_socket() -> Generator[MagicMock, None, None]:
    """Fixture to provide a mock ZMQ socket."""
    mock_socket = MagicMock()
    mock_socket.bind = AsyncMock()
    mock_socket.connect = AsyncMock()
    mock_socket.send_multipart = AsyncMock()
    mock_socket.recv_multipart = AsyncMock()
    mock_socket.subscribe = MagicMock()
    mock_socket.setsockopt = MagicMock()
    mock_socket.close = AsyncMock()
    yield mock_socket


@pytest.fixture
def test_message() -> MockTestMessage:
    """Fixture providing a test message."""
    return MockTestMessage(
        test_data="test_data",
        counter=1,
    )


@pytest.fixture
def status_message() -> StatusMessage:
    """Fixture providing a status message."""
    return StatusMessage(
        service_id="test_service",
        service_type=ServiceType.TEST,
        state=ServiceState.READY,
    )


@pytest.fixture
def tcp_config() -> ZMQTCPConfig:
    """Fixture providing ZMQ TCP configuration."""
    return ZMQTCPConfig(
        host="127.0.0.1",
    )


@pytest.fixture
def ipc_config() -> Generator[ZMQIPCConfig, None, None]:
    """Fixture providing ZMQ IPC configuration."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield ZMQIPCConfig(path=tmp_dir)


@pytest.fixture
async def tcp_communication(
    tcp_config: ZMQTCPConfig,
) -> AsyncGenerator[ZMQTCPCommunication, None]:
    """Fixture providing a ZMQ TCP communication instance."""
    comm = ZMQTCPCommunication(tcp_config)
    try:
        yield comm
    finally:
        await comm.shutdown()


@pytest.fixture
async def ipc_communication(
    ipc_config: ZMQIPCConfig,
) -> AsyncGenerator[ZMQIPCCommunication, None]:
    """Fixture providing a ZMQ IPC communication instance."""
    comm = ZMQIPCCommunication(ipc_config)
    try:
        yield comm
    finally:
        await comm.shutdown()


@pytest.fixture
def mock_communication_data() -> MockCommunicationData:
    """Fixture providing mock communication data."""
    return MockCommunicationData()


@pytest.fixture
def mock_base_communication(
    mock_communication_data: MockCommunicationData,
) -> MagicMock:
    """Fixture providing a mock base communication instance."""
    mock_comm = MagicMock(spec=BaseCommunication)
    mock_comm.initialize = AsyncMock()
    mock_comm.shutdown = AsyncMock()
    mock_comm.is_initialized = True
    mock_comm.stop_requested = False
    mock_comm.get_address = MagicMock(return_value="inproc://test_base_comm")
    mock_comm.mock_data = mock_communication_data
    return mock_comm


@pytest.fixture
def mock_client_protocol() -> MagicMock:
    """Fixture providing a mock client protocol."""
    mock_client = MagicMock(spec=CommunicationClientProtocol)
    mock_client.initialize = AsyncMock()
    mock_client.shutdown = AsyncMock()
    mock_client.is_initialized = True
    return mock_client


@pytest.fixture
async def zmq_base_client(
    mock_zmq_context: MagicMock,
) -> AsyncGenerator[BaseZMQClient, None]:
    """Fixture providing a ZMQ base client instance."""
    client = BaseZMQClient(
        context=mock_zmq_context,
        socket_type=zmq.PUB,
        address="inproc://test_zmq_base_client",
        bind=True,
    )
    try:
        yield client
    finally:
        await client.shutdown()


@pytest.fixture
def sample_addresses() -> dict[CommunicationClientAddressType, str]:
    """Fixture providing sample addresses for testing."""
    return {
        CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND: "inproc://test_proxy_frontend",
        CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND: "inproc://test_proxy_backend",
        CommunicationClientAddressType.CREDIT_DROP: "inproc://test_credit_drop",
        CommunicationClientAddressType.CREDIT_RETURN: "inproc://test_credit_return",
        CommunicationClientAddressType.PARSED_INFERENCE: "inproc://test_records",
    }


@pytest.fixture
def message_types() -> list[MessageType]:
    """Fixture providing a list of message types for testing."""
    return [
        MessageType.STATUS,
        MessageType.HEARTBEAT,
        MessageType.ERROR,
        MessageType.CREDIT_DROP,
        MessageType.CREDIT_RETURN,
    ]


@pytest.fixture
def client_types() -> list[CommunicationClientType]:
    """Fixture providing a list of client types for testing."""
    return [
        CommunicationClientType.PUB,
        CommunicationClientType.SUB,
        CommunicationClientType.PUSH,
        CommunicationClientType.PULL,
        CommunicationClientType.REQUEST,
        CommunicationClientType.REPLY,
    ]


@pytest.fixture
def socket_options() -> dict[int, int]:
    """Fixture providing sample socket options for testing."""
    return {
        zmq.RCVTIMEO: 1000,
        zmq.SNDTIMEO: 1000,
        zmq.LINGER: 0,
    }


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Fixture providing an event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        yield loop
    finally:
        loop.close()


@pytest.fixture
def mock_async_callback() -> AsyncMock:
    """Fixture providing a mock async callback."""
    return AsyncMock()


@pytest.fixture
def mock_sync_callback() -> MagicMock:
    """Fixture providing a mock sync callback."""
    return MagicMock()


@pytest.fixture
def test_timeout() -> float:
    """Fixture providing a test timeout value."""
    return 0.1  # 100ms for fast tests


@pytest.fixture
def multiple_test_messages() -> list[MockTestMessage]:
    """Fixture providing multiple test messages."""
    return [
        MockTestMessage(test_data="msg1", counter=1),
        MockTestMessage(test_data="msg2", counter=2),
        MockTestMessage(test_data="msg3", counter=3),
        MockTestMessage(test_data="msg4", counter=4),
    ]


@pytest.fixture
def cleanup_tasks() -> Generator[list[asyncio.Task], None, None]:
    """Fixture providing a list to track cleanup tasks."""
    tasks = []
    yield tasks
    # Cancel any remaining tasks
    for task in tasks:
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                asyncio.get_event_loop().run_until_complete(task)
