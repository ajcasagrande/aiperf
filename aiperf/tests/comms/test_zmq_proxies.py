# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive tests for ZMQ Proxy implementations.

This module tests the critical functionality of ZMQ proxies including:
- Factory registration and creation
- Proxy lifecycle (initialization, running, shutdown)
- Configuration validation and socket binding
- Error handling and edge cases
- Message forwarding correctness (integration tests)
"""

import asyncio
import contextlib
import logging
import tempfile
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import zmq
import zmq.asyncio

from aiperf.common.comms.zmq.clients import (
    BaseZMQProxy,
    ZMQDealerReqClient,
    ZMQPubClient,
    ZMQPullClient,
    ZMQPushClient,
    ZMQRouterRepClient,
    ZMQSubClient,
)
from aiperf.common.config.zmq_config import ZMQIPCProxyConfig, ZMQTCPProxyConfig
from aiperf.common.enums import MessageType, ZMQProxyType
from aiperf.common.exceptions import CommunicationError, CommunicationErrorReason
from aiperf.common.factories import ZMQProxyFactory
from aiperf.common.messages import ConversationRequestMessage, Message, TestMessage
from aiperf.tests.base_test_service import real_sleep
from aiperf.tests.utils.async_test_utils import AwaitableMock

logger = logging.getLogger("aiperf")


class TestZMQProxyConfiguration:
    """Test proxy configuration and validation."""

    @pytest.mark.parametrize("config_class", [ZMQTCPProxyConfig, ZMQIPCProxyConfig])
    def test_proxy_config_properties(self, config_class):
        """Test that proxy configs properly generate addresses."""
        if config_class == ZMQTCPProxyConfig:
            config = config_class(
                host="localhost", frontend_port=5555, backend_port=5556
            )
            assert config.frontend_address == "tcp://localhost:5555"
            assert config.backend_address == "tcp://localhost:5556"
        else:
            with tempfile.TemporaryDirectory() as tmpdir:
                config = config_class(path=tmpdir, name="test_proxy")
                assert (
                    config.frontend_address == f"ipc://{tmpdir}/test_proxy_frontend.ipc"
                )
                assert (
                    config.backend_address == f"ipc://{tmpdir}/test_proxy_backend.ipc"
                )

    def test_tcp_config_optional_addresses(self):
        """Test TCP config with optional control and capture addresses."""
        config = ZMQTCPProxyConfig(
            host="localhost",
            frontend_port=5555,
            backend_port=5556,
            control_port=5557,
            capture_port=5558,
        )

        assert config.control_address == "tcp://localhost:5557"
        assert config.capture_address == "tcp://localhost:5558"

    def test_ipc_config_optional_addresses(self):
        """Test IPC config with optional control and capture addresses."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ZMQIPCProxyConfig(
                path=tmpdir, name="test_proxy", enable_control=True, enable_capture=True
            )

            assert config.control_address == f"ipc://{tmpdir}/test_proxy_control.ipc"
            assert config.capture_address == f"ipc://{tmpdir}/test_proxy_capture.ipc"


