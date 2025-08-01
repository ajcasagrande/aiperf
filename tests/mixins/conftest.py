# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Fixtures for testing mixins.

Example usage of the mock classes:

```python
import pytest
from tests.mixins.conftest import MockServiceController, MockCommunication

async def test_service_registration(mock_service_controller):
    # Register a service
    await mock_service_controller.register_service(
        service_id="test-service-1",
        service_type="worker",
        service_info={"endpoint": "test_endpoint"}
    )

    # Verify registration
    assert mock_service_controller.is_service_registered("test-service-1")
    assert mock_service_controller.get_service_count() == 1
    assert mock_service_controller.get_service_count("worker") == 1

async def test_profiling_workflow(mock_service_controller):
    # Register services
    await mock_service_controller.register_service("svc1", "worker")
    await mock_service_controller.register_service("svc2", "parser")

    # Start profiling
    await mock_service_controller.start_profiling()

    # Verify state
    assert mock_service_controller.profiling_started
    assert mock_service_controller.profiling_configured

    services = mock_service_controller.get_registered_services()
    assert all(svc["state"] == "profiling" for svc in services.values())

async def test_communication_mock(mock_communication):
    # Create clients
    pub_client = mock_communication.create_pub_client("tcp://test:5555")
    sub_client = mock_communication.create_sub_client("tcp://test:5556")

    # Test publishing
    from aiperf.common.messages import Message
    test_message = Message(message_type="TEST", service_id="test")
    await pub_client.publish(test_message)

    # Verify message was stored
    assert len(pub_client.published_messages) == 1
    assert pub_client.published_messages[0].message_type == "TEST"

async def test_integration_environment(mock_test_environment):
    env = mock_test_environment
    controller = env["controller"]
    communication = env["communication"]
    test_service = env["test_service"]

    # Service should be auto-registered
    assert controller.is_service_registered(test_service.service_id)

    # Test profiling workflow
    await controller.start_profiling()
    assert controller.profiling_started
```
"""

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Any, cast
from unittest.mock import MagicMock

import pytest

from aiperf.common.base_service import BaseService
from aiperf.common.config.endpoint_config import EndpointConfig
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.constants import DEFAULT_COMMS_REQUEST_TIMEOUT
from aiperf.common.enums.communication_enums import CommClientType
from aiperf.common.enums.message_enums import MessageType
from aiperf.common.factories import ServiceFactory
from aiperf.common.messages import Message
from aiperf.common.messages.command_messages import (
    CommandMessage,
    ConnectionProbeMessage,
)
from aiperf.common.mixins.aiperf_lifecycle_mixin import AIPerfLifecycleMixin
from aiperf.common.protocols import (
    CommunicationClientProtocol,
    PubClientProtocol,
    PullClientProtocol,
    PushClientProtocol,
    ReplyClientProtocol,
    RequestClientProtocol,
    SubClientProtocol,
)
from aiperf.common.types import (
    CommAddressType,
    MessageCallbackMapT,
    MessageTypeT,
)


class MockServiceController(AIPerfLifecycleMixin):
    """Mock service controller for testing service registration and profiling."""

    def __init__(self) -> None:
        # Set id before calling super().__init__ as it's required by AIPerfLifecycleMixin
        self.id = f"MockServiceController_{id(self)}"
        super().__init__()
        self.registered_services: dict[str, dict[str, Any]] = {}
        self.service_map: dict[str, list[dict[str, Any]]] = {}
        self.profiling_started = False
        self.profiling_configured = False
        self.registration_callbacks: list[
            Callable[[dict[str, Any]], Coroutine[Any, Any, None]]
        ] = []
        self.profiling_callbacks: list[Callable[[], Coroutine[Any, Any, None]]] = []

    async def register_service(
        self,
        service_id: str,
        service_type: str,
        service_info: dict[str, Any] | None = None,
    ) -> None:
        """Register a service with the controller."""
        info = service_info or {}
        service_data = {
            "service_id": service_id,
            "service_type": service_type,
            "registration_time": asyncio.get_event_loop().time(),
            "state": "registered",
            **info,
        }

        self.registered_services[service_id] = service_data

        if service_type not in self.service_map:
            self.service_map[service_type] = []
        self.service_map[service_type].append(service_data)

        # Notify registration callbacks
        for callback in self.registration_callbacks:
            await callback(service_data)

    async def unregister_service(self, service_id: str) -> bool:
        """Unregister a service from the controller."""
        if service_id not in self.registered_services:
            return False

        service_data = self.registered_services.pop(service_id)
        service_type = service_data["service_type"]

        if service_type in self.service_map:
            self.service_map[service_type] = [
                s
                for s in self.service_map[service_type]
                if s["service_id"] != service_id
            ]
            if not self.service_map[service_type]:
                del self.service_map[service_type]

        return True

    async def configure_profiling(self) -> None:
        """Configure profiling for all registered services."""
        if not self.registered_services:
            raise ValueError("No services registered")

        self.profiling_configured = True

        # Update all registered services to configured state
        for service_data in self.registered_services.values():
            service_data["state"] = "configured"

    async def start_profiling(self) -> None:
        """Start profiling for all registered services."""
        if not self.profiling_configured:
            await self.configure_profiling()

        self.profiling_started = True

        # Update all registered services to profiling state
        for service_data in self.registered_services.values():
            service_data["state"] = "profiling"

        # Notify profiling callbacks
        for callback in self.profiling_callbacks:
            await callback()

    async def stop_profiling(self) -> None:
        """Stop profiling for all registered services."""
        self.profiling_started = False
        self.profiling_configured = False

        # Update all registered services to stopped state
        for service_data in self.registered_services.values():
            service_data["state"] = "stopped"

    def get_registered_services(self) -> dict[str, dict[str, Any]]:
        """Get all registered services."""
        return self.registered_services.copy()

    def get_services_by_type(self, service_type: str) -> list[dict[str, Any]]:
        """Get all services of a specific type."""
        return self.service_map.get(service_type, []).copy()

    def is_service_registered(self, service_id: str) -> bool:
        """Check if a service is registered."""
        return service_id in self.registered_services

    def get_service_count(self, service_type: str | None = None) -> int:
        """Get count of registered services, optionally filtered by type."""
        if service_type is None:
            return len(self.registered_services)
        return len(self.service_map.get(service_type, []))

    def add_registration_callback(
        self, callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]]
    ) -> None:
        """Add a callback to be called when a service registers."""
        self.registration_callbacks.append(callback)

    def add_profiling_callback(
        self, callback: Callable[[], Coroutine[Any, Any, None]]
    ) -> None:
        """Add a callback to be called when profiling starts."""
        self.profiling_callbacks.append(callback)

    def clear(self) -> None:
        """Clear all services and reset state."""
        self.registered_services.clear()
        self.service_map.clear()
        self.profiling_started = False
        self.profiling_configured = False
        self.registration_callbacks.clear()
        self.profiling_callbacks.clear()


class MockCommunicationClient(AIPerfLifecycleMixin):
    """Base mock communication client."""

    def __init__(
        self, address: str, bind: bool, socket_ops: dict | None = None, **kwargs
    ) -> None:
        # Set id before calling super().__init__ as it's required by AIPerfLifecycleMixin
        self.id = f"MockCommunicationClient_{id(self)}"
        self.address = address
        self.bind = bind
        self.socket_ops = socket_ops or {}
        super().__init__(**kwargs)


class MockPubClient(MockCommunicationClient):
    """Mock PUB client."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.published_messages: list[Message] = []

    async def publish(self, message: Message) -> None:
        self.published_messages.append(message)


