# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Shared fixtures for testing AIPerf ZMQ communication components.

This file contains fixtures specifically for ZMQ testing.
"""

import errno
import tempfile
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import zmq
import zmq.asyncio

from aiperf.common.comms.zmq import (
    BaseZMQClient,
    ZMQDealerRequestClient,
    ZMQIPCCommunication,
    ZMQPubClient,
    ZMQPullClient,
    ZMQPushClient,
    ZMQRouterReplyClient,
    ZMQSocketDefaults,
    ZMQSubClient,
    ZMQTCPCommunication,
)
from aiperf.common.config.zmq_config import ZMQIPCConfig, ZMQTCPConfig
from aiperf.common.enums import CommunicationClientAddressType, CommunicationClientType
from tests.comms.conftest import MockTestMessage


@pytest.fixture
def mock_zmq_context_instance() -> Generator[MagicMock, None, None]:
    """Fixture to provide a mock ZMQ context instance."""
    with patch("zmq.asyncio.Context.instance") as mock_instance:
        mock_context = MagicMock()
        mock_instance.return_value = mock_context

        # Mock socket creation
        mock_socket = MagicMock()
        mock_socket.bind = MagicMock()  # Synchronous operation
        mock_socket.connect = MagicMock()  # Synchronous operation
        mock_socket.send_multipart = AsyncMock()
        mock_socket.send_string = AsyncMock()  # Add send_string mock for PUSH client
        # Make recv_multipart raise zmq.Again to prevent background task from processing invalid data
        mock_socket.recv_multipart = AsyncMock(side_effect=zmq.Again())
        mock_socket.recv_string = AsyncMock(
            side_effect=zmq.Again()
        )  # Add recv_string mock for PULL client
        mock_socket.subscribe = MagicMock()
        mock_socket.setsockopt = MagicMock()
        mock_socket.close = MagicMock()  # Synchronous operation
        mock_context.socket.return_value = mock_socket

        yield mock_context


@pytest.fixture
def zmq_socket_defaults() -> dict[int, int]:
    """Fixture providing ZMQ socket defaults."""
    return {
        zmq.RCVTIMEO: ZMQSocketDefaults.RCVTIMEO,
        zmq.SNDTIMEO: ZMQSocketDefaults.SNDTIMEO,
        zmq.TCP_KEEPALIVE: ZMQSocketDefaults.TCP_KEEPALIVE,
        zmq.TCP_KEEPALIVE_IDLE: ZMQSocketDefaults.TCP_KEEPALIVE_IDLE,
        zmq.TCP_KEEPALIVE_INTVL: ZMQSocketDefaults.TCP_KEEPALIVE_INTVL,
        zmq.TCP_KEEPALIVE_CNT: ZMQSocketDefaults.TCP_KEEPALIVE_CNT,
        zmq.IMMEDIATE: ZMQSocketDefaults.IMMEDIATE,
        zmq.LINGER: ZMQSocketDefaults.LINGER,
    }


@pytest.fixture
def zmq_socket_types() -> dict[str, zmq.SocketType]:
    """Fixture providing ZMQ socket types."""
    return {
        "PUB": zmq.PUB,
        "SUB": zmq.SUB,
        "PUSH": zmq.PUSH,
        "PULL": zmq.PULL,
        "REQ": zmq.REQ,
        "REP": zmq.REP,
        "DEALER": zmq.DEALER,
        "ROUTER": zmq.ROUTER,
        "XPUB": zmq.XPUB,
        "XSUB": zmq.XSUB,
    }  # type: ignore[return-value]


@pytest.fixture
def inproc_addresses() -> dict[str, str]:
    """Fixture providing inproc addresses for testing."""
    return {
        "local": "inproc://test_local",
        "any": "inproc://test_any",
        "remote": "inproc://test_remote",
        "port_zero": "inproc://test_port_zero",
    }


@pytest.fixture
def inproc_addresses_alt() -> dict[str, str]:
    """Fixture providing alternative inproc addresses for testing."""
    return {
        "local": "inproc://test_local_alt",
        "abstract": "inproc://test_abstract_alt",
        "relative": "inproc://test_relative_alt",
    }


@pytest.fixture
async def zmq_pub_bind_client(
    mock_zmq_context_instance: MagicMock,
) -> AsyncGenerator[ZMQPubClient, None]:
    """Fixture providing a ZMQ pub client."""
    client = ZMQPubClient(
        context=mock_zmq_context_instance,
        address="inproc://test_pub_client",
        bind=True,
    )
    try:
        yield client
    finally:
        await client.shutdown()


@pytest.fixture
async def zmq_sub_connect_client(
    mock_zmq_context_instance: MagicMock,
) -> AsyncGenerator[ZMQSubClient, None]:
    """Fixture providing a ZMQ sub client."""
    client = ZMQSubClient(
        context=mock_zmq_context_instance,
        address="inproc://test_sub_client",
        bind=False,
    )
    try:
        yield client
    finally:
        await client.shutdown()


@pytest.fixture
async def zmq_push_bind_client(
    mock_zmq_context_instance: MagicMock,
) -> AsyncGenerator[ZMQPushClient, None]:
    """Fixture providing a ZMQ push client."""
    client = ZMQPushClient(
        context=mock_zmq_context_instance,
        address="inproc://test_push_client",
        bind=True,
    )
    try:
        yield client
    finally:
        await client.shutdown()


@pytest.fixture
async def zmq_pull_connect_client(
    mock_zmq_context_instance: MagicMock,
) -> AsyncGenerator[ZMQPullClient, None]:
    """Fixture providing a ZMQ pull client."""
    client = ZMQPullClient(
        context=mock_zmq_context_instance,
        address="inproc://test_pull_client",
        bind=False,
    )
    try:
        yield client
    finally:
        await client.shutdown()


@pytest.fixture
async def zmq_request_connect_client(
    mock_zmq_context_instance: MagicMock,
) -> AsyncGenerator[ZMQDealerRequestClient, None]:
    """Fixture providing a ZMQ request client."""
    client = ZMQDealerRequestClient(
        context=mock_zmq_context_instance,
        address="inproc://test_request_client",
        bind=False,
    )
    try:
        yield client
    finally:
        await client.shutdown()


@pytest.fixture
async def zmq_reply_bind_client(
    mock_zmq_context_instance: MagicMock,
) -> AsyncGenerator[ZMQRouterReplyClient, None]:
    """Fixture providing a ZMQ reply client."""
    client = ZMQRouterReplyClient(
        context=mock_zmq_context_instance,
        address="inproc://test_reply_client",
        bind=True,
    )
    try:
        yield client
    finally:
        await client.shutdown()


@pytest.fixture
async def zmq_base_bind_client_pub(
    mock_zmq_context_instance: MagicMock,
) -> AsyncGenerator[BaseZMQClient, None]:
    """Fixture providing a base ZMQ client with PUB socket."""
    client = BaseZMQClient(
        context=mock_zmq_context_instance,
        socket_type=zmq.PUB,
        address="inproc://test_base_client_pub",
        bind=True,
    )
    try:
        yield client
    finally:
        await client.shutdown()


@pytest.fixture
async def zmq_base_connect_client_sub(
    mock_zmq_context_instance: MagicMock,
) -> AsyncGenerator[BaseZMQClient, None]:
    """Fixture providing a base ZMQ client with SUB socket."""
    client = BaseZMQClient(
        context=mock_zmq_context_instance,
        socket_type=zmq.SUB,
        address="inproc://test_base_client_sub",
        bind=False,
    )
    try:
        yield client
    finally:
        await client.shutdown()


@pytest.fixture
def zmq_tcp_config_custom() -> ZMQTCPConfig:
    """Fixture providing custom ZMQ TCP configuration."""
    return ZMQTCPConfig(
        host="192.168.1.1",
    )


@pytest.fixture
def zmq_ipc_config_custom() -> Generator[ZMQIPCConfig, None]:
    """Fixture providing custom ZMQ IPC configuration."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield ZMQIPCConfig(path=tmp_dir)