class TestZMQProxyFactory:
    """Test the ZMQ proxy factory registration and creation."""

    def test_factory_registration(self):
        """Test that all proxy types are properly registered."""
        supported_types = {
            ZMQProxyType.XPUB_XSUB,
            ZMQProxyType.DEALER_ROUTER,
            ZMQProxyType.PUSH_PULL,
        }

        for proxy_type in supported_types:
            assert ZMQProxyFactory.is_registered(proxy_type), (
                f"{proxy_type} not registered"
            )

    @pytest.mark.parametrize(
        "proxy_type",
        [ZMQProxyType.XPUB_XSUB, ZMQProxyType.DEALER_ROUTER, ZMQProxyType.PUSH_PULL],
    )
    def test_factory_creation(self, proxy_type):
        """Test factory can create proxy instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ZMQIPCProxyConfig(path=tmpdir, name=f"test_{proxy_type.value}")

            proxy = ZMQProxyFactory.create_instance(
                proxy_type, context=zmq.asyncio.Context(), zmq_proxy_config=config
            )

            assert isinstance(proxy, BaseZMQProxy)
            assert proxy.frontend_address == config.frontend_address
            assert proxy.backend_address == config.backend_address

    def test_factory_creation_with_invalid_type(self):
        """Test factory raises error for invalid proxy type."""
        from aiperf.common.exceptions import FactoryCreationError

        with pytest.raises(FactoryCreationError):
            ZMQProxyFactory.create_instance(
                "invalid_proxy_type",  # type: ignore
                context=zmq.asyncio.Context(),
                zmq_proxy_config=ZMQIPCProxyConfig(),
            )


class TestZMQProxyLifecycle:
    """Test proxy lifecycle management (initialization, running, shutdown)."""

    @pytest.fixture
    async def mock_proxy_context(self):
        """Create a mocked ZMQ context for testing."""
        context = MagicMock(spec=zmq.asyncio.Context)
        mock_socket = MagicMock(spec=zmq.asyncio.Socket)
        context.socket.return_value = mock_socket
        return context

    @pytest.fixture
    async def test_config(self):
        """Create a test configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield ZMQIPCProxyConfig(path=tmpdir, name="test_proxy")

    @pytest.mark.asyncio
    async def test_proxy_initialization(self, mock_proxy_context, test_config):
        """Test proxy initialization sets up sockets correctly."""
        proxy = ZMQProxyFactory.create_instance(
            ZMQProxyType.PUSH_PULL,
            context=mock_proxy_context,
            zmq_proxy_config=test_config,
        )

        # Mock the socket initialization
        proxy.frontend_socket.initialize = AsyncMock()
        proxy.backend_socket.initialize = AsyncMock()

        await proxy._initialize()

        proxy.frontend_socket.initialize.assert_called_once()
        proxy.backend_socket.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_proxy_initialization_failure(self, mock_proxy_context, test_config):
        """Test proxy handles initialization failures gracefully."""
        proxy = ZMQProxyFactory.create_instance(
            ZMQProxyType.PUSH_PULL,
            context=mock_proxy_context,
            zmq_proxy_config=test_config,
        )

        # Mock initialization failure
        proxy.frontend_socket.initialize = AsyncMock(
            side_effect=Exception("Init failed")
        )
        proxy.backend_socket.initialize = AsyncMock()

        with pytest.raises(Exception, match="Init failed"):
            await proxy._initialize()

    @pytest.mark.asyncio
    async def test_proxy_shutdown(self, mock_proxy_context, test_config):
        """Test proxy shutdown cleans up resources properly."""
        proxy = ZMQProxyFactory.create_instance(
            ZMQProxyType.PUSH_PULL,
            context=mock_proxy_context,
            zmq_proxy_config=test_config,
        )

        # Mock both the socket objects and their shutdown methods
        frontend_mock = AsyncMock()
        frontend_mock.shutdown = AsyncMock(return_value=None)
        backend_mock = AsyncMock()
        backend_mock.shutdown = AsyncMock(return_value=None)

        proxy.frontend_socket = frontend_mock
        proxy.backend_socket = backend_mock

        # Ensure control and capture clients are None
        proxy.control_client = None
        proxy.capture_client = None

        proxy.monitor_task = None
        proxy.proxy_task = AwaitableMock()

        with contextlib.suppress(asyncio.CancelledError):
            await proxy.stop()

        proxy.proxy_task.cancel.assert_called_once()
        frontend_mock.shutdown.assert_called_once()
        backend_mock.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_proxy_from_config_creation(self, test_config):
        """Test creating proxy from config class method."""
        proxy_class = ZMQProxyFactory._registry[ZMQProxyType.PUSH_PULL]

        proxy = proxy_class.from_config(test_config)
        assert proxy is not None
        assert isinstance(proxy, BaseZMQProxy)

    @pytest.mark.asyncio
    async def test_proxy_from_config_none(self):
        """Test creating proxy from None config returns None."""
        proxy_class = ZMQProxyFactory._registry[ZMQProxyType.PUSH_PULL]

        proxy = proxy_class.from_config(None)
        assert proxy is None


