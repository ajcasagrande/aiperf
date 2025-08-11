# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Common fixtures for tests.
"""

from unittest.mock import Mock

import pytest

from aiperf.common.config import EndpointConfig, ServiceConfig, UserConfig
from aiperf.common.enums import CommAddress, CommunicationBackend, ServiceRunType
from aiperf.common.mixins import (
    AIPerfLifecycleMixin,
    AIPerfLoggerMixin,
    BaseMixin,
    CommandHandlerMixin,
    CommunicationMixin,
    HooksMixin,
    MessageBusClientMixin,
    ProcessHealthMixin,
    PullClientMixin,
    ReplyClientMixin,
    TaskManagerMixin,
)


@pytest.fixture
def mock_service_config() -> ServiceConfig:
    """Create a mock ServiceConfig for testing."""
    return ServiceConfig(
        service_run_type=ServiceRunType.MULTIPROCESSING,
        comm_backend=CommunicationBackend.ZMQ_IPC,
    )


@pytest.fixture
def mock_user_config() -> UserConfig:
    """Create a mock UserConfig for testing."""
    return UserConfig(endpoint=EndpointConfig(model_names=["test-model"]))


@pytest.fixture
def mock_service_id() -> str:
    """Create a mock service ID for testing."""
    return "test_service_123"


@pytest.fixture
def mock_comm_address() -> CommAddress:
    """Create a mock communication address for testing."""
    return CommAddress.EVENT_BUS_PROXY_FRONTEND


@pytest.fixture
def mock_communication_factory(monkeypatch):
    """Mock the CommunicationFactory to avoid actual communication setup."""
    mock_comms = Mock()
    mock_comms.attach_child_lifecycle = Mock()
    mock_comms.create_sub_client = Mock(return_value=Mock())
    mock_comms.create_pub_client = Mock(return_value=Mock())
    mock_comms.create_pull_client = Mock(return_value=Mock())
    mock_comms.create_reply_client = Mock(return_value=Mock())

    mock_factory = Mock()
    mock_factory.get_or_create_instance.return_value = mock_comms
    monkeypatch.setattr("aiperf.common.factories.CommunicationFactory", mock_factory)

    return mock_comms


# Base mixin fixtures
@pytest.fixture
def base_mixin() -> BaseMixin:
    """Create a BaseMixin instance for testing."""
    return BaseMixin()


@pytest.fixture
def aiperf_logger_mixin() -> AIPerfLoggerMixin:
    """Create an AIPerfLoggerMixin instance for testing."""
    return AIPerfLoggerMixin(logger_name="test_logger")


@pytest.fixture
def process_health_mixin() -> ProcessHealthMixin:
    """Create a ProcessHealthMixin instance for testing."""
    return ProcessHealthMixin()


@pytest.fixture
def task_manager_mixin() -> TaskManagerMixin:
    """Create a TaskManagerMixin instance for testing."""
    return TaskManagerMixin()


@pytest.fixture
def hooks_mixin() -> HooksMixin:
    """Create a HooksMixin instance for testing."""
    return HooksMixin()


# Communication and lifecycle mixins
@pytest.fixture
def communication_mixin(
    mock_service_config: ServiceConfig, mock_communication_factory
) -> CommunicationMixin:
    """Create a CommunicationMixin instance for testing."""
    return CommunicationMixin(service_config=mock_service_config)


@pytest.fixture
def aiperf_lifecycle_mixin() -> AIPerfLifecycleMixin:
    """Create an AIPerfLifecycleMixin instance for testing."""
    return AIPerfLifecycleMixin(id="test_lifecycle")


@pytest.fixture
def message_bus_mixin(
    mock_service_config: ServiceConfig, mock_communication_factory
) -> MessageBusClientMixin:
    """Create a MessageBusClientMixin instance for testing."""
    return MessageBusClientMixin(service_config=mock_service_config)


@pytest.fixture
def pull_client_mixin(
    mock_service_config: ServiceConfig,
    mock_comm_address: CommAddress,
    mock_communication_factory,
) -> PullClientMixin:
    """Create a PullClientMixin instance for testing."""
    return PullClientMixin(
        service_config=mock_service_config,
        pull_client_address=mock_comm_address,
    )


@pytest.fixture
def reply_client_mixin(
    mock_service_config: ServiceConfig,
    mock_comm_address: CommAddress,
    mock_communication_factory,
) -> ReplyClientMixin:
    """Create a ReplyClientMixin instance for testing."""
    return ReplyClientMixin(
        service_config=mock_service_config,
        reply_client_address=mock_comm_address,
    )


@pytest.fixture
def command_handler_mixin(
    mock_service_config: ServiceConfig,
    mock_user_config: UserConfig,
    mock_service_id: str,
    mock_communication_factory,
) -> CommandHandlerMixin:
    """Create a CommandHandlerMixin instance for testing."""
    return CommandHandlerMixin(
        service_config=mock_service_config,
        user_config=mock_user_config,
        service_id=mock_service_id,
    )


# Base test service classes
class BaseTestService:
    """Base test class that provides common service testing functionality.

    This class provides:
    - Pre-configured fixtures for service components
    - Common setup and teardown patterns
    - Helper methods for testing service behavior
    - Standardized mock configurations

    Usage:
        class TestMyService(BaseTestService):
            def test_my_functionality(self, base_test_service):
                service = base_test_service
                # Test your service functionality
    """

    @pytest.fixture
    def base_test_service(
        self,
        mock_service_config: ServiceConfig,
        mock_user_config: UserConfig,
        mock_service_id: str,
        mock_communication_factory,
    ):
        """Create a base test service with all dependencies mocked."""
        from aiperf.common.base_service import BaseService
        from aiperf.common.enums import ServiceType

        class TestableBaseService(BaseService):
            service_type = ServiceType.WORKER  # Default service type

            def handle_command(self, command):
                """Default command handler for testing."""
                pass

        service = TestableBaseService(
            service_config=mock_service_config,
            user_config=mock_user_config,
            service_id=mock_service_id,
        )

        # Mock any additional communication clients that services typically need
        service._mock_communication_factory = mock_communication_factory

        return service

    def assert_service_initialized(self, service):
        """Assert that a service is properly initialized."""
        assert service.service_config is not None
        assert service.user_config is not None
        assert service.service_id is not None
        assert hasattr(service, "service_type")

    def assert_communication_setup(self, service):
        """Assert that communication components are properly set up."""
        assert hasattr(service, "comms")


# Additional service fixtures for mixin combinations
@pytest.fixture
def test_service_with_pull_client(
    mock_service_config: ServiceConfig,
    mock_user_config: UserConfig,
    mock_service_id: str,
    mock_comm_address: CommAddress,
    mock_communication_factory,
):
    """Create a test service that includes PullClientMixin."""
    from aiperf.common.base_service import BaseService
    from aiperf.common.enums import ServiceType
    from aiperf.common.mixins import PullClientMixin

    class TestServiceWithPullClient(PullClientMixin, BaseService):
        service_type = ServiceType.WORKER

        def handle_command(self, command):
            pass

    return TestServiceWithPullClient(
        service_config=mock_service_config,
        user_config=mock_user_config,
        service_id=mock_service_id,
        pull_client_address=mock_comm_address,
    )


@pytest.fixture
def test_service_with_reply_client(
    mock_service_config: ServiceConfig,
    mock_user_config: UserConfig,
    mock_service_id: str,
    mock_comm_address: CommAddress,
    mock_communication_factory,
):
    """Create a test service that includes ReplyClientMixin."""
    from aiperf.common.base_service import BaseService
    from aiperf.common.enums import ServiceType
    from aiperf.common.mixins import ReplyClientMixin

    class TestServiceWithReplyClient(ReplyClientMixin, BaseService):
        service_type = ServiceType.WORKER

        def handle_command(self, command):
            pass

    return TestServiceWithReplyClient(
        service_config=mock_service_config,
        user_config=mock_user_config,
        service_id=mock_service_id,
        reply_client_address=mock_comm_address,
    )


@pytest.fixture
def test_service_with_process_health(
    mock_service_config: ServiceConfig,
    mock_user_config: UserConfig,
    mock_service_id: str,
    mock_communication_factory,
):
    """Create a test service that includes ProcessHealthMixin."""
    from aiperf.common.base_service import BaseService
    from aiperf.common.enums import ServiceType
    from aiperf.common.mixins import ProcessHealthMixin

    class TestServiceWithProcessHealth(ProcessHealthMixin, BaseService):
        service_type = ServiceType.WORKER

        def handle_command(self, command):
            pass

    return TestServiceWithProcessHealth(
        service_config=mock_service_config,
        user_config=mock_user_config,
        service_id=mock_service_id,
    )


class BaseTestServiceWithMixins(BaseTestService):
    """Extended base test class for services that use specific mixins.

    This provides fixtures for services that combine multiple mixins like:
    - PullClientMixin
    - ReplyClientMixin
    - ProcessHealthMixin
    - etc.
    """

    def assert_pull_client_setup(self, service):
        """Assert that pull client is properly configured."""
        assert hasattr(service, "pull_client")
        assert service.pull_client is not None

    def assert_reply_client_setup(self, service):
        """Assert that reply client is properly configured."""
        assert hasattr(service, "reply_client")
        assert service.reply_client is not None

    def assert_process_health_setup(self, service):
        """Assert that process health monitoring is set up."""
        assert hasattr(service, "get_process_health")