@pytest.fixture
async def zmq_tcp_communication_custom(
    zmq_tcp_config_custom: ZMQTCPConfig,
) -> AsyncGenerator[ZMQTCPCommunication, None]:
    """Fixture providing a custom ZMQ TCP communication instance."""
    comm = ZMQTCPCommunication(zmq_tcp_config_custom)
    try:
        yield comm
    finally:
        await comm.shutdown()


@pytest.fixture
async def zmq_ipc_communication_custom(
    zmq_ipc_config_custom: ZMQIPCConfig,
) -> AsyncGenerator[ZMQIPCCommunication, None]:
    """Fixture providing a custom ZMQ IPC communication instance."""
    comm = ZMQIPCCommunication(zmq_ipc_config_custom)
    try:
        yield comm
    finally:
        await comm.shutdown()


@pytest.fixture
def client_socket_combinations() -> list[
    tuple[CommunicationClientType, zmq.SocketType]
]:
    """Fixture providing client type and socket type combinations."""
    return [
        (CommunicationClientType.PUB, zmq.PUB),
        (CommunicationClientType.SUB, zmq.SUB),
        (CommunicationClientType.PUSH, zmq.PUSH),
        (CommunicationClientType.PULL, zmq.PULL),
        (CommunicationClientType.REQUEST, zmq.DEALER),
        (CommunicationClientType.REPLY, zmq.ROUTER),
    ]  # type: ignore[return-value]