class MockSubClient(MockCommunicationClient):
    """Mock SUB client."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.subscriptions: dict[
            MessageTypeT, list[Callable[[Message], Coroutine[Any, Any, None]]]
        ] = {}

    async def subscribe(
        self,
        message_type: MessageTypeT,
        callback: Callable[[Message], Coroutine[Any, Any, None]],
    ) -> None:
        if message_type not in self.subscriptions:
            self.subscriptions[message_type] = []
        self.subscriptions[message_type].append(callback)

    async def subscribe_all(self, message_callback_map: MessageCallbackMapT) -> None:
        for message_type, callback in message_callback_map.items():
            if isinstance(callback, list):
                for cb in callback:
                    await self.subscribe(message_type, cb)
            else:
                await self.subscribe(message_type, callback)


class MockPushClient(MockCommunicationClient):
    """Mock PUSH client."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.pushed_messages: list[Message] = []

    async def push(self, message: Message) -> None:
        self.pushed_messages.append(message)


class MockPullClient(MockCommunicationClient):
    """Mock PULL client."""

    def __init__(
        self, *args, max_pull_concurrency: int | None = None, **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self.max_pull_concurrency = max_pull_concurrency
        self.pull_callbacks: dict[
            MessageTypeT, list[Callable[[Message], Coroutine[Any, Any, None]]]
        ] = {}

    def register_pull_callback(
        self,
        message_type: MessageTypeT,
        callback: Callable[[Message], Coroutine[Any, Any, None]],
    ) -> None:
        if message_type not in self.pull_callbacks:
            self.pull_callbacks[message_type] = []
        self.pull_callbacks[message_type].append(callback)


class MockRequestClient(MockCommunicationClient):
    """Mock REQUEST client."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.requests: list[Message] = []
        self.mock_responses: dict[str, dict[str, Any]] = {}

    async def request(
        self,
        message: Message,
        timeout: float = DEFAULT_COMMS_REQUEST_TIMEOUT,
    ) -> dict[str, Any]:
        self.requests.append(message)
        return self.mock_responses.get(str(message.message_type), {})

    async def request_async(
        self,
        message: Message,
        callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        self.requests.append(message)
        response = self.mock_responses.get(str(message.message_type), {})
        await callback(response)


class MockReplyClient(MockCommunicationClient):
    """Mock REPLY client."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.request_handlers: dict[
            str,
            dict[
                MessageTypeT,
                Callable[[Message], Coroutine[Any, Any, dict[str, Any] | None]],
            ],
        ] = {}

    def register_request_handler(
        self,
        service_id: str,
        message_type: MessageTypeT,
        handler: Callable[[Message], Coroutine[Any, Any, dict[str, Any] | None]],
    ) -> None:
        if service_id not in self.request_handlers:
            self.request_handlers[service_id] = {}
        self.request_handlers[service_id][message_type] = handler