class TestZMQProxySocketTypes:
    """Test that proxies create correct socket types."""

    @pytest.mark.parametrize(
        "proxy_type,expected_frontend,expected_backend",
        [
            (ZMQProxyType.XPUB_XSUB, zmq.XSUB, zmq.XPUB),
            (ZMQProxyType.DEALER_ROUTER, zmq.ROUTER, zmq.DEALER),
            (ZMQProxyType.PUSH_PULL, zmq.PULL, zmq.PUSH),
        ],
    )
    def test_proxy_socket_types(self, proxy_type, expected_frontend, expected_backend):
        """Test that proxies create sockets with correct types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ZMQIPCProxyConfig(path=tmpdir, name=f"test_{proxy_type.value}")

            proxy = ZMQProxyFactory.create_instance(
                proxy_type, context=zmq.asyncio.Context(), zmq_proxy_config=config
            )

            # The socket types are set during BaseZMQClient initialization
            # We verify through the socket_type property
            assert proxy.frontend_socket.socket_type == expected_frontend
            assert proxy.backend_socket.socket_type == expected_backend


@pytest.mark.integration
class TestZMQProxyIntegration:
    """Integration tests for ZMQ proxy message forwarding.

    These tests use real ZMQ sockets to verify message forwarding works correctly.
    They are marked as integration tests and can be run separately if needed.
    """

    @pytest.fixture
    def zmq_context(self):
        """Create a real ZMQ context for integration tests."""
        context = zmq.asyncio.Context()
        yield context
        context.term()

    @asynccontextmanager
    async def _setup_proxy_with_cleanup(
        self, proxy_type: ZMQProxyType, context: zmq.asyncio.Context
    ) -> AsyncGenerator[tuple[BaseZMQProxy, ZMQIPCProxyConfig], None]:
        """Setup a proxy with automatic cleanup."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ZMQIPCProxyConfig(path=tmpdir, name=f"test_{proxy_type.value}")

            proxy = ZMQProxyFactory.create_instance(
                proxy_type, context=context, zmq_proxy_config=config
            )
            # Start the proxy in background
            proxy_task = asyncio.create_task(proxy.run())

            try:
                # Give proxy time to initialize
                await real_sleep(0.1)
                yield proxy, config
            finally:
                with contextlib.suppress(asyncio.CancelledError):
                    await proxy.stop()
                proxy_task.cancel()
                context.term()

                with contextlib.suppress(asyncio.CancelledError):
                    await proxy_task

    @pytest.mark.asyncio
    async def test_push_pull_proxy_forwarding(self, zmq_context, test_message):
        """Test PUSH/PULL proxy forwards messages correctly."""
        async with self._setup_proxy_with_cleanup(
            ZMQProxyType.PUSH_PULL, zmq_context
        ) as (proxy, config):
            # Create client (connects to frontend)
            push_client = ZMQPushClient(
                context=zmq_context, address=config.frontend_address, bind=False
            )

            # Create service (connects to backend)
            pull_client = ZMQPullClient(
                context=zmq_context, address=config.backend_address, bind=False
            )

            try:
                await asyncio.gather(push_client.initialize(), pull_client.initialize())

                # Allow connections to establish
                await real_sleep(0.1)

                def callback(message):
                    assert message == test_message

                await pull_client.register_pull_callback(MessageType.TEST, callback)
                await push_client.push(test_message)

            finally:
                await asyncio.gather(push_client.shutdown(), pull_client.shutdown())

    @pytest.mark.asyncio
    async def test_pub_sub_proxy_forwarding(self, zmq_context):
        """Test XPUB/XSUB proxy forwards pub/sub messages correctly."""
        async with self._setup_proxy_with_cleanup(
            ZMQProxyType.XPUB_XSUB, zmq_context
        ) as (proxy, config):
            # Create publisher (connects to frontend)
            pub_client = ZMQPubClient(
                context=zmq_context, address=config.frontend_address, bind=False
            )

            # Create subscriber (connects to backend)
            sub_client = ZMQSubClient(
                context=zmq_context, address=config.backend_address, bind=False
            )

            try:
                await asyncio.gather(pub_client.initialize(), sub_client.initialize())

                # Subscribe to topic
                messages_received = []

                async def message_handler(message: Message):
                    messages_received.append(message)

                await sub_client.subscribe(MessageType.TEST, message_handler)

                # Allow subscription to propagate
                await real_sleep(0.2)

                # Publish message
                test_message = TestMessage()
                await pub_client.publish(test_message)

                # Wait for message delivery
                await real_sleep(0.1)

                assert len(messages_received) == 1
                assert messages_received[0] == test_message

            finally:
                await asyncio.gather(pub_client.shutdown(), sub_client.shutdown())

    @pytest.mark.asyncio
    async def test_dealer_router_proxy_forwarding(self, zmq_context):
        """Test ROUTER/DEALER proxy forwards request/reply messages correctly."""
        async with self._setup_proxy_with_cleanup(
            ZMQProxyType.DEALER_ROUTER, zmq_context
        ) as (proxy, config):
            # Create dealer client (connects to frontend)
            dealer_client = ZMQDealerReqClient(
                context=zmq_context, address=config.frontend_address, bind=False
            )

            # Create router service (connects to backend)
            router_client = ZMQRouterRepClient(
                context=zmq_context, address=config.backend_address, bind=False
            )

            async def _mock_handler(message: Message):
                logger.debug("Received message: %s", message)
                return message

            try:
                await asyncio.gather(
                    dealer_client.initialize(), router_client.initialize()
                )

                router_client.register_request_handler(
                    "test-service", MessageType.CONVERSATION_REQUEST, _mock_handler
                )

                # Allow connections to establish
                await real_sleep(0.1)

                # Send request through proxy
                test_request = ConversationRequestMessage(
                    request_id="123456",
                    conversation_id="123",
                    service_id="test-service",
                )

                event = asyncio.Event()

                async def _mock_response_handler(message: Message):
                    logger.debug("Received response: %s", message)
                    assert message == test_request
                    event.set()

                await dealer_client.request_async(test_request, _mock_response_handler)
                await event.wait()

            finally:
                with contextlib.suppress(asyncio.CancelledError):
                    await asyncio.gather(
                        dealer_client.shutdown(), router_client.shutdown()
                    )
                    zmq_context.term()


