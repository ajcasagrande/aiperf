# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
ZMQ Communication Test Fixtures.

This module provides specialized fixtures for testing ZMQ communication components,
including proxies, clients, and configurations.
"""

import asyncio
import tempfile
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, suppress
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import zmq
import zmq.asyncio

from aiperf.common.config.zmq_config import ZMQIPCProxyConfig, ZMQTCPProxyConfig
from aiperf.common.enums import ZMQProxyType
from aiperf.common.factories import ZMQProxyFactory
from aiperf.common.messages import TestMessage


@pytest.fixture
def test_message() -> TestMessage:
    """Provide a test message for testing."""
    return TestMessage()


@pytest.fixture
def zmq_context() -> Generator[zmq.asyncio.Context, None, None]:
    """Provide a real ZMQ context for integration tests."""
    context = zmq.asyncio.Context()
    yield context
    context.term()


@pytest.fixture
def mock_zmq_context() -> Generator[MagicMock, None, None]:
    """Provide a mock ZMQ context for unit tests."""
    context = MagicMock(spec=zmq.asyncio.Context)
    mock_socket = MagicMock(spec=zmq.asyncio.Socket)
    context.socket.return_value = mock_socket
    yield context


@pytest.fixture
def temp_ipc_config() -> Generator[ZMQIPCProxyConfig, None, None]:
    """Provide a temporary IPC proxy configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield ZMQIPCProxyConfig(path=tmpdir, name="test_proxy")


@pytest.fixture
def tcp_config() -> ZMQTCPProxyConfig:
    """Provide a TCP proxy configuration for testing."""
    return ZMQTCPProxyConfig(host="127.0.0.1", frontend_port=15555, backend_port=15556)


@pytest.fixture
def tcp_config_with_control() -> ZMQTCPProxyConfig:
    """Provide a TCP proxy configuration with control and capture enabled."""
    return ZMQTCPProxyConfig(
        host="127.0.0.1",
        frontend_port=15555,
        backend_port=15556,
        control_port=15557,
        capture_port=15558,
    )


@pytest.fixture
def ipc_config_with_control() -> Generator[ZMQIPCProxyConfig, None, None]:
    """Provide an IPC proxy configuration with control and capture enabled."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield ZMQIPCProxyConfig(
            path=tmpdir, name="test_proxy", enable_control=True, enable_capture=True
        )


@pytest.fixture
def mock_proxy_sockets() -> dict[str, AsyncMock]:
    """Provide mocks for proxy frontend and backend sockets."""
    return {
        "frontend": AsyncMock(),
        "backend": AsyncMock(),
        "control": AsyncMock(),
        "capture": AsyncMock(),
    }


@pytest.fixture
async def proxy_factory_instances() -> dict[ZMQProxyType, type]:
    """Provide proxy class instances from the factory for testing."""
    return {
        proxy_type: ZMQProxyFactory._registry[proxy_type]
        for proxy_type in [
            ZMQProxyType.XPUB_XSUB,
            ZMQProxyType.DEALER_ROUTER,
            ZMQProxyType.PUSH_PULL,
        ]
    }


@asynccontextmanager
async def managed_proxy(
    proxy_type: ZMQProxyType,
    context: zmq.asyncio.Context,
    config: ZMQIPCProxyConfig | ZMQTCPProxyConfig,
    start_proxy: bool = True,
) -> AsyncGenerator[tuple[Any, ZMQIPCProxyConfig | ZMQTCPProxyConfig], None]:
    """
    Context manager for creating and managing a proxy lifecycle.

    Args:
        proxy_type: The type of proxy to create
        context: ZMQ context to use
        config: Proxy configuration
        start_proxy: Whether to start the proxy automatically

    Yields:
        Tuple of (proxy instance, config)
    """
    proxy = ZMQProxyFactory.create_instance(
        proxy_type, context=context, zmq_proxy_config=config
    )

    proxy_task = None
    try:
        if start_proxy:
            proxy_task = asyncio.create_task(proxy.run())
            # Give proxy time to initialize
            await asyncio.sleep(0.1)

        yield proxy, config

    finally:
        # Cleanup
        if proxy_task and not proxy_task.done():
            proxy_task.cancel()
            with suppress(asyncio.CancelledError, asyncio.TimeoutError):
                await asyncio.wait_for(proxy_task, timeout=1.0)

        await proxy.stop()


@pytest.fixture
def managed_proxy_fixture(zmq_context):
    """Provide the managed_proxy context manager as a fixture."""
    return lambda proxy_type, config, start_proxy=True: managed_proxy(
        proxy_type, zmq_context, config, start_proxy
    )


# Parametrized fixtures for testing all proxy types
@pytest.fixture(
    params=[ZMQProxyType.XPUB_XSUB, ZMQProxyType.DEALER_ROUTER, ZMQProxyType.PUSH_PULL]
)
def proxy_type(request) -> ZMQProxyType:
    """Parametrized fixture that provides all proxy types."""
    return request.param


@pytest.fixture(params=["ipc_config", "tcp_config"])
def proxy_config(request, temp_ipc_config, tcp_config):
    """Parametrized fixture that provides different config types."""
    if request.param == "ipc_config":
        return temp_ipc_config
    else:
        return tcp_config


@pytest.fixture
def socket_type_mapping() -> dict[ZMQProxyType, tuple[int, int]]:
    """Provide expected socket types for each proxy type."""
    return {
        ZMQProxyType.XPUB_XSUB: (zmq.XSUB, zmq.XPUB),
        ZMQProxyType.DEALER_ROUTER: (zmq.ROUTER, zmq.DEALER),
        ZMQProxyType.PUSH_PULL: (zmq.PULL, zmq.PUSH),
    }


# Error simulation fixtures
@pytest.fixture
def mock_failing_socket():
    """Provide a mock socket that fails during operations."""
    mock_socket = AsyncMock()
    mock_socket.initialize.side_effect = Exception("Socket initialization failed")
    return mock_socket


@pytest.fixture
def mock_timeout_socket():
    """Provide a mock socket that times out during operations."""
    mock_socket = AsyncMock()
    mock_socket.receive.side_effect = asyncio.TimeoutError("Operation timed out")
    return mock_socket