class MockCommunication(AIPerfLifecycleMixin):
    """Mock communication implementation that supports all protocols."""

    def __init__(self) -> None:
        # Set id for logging compatibility
        self.id = f"MockCommunication_{id(self)}"
        super().__init__()
        self.clients: list[MockCommunicationClient] = []
        self.addresses: dict[CommAddressType, str] = {}

    async def stop(self) -> None:
        await super().stop()
        for client in self.clients:
            await client.stop()

    # Communication Protocol Methods
    def get_address(self, address_type: CommAddressType) -> str:
        if isinstance(address_type, str):
            return address_type
        return self.addresses.get(address_type, f"mock://{address_type}")

    def create_client(
        self,
        client_type: CommClientType,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
        max_pull_concurrency: int | None = None,
    ) -> CommunicationClientProtocol:
        address_str = self.get_address(address)

        if client_type == CommClientType.PUB:
            client = MockPubClient(address_str, bind, socket_ops)
        elif client_type == CommClientType.SUB:
            client = MockSubClient(address_str, bind, socket_ops)
        elif client_type == CommClientType.PUSH:
            client = MockPushClient(address_str, bind, socket_ops)
        elif client_type == CommClientType.PULL:
            client = MockPullClient(
                address_str, bind, socket_ops, max_pull_concurrency=max_pull_concurrency
            )
        elif client_type == CommClientType.REQUEST:
            client = MockRequestClient(address_str, bind, socket_ops)
        elif client_type == CommClientType.REPLY:
            client = MockReplyClient(address_str, bind, socket_ops)
        else:
            client = MockCommunicationClient(address_str, bind, socket_ops)

        self.clients.append(client)
        return client

    def create_pub_client(
        self,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> PubClientProtocol:
        return cast(
            PubClientProtocol,
            self.create_client(CommClientType.PUB, address, bind, socket_ops),
        )

    def create_sub_client(
        self,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> SubClientProtocol:
        return cast(
            SubClientProtocol,
            self.create_client(CommClientType.SUB, address, bind, socket_ops),
        )

    def create_push_client(
        self,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> PushClientProtocol:
        return cast(
            PushClientProtocol,
            self.create_client(CommClientType.PUSH, address, bind, socket_ops),
        )

    def create_pull_client(
        self,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
        max_pull_concurrency: int | None = None,
    ) -> PullClientProtocol:
        return cast(
            PullClientProtocol,
            self.create_client(
                CommClientType.PULL, address, bind, socket_ops, max_pull_concurrency
            ),
        )

    def create_request_client(
        self,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> RequestClientProtocol:
        return cast(
            RequestClientProtocol,
            self.create_client(CommClientType.REQUEST, address, bind, socket_ops),
        )

    def create_reply_client(
        self,
        address: CommAddressType,
        bind: bool = False,
        socket_ops: dict | None = None,
    ) -> ReplyClientProtocol:
        return cast(
            ReplyClientProtocol,
            self.create_client(CommClientType.REPLY, address, bind, socket_ops),
        )

    def clear(self) -> None:
        """Clear all stored data and reset state."""
        self.clients.clear()
        self.addresses.clear()


@ServiceFactory.register("test_service_type")
class BaseTestService(BaseService):
    """
    Base class for testing services.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.comms = MockCommunication()

    async def publish(self, message: Message) -> None:
        if message.message_type == MessageType.CONNECTION_PROBE:
            await self._process_connection_probe_message(
                cast(ConnectionProbeMessage, message)
            )
        elif message.message_type == MessageType.COMMAND:
            await self._process_command_message(cast(CommandMessage, message))
        else:
            await super().publish(message)


@pytest.fixture
def service_class() -> type[BaseService]:
    """
    Return the service class to test.
    """
    return BaseService


@pytest.fixture
async def test_service() -> AsyncGenerator[BaseTestService, None]:
    """
    Return a service instance.
    """

    service = cast(
        BaseTestService,
        ServiceFactory.create_instance(
            "test_service_type",
            service_config=ServiceConfig(),
            user_config=UserConfig(
                endpoint=EndpointConfig(
                    model_names=["test_model_name"],
                ),
            ),
        ),
    )
    try:
        await service.initialize()
        await service.start()
        yield service
    finally:
        await service.stop()


@pytest.fixture
async def initialized_service(
    test_service: BaseTestService,
) -> AsyncGenerator[BaseTestService, None]:
    """
    Return an initialized service instance.
    """
    await test_service.initialize()
    yield test_service


@pytest.fixture
async def started_service(
    initialized_service: BaseTestService,
) -> AsyncGenerator[BaseTestService, None]:
    """
    Return a started service instance.
    """
    await initialized_service.start()
    yield initialized_service


@pytest.fixture
def mock_communication() -> MockCommunication:
    """
    Return a fresh MockCommunication instance for testing.
    """
    return MockCommunication()


@pytest.fixture
def mock_pub_client() -> MockPubClient:
    """
    Return a fresh MockPubClient instance for testing.
    """
    return MockPubClient("mock://test", False)


@pytest.fixture
def mock_sub_client() -> MockSubClient:
    """
    Return a fresh MockSubClient instance for testing.
    """
    return MockSubClient("mock://test", False)


@pytest.fixture
def mock_push_client() -> MockPushClient:
    """
    Return a fresh MockPushClient instance for testing.
    """
    return MockPushClient("mock://test", False)


@pytest.fixture
def mock_pull_client() -> MockPullClient:
    """
    Return a fresh MockPullClient instance for testing.
    """
    return MockPullClient("mock://test", False)


@pytest.fixture
def mock_request_client() -> MockRequestClient:
    """
    Return a fresh MockRequestClient instance for testing.
    """
    return MockRequestClient("mock://test", False)


@pytest.fixture
def mock_reply_client() -> MockReplyClient:
    """
    Return a fresh MockReplyClient instance for testing.
    """
    return MockReplyClient("mock://test", False)


@pytest.fixture
def mock_service_controller() -> MockServiceController:
    """
    Return a fresh MockServiceController instance for testing.
    """
    return MockServiceController()


class MockMessageBusClient(MockCommunicationClient):
    """Mock message bus client that combines pub/sub functionality."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.comms = MockCommunication()
        self.sub_client = MockSubClient(*args, **kwargs)
        self.pub_client = MockPubClient(*args, **kwargs)
        self.published_messages: list[Message] = []
        self.subscriptions: dict[
            MessageTypeT, list[Callable[[Message], Coroutine[Any, Any, None]]]
        ] = {}
        # Add required id attribute
        self.id = f"MockMessageBusClient_{id(self)}"

    async def publish(self, message: Message) -> None:
        """Publish a message to the message bus."""
        self.published_messages.append(message)
        await self.pub_client.publish(message)

    async def subscribe(
        self,
        message_type: MessageTypeT,
        callback: Callable[[Message], Coroutine[Any, Any, None]],
    ) -> None:
        """Subscribe to a message type."""
        if message_type not in self.subscriptions:
            self.subscriptions[message_type] = []
        self.subscriptions[message_type].append(callback)
        await self.sub_client.subscribe(message_type, callback)

    async def subscribe_all(self, message_callback_map: MessageCallbackMapT) -> None:
        """Subscribe to multiple message types."""
        for message_type, callback in message_callback_map.items():
            if isinstance(callback, list):
                for cb in callback:
                    await self.subscribe(message_type, cb)
            else:
                await self.subscribe(message_type, callback)

    async def simulate_message(self, message: Message) -> None:
        """Simulate receiving a message and call appropriate callbacks."""
        if message.message_type in self.subscriptions:
            for callback in self.subscriptions[message.message_type]:
                await callback(message)

    def get_published_messages(
        self, message_type: MessageTypeT | None = None
    ) -> list[Message]:
        """Get published messages, optionally filtered by type."""
        if message_type is None:
            return self.published_messages.copy()
        return [
            msg for msg in self.published_messages if msg.message_type == message_type
        ]

    def clear_messages(self) -> None:
        """Clear all stored messages."""
        self.published_messages.clear()
        self.pub_client.published_messages.clear()


@pytest.fixture
def mock_message_bus_client() -> MockMessageBusClient:
    """
    Return a fresh MockMessageBusClient instance for testing.
    """
    return MockMessageBusClient("mock://test", False)


@pytest.fixture
def patch_communication_factory():
    """
    Patch the CommunicationFactory to return MockCommunication instead of real ZMQ communication.
    This prevents any real network connections during testing.
    """
    from unittest.mock import patch

    from aiperf.common.factories import CommunicationFactory

    # Create a mock communication instance that will be reused
    mock_comm = MockCommunication()

    def mock_get_or_create_instance(*args, **kwargs):
        """Mock factory method that returns our MockCommunication."""
        return mock_comm

    def mock_create_instance(*args, **kwargs):
        """Mock factory method that returns our MockCommunication."""
        return mock_comm

    with (
        patch.object(
            CommunicationFactory,
            "get_or_create_instance",
            side_effect=mock_get_or_create_instance,
        ),
        patch.object(
            CommunicationFactory, "create_instance", side_effect=mock_create_instance
        ),
    ):
        yield mock_comm


@pytest.fixture
def patch_all_communication():
    """
    Comprehensive patch that prevents all real communication during testing.
    Patches both factory methods and any direct imports.
    """
    from unittest.mock import patch

    from aiperf.common.factories import CommunicationFactory

    # Create a mock communication instance
    mock_comm = MockCommunication()

    patches = [
        # Patch the factory methods
        patch.object(
            CommunicationFactory, "get_or_create_instance", return_value=mock_comm
        ),
        patch.object(CommunicationFactory, "create_instance", return_value=mock_comm),
        # Patch ZMQ context creation to prevent real sockets
        patch("zmq.Context", return_value=MagicMock()),
        patch("zmq.asyncio.Context", return_value=MagicMock()),
        # Patch any direct ZMQ imports
        patch("aiperf.comms.zmq_comms.zmq.Context", return_value=MagicMock()),
        patch("aiperf.comms.zmq_comms.zmq.asyncio.Context", return_value=MagicMock()),
    ]

    # Start all patches
    for p in patches:
        p.start()

    try:
        yield mock_comm
    finally:
        # Stop all patches
        for p in patches:
            p.stop()


@pytest.fixture
async def mock_test_environment() -> AsyncGenerator[dict[str, Any], None]:
    """
    Return a comprehensive mock test environment with all components initialized.

    This fixture provides:
    - Mock communication layer (no real ZMQ connections)
    - Mock service controller
    - Mock message bus client
    - Pre-configured test service

    Perfect for integration testing scenarios.
    """
    from unittest.mock import patch

    from aiperf.common.factories import CommunicationFactory

    # Create all mock components
    mock_comms = MockCommunication()
    mock_controller = MockServiceController()
    mock_bus = MockMessageBusClient("mock://test", False)

    # Patch the CommunicationFactory to return our mock
    def mock_get_or_create_instance(*args, **kwargs):
        return mock_comms

    def mock_create_instance(*args, **kwargs):
        return mock_comms

    with (
        patch.object(
            CommunicationFactory,
            "get_or_create_instance",
            side_effect=mock_get_or_create_instance,
        ),
        patch.object(
            CommunicationFactory, "create_instance", side_effect=mock_create_instance
        ),
        patch("zmq.Context"),
        patch("zmq.asyncio.Context"),
    ):
        # Initialize all components
        await mock_comms.initialize_and_start()
        await mock_controller.initialize_and_start()
        await mock_bus.initialize_and_start()

        # Create a test service - now it will use our mock communication
        test_service = cast(
            BaseTestService,
            ServiceFactory.create_instance(
                "test_service_type",
                service_config=ServiceConfig(),
                user_config=UserConfig(
                    endpoint=EndpointConfig(
                        model_names=["test_model_name"],
                    ),
                ),
            ),
        )

        await test_service.initialize_and_start()

        # Register the test service with the controller
        await mock_controller.register_service(
            service_id=test_service.service_id,
            service_type="test_service_type",
            service_info={"endpoint": "test_endpoint"},
        )

        environment = {
            "communication": mock_comms,
            "controller": mock_controller,
            "message_bus": mock_bus,
            "test_service": test_service,
            "service_id": test_service.service_id,
        }

        try:
            yield environment
        finally:
            # Cleanup all components
            await test_service.stop()
            await mock_bus.stop()
            await mock_controller.stop()
            await mock_comms.stop()

            # Clear all state
            mock_comms.clear()
            mock_controller.clear()
            mock_bus.clear_messages()


@pytest.fixture
async def no_real_connections_test_service(
    patch_all_communication,
) -> AsyncGenerator[BaseTestService, None]:
    """
    Create a test service with guaranteed no real network connections.
    Uses comprehensive patching to prevent any ZMQ sockets from being created.
    """
    mock_comm = patch_all_communication

    # Create test service - will use mocked communication
    service = cast(
        BaseTestService,
        ServiceFactory.create_instance(
            "test_service_type",
            service_config=ServiceConfig(),
            user_config=UserConfig(
                endpoint=EndpointConfig(
                    model_names=["test_model_name"],
                ),
            ),
        ),
    )

    try:
        await service.initialize_and_start()
        yield service
    finally:
        await service.stop()