@pytest.fixture
def address_type_combinations() -> list[tuple[CommunicationClientAddressType, str]]:
    """Fixture providing address type and expected address combinations."""
    return [
        (
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
            "inproc://test_addr_proxy_frontend",
        ),
        (
            CommunicationClientAddressType.EVENT_BUS_PROXY_BACKEND,
            "inproc://test_addr_proxy_backend",
        ),
        (CommunicationClientAddressType.CREDIT_DROP, "inproc://test_addr_credit_drop"),
        (
            CommunicationClientAddressType.CREDIT_RETURN,
            "inproc://test_addr_credit_return",
        ),
        (CommunicationClientAddressType.RECORDS, "inproc://test_addr_records"),
    ]


@pytest.fixture
def mock_message_handler() -> MagicMock:
    """Fixture providing a mock message handler."""
    handler = MagicMock()
    handler.return_value = AsyncMock()
    return handler


@pytest.fixture
def mock_message_callback() -> AsyncMock:
    """Fixture providing a mock message callback."""
    return AsyncMock()


@pytest.fixture
def bind_connect_combinations() -> list[tuple[bool, str]]:
    """Fixture providing bind/connect combinations."""
    return [
        (True, "BIND"),
        (False, "CONNECT"),
    ]


@pytest.fixture
def socket_options_combinations() -> list[dict[int, int]]:
    """Fixture providing various socket options combinations."""
    return [
        {},  # No options
        {zmq.RCVTIMEO: 5000},  # Only receive timeout
        {zmq.SNDTIMEO: 3000},  # Only send timeout
        {zmq.LINGER: 1000},  # Only linger
        {zmq.RCVTIMEO: 2000, zmq.SNDTIMEO: 2000},  # Both timeouts
        {zmq.RCVTIMEO: 1000, zmq.SNDTIMEO: 1000, zmq.LINGER: 0},  # All options
    ]


@pytest.fixture
def client_id_generator() -> Generator[str, None, None]:
    """Fixture providing unique client IDs."""
    counter = 0
    while True:
        counter += 1
        yield f"test_client_{counter}"


@pytest.fixture
def test_messages_batch() -> list[MockTestMessage]:
    """Fixture providing a batch of test messages."""
    from aiperf.common.enums import MessageType

    return [
        MockTestMessage(
            message_type=MessageType.STATUS, test_data="batch_msg_1", counter=1
        ),
        MockTestMessage(
            message_type=MessageType.HEARTBEAT, test_data="batch_msg_2", counter=2
        ),
        MockTestMessage(
            message_type=MessageType.COMMAND, test_data="batch_msg_3", counter=3
        ),
        MockTestMessage(
            message_type=MessageType.ERROR, test_data="batch_msg_4", counter=4
        ),
        MockTestMessage(
            message_type=MessageType.NOTIFICATION, test_data="batch_msg_5", counter=5
        ),
    ]


@pytest.fixture
def mock_zmq_error_scenarios() -> dict[str, Exception]:
    """Fixture providing various ZMQ error scenarios."""
    return {
        "context_terminated": zmq.ContextTerminated(),
        "again": zmq.Again(),
        "invalid_socket": zmq.ZMQError(errno=errno.EINVAL, msg="Invalid socket"),
        "address_in_use": zmq.ZMQError(
            errno=errno.EADDRINUSE, msg="Address already in use"
        ),
        "timeout": zmq.ZMQError(errno=errno.ETIMEDOUT, msg="Operation timed out"),
    }


@pytest.fixture
def concurrent_client_count() -> int:
    """Fixture providing the number of concurrent clients for stress testing."""
    return 10


@pytest.fixture
def message_batch_size() -> int:
    """Fixture providing the batch size for message testing."""
    return 100


@pytest.fixture
def stress_test_timeout() -> float:
    """Fixture providing timeout for stress tests."""
    return 30.0  # 30 seconds


@pytest.fixture
def performance_test_iterations() -> int:
    """Fixture providing number of iterations for performance tests."""
    return 1000