class TestZMQProxyErrorHandling:
    """Test error handling in proxy operations."""

    @pytest.mark.asyncio
    async def test_proxy_run_with_socket_error(self):
        """Test proxy handles socket errors during run."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ZMQIPCProxyConfig(path=tmpdir, name="error_test")

            proxy = ZMQProxyFactory.create_instance(
                ZMQProxyType.PUSH_PULL,
                context=zmq.asyncio.Context(),
                zmq_proxy_config=config,
            )

            # Mock socket initialization to fail
            proxy.frontend_socket.initialize = AsyncMock(
                side_effect=CommunicationError(
                    CommunicationErrorReason.SOCKET_ERROR, "Socket bind failed"
                )
            )

            with pytest.raises(CommunicationError):
                await proxy.run()

    @pytest.mark.asyncio
    async def test_proxy_graceful_shutdown_on_cancellation(self):
        """Test proxy shuts down gracefully when cancelled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = ZMQIPCProxyConfig(path=tmpdir, name="cancel_test")

            proxy = ZMQProxyFactory.create_instance(
                ZMQProxyType.PUSH_PULL,
                context=zmq.asyncio.Context(),
                zmq_proxy_config=config,
            )

            # Mock successful initialization but failing proxy
            proxy._initialize = AsyncMock()

            with patch("zmq.proxy_steerable", side_effect=asyncio.CancelledError()):
                proxy_task = asyncio.create_task(proxy.run())

                # Cancel the task
                await asyncio.sleep(0.01)
                proxy_task.cancel()

                with pytest.raises(asyncio.CancelledError):
                    await proxy_task

    def test_socket_type_validation(self):
        """Test that proxy sockets have correct type constraints."""
        from aiperf.common.comms.zmq.clients.zmq_proxy_sockets import (
            ProxyBackendSocket,
            ProxyFrontendSocket,
        )

        # This is more of a type-checking test - ensures the Generic[SocketT]
        # constraints are working as expected
        frontend = ProxyFrontendSocket[zmq.PULL]
        backend = ProxyBackendSocket[zmq.PUSH]

        # These should be constructible without errors
        assert frontend is not None
        assert backend is not None
