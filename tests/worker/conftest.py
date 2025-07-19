# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Shared fixtures for worker service tests.

This file contains worker-specific fixtures that are automatically discovered by pytest
and made available to test functions in the worker test directory.
"""

import time
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aiperf.clients.client_interfaces import (
    InferenceClientProtocol,
    RequestConverterProtocol,
)
from aiperf.clients.model_endpoint_info import (
    EndpointInfo,
    ModelEndpointInfo,
    ModelInfo,
    ModelListInfo,
)
from aiperf.common.comms.base_comms import BaseCommunication
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.enums import (
    CommunicationBackend,
    CommunicationClientAddressType,
    EndpointType,
    ModelSelectionStrategy,
    ServiceRunType,
    ServiceType,
)
from aiperf.common.messages import (
    CommandMessage,
    ConversationResponseMessage,
    CreditDropMessage,
)
from aiperf.common.models import Conversation, RequestRecord, Turn
from aiperf.services.workers.worker import Worker


@pytest.fixture
def worker_service_config() -> ServiceConfig:
    """Create a service configuration for worker testing."""
    return ServiceConfig(
        service_run_type=ServiceRunType.MULTIPROCESSING,
        comm_backend=CommunicationBackend.ZMQ_TCP,
    )


@pytest.fixture
def worker_user_config() -> UserConfig:
    """Create a user configuration for worker testing."""
    return UserConfig(
        endpoint_type=EndpointType.OPENAI_CHAT_COMPLETIONS,
        model_names=["test-model"],
        model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
    )


@pytest.fixture
def mock_inference_client() -> AsyncMock:
    """Create a mock inference client."""
    mock_client = AsyncMock(spec=InferenceClientProtocol)
    mock_client.send_request.return_value = RequestRecord(
        timestamp_ns=time.time_ns(),
        start_perf_ns=time.perf_counter_ns(),
        end_perf_ns=time.perf_counter_ns(),
    )
    mock_client.close.return_value = None
    return mock_client


@pytest.fixture
def mock_request_converter() -> AsyncMock:
    """Create a mock request converter."""
    mock_converter = AsyncMock(spec=RequestConverterProtocol)
    mock_converter.format_payload.return_value = {
        "messages": [{"role": "user", "content": "test"}]
    }
    return mock_converter


@pytest.fixture
def mock_model_endpoint() -> ModelEndpointInfo:
    """Create a mock model endpoint info."""
    return ModelEndpointInfo(
        endpoint=EndpointInfo(
            type=EndpointType.OPENAI_CHAT_COMPLETIONS,
            base_url="http://test-server:8000",
            api_key="test-key",
        ),
        models=ModelListInfo(
            models=[ModelInfo(name="test-model")],
            model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
        ),
    )


@pytest.fixture
def mock_communication_clients() -> dict[str, AsyncMock]:
    """Create mock communication clients for worker testing."""
    clients = {}

    # Mock pull client for credit drops
    clients["credit_drop"] = AsyncMock()
    clients["credit_drop"].register_pull_callback.return_value = None

    # Mock push client for credit returns
    clients["credit_return"] = AsyncMock()
    clients["credit_return"].push.return_value = None

    # Mock push client for inference results
    clients["inference_results"] = AsyncMock()
    clients["inference_results"].push.return_value = None

    # Mock request client for conversation data
    clients["conversation_data"] = AsyncMock()
    clients["conversation_data"].request.return_value = ConversationResponseMessage(
        service_id="test-service",
        conversation=Conversation(
            turns=[Turn(messages=[{"role": "user", "content": "Test message"}])]
        ),
    )

    # Mock pub client for health messages
    clients["pub"] = AsyncMock()
    clients["pub"].publish.return_value = None

    return clients


@pytest.fixture
def mock_communication(mock_communication_clients: dict[str, AsyncMock]) -> AsyncMock:
    """Create a mock communication object for worker testing."""
    mock_comm = AsyncMock(spec=BaseCommunication)
    mock_comm.initialize.return_value = None
    mock_comm.shutdown.return_value = None

    # Set up client creation methods
    mock_comm.create_pull_client.return_value = mock_communication_clients[
        "credit_drop"
    ]
    mock_comm.create_push_client.side_effect = lambda addr_type: {
        CommunicationClientAddressType.CREDIT_RETURN: mock_communication_clients[
            "credit_return"
        ],
        CommunicationClientAddressType.RAW_INFERENCE_PROXY_FRONTEND: mock_communication_clients[
            "inference_results"
        ],
    }.get(addr_type, AsyncMock())

    mock_comm.create_request_client.return_value = mock_communication_clients[
        "conversation_data"
    ]
    mock_comm.create_pub_client.return_value = mock_communication_clients["pub"]

    return mock_comm


@pytest.fixture
def sample_credit_drop_message() -> CreditDropMessage:
    """Create a sample credit drop message for testing."""
    return CreditDropMessage(
        service_id="test-service",
        conversation_id="test-conversation-123",
        credit_drop_ns=time.time_ns(),
        warmup=False,
    )


@pytest.fixture
def sample_warmup_credit_drop_message() -> CreditDropMessage:
    """Create a sample warmup credit drop message for testing."""
    return CreditDropMessage(
        service_id="test-service",
        conversation_id="test-conversation-warmup",
        credit_drop_ns=time.time_ns(),
        warmup=True,
    )


@pytest.fixture
def sample_conversation_response() -> ConversationResponseMessage:
    """Create a sample conversation response message for testing."""
    return ConversationResponseMessage(
        service_id="test-service",
        conversation=Conversation(
            turns=[Turn(messages=[{"role": "user", "content": "Test prompt"}])]
        ),
    )


@pytest.fixture
def sample_turn() -> Turn:
    """Create a sample turn for testing."""
    return Turn(messages=[{"role": "user", "content": "Test message"}])


@pytest.fixture
def sample_request_record() -> RequestRecord:
    """Create a sample request record for testing."""
    return RequestRecord(
        timestamp_ns=time.time_ns(),
        start_perf_ns=time.perf_counter_ns(),
        end_perf_ns=time.perf_counter_ns(),
    )


@pytest.fixture
def sample_failed_request_record() -> RequestRecord:
    """Create a sample failed request record for testing."""
    from aiperf.common.models import ErrorDetails

    return RequestRecord(
        timestamp_ns=time.time_ns(),
        start_perf_ns=time.perf_counter_ns(),
        end_perf_ns=time.perf_counter_ns(),
        error=ErrorDetails(
            error_type="TestError",
            message="Test error message",
            traceback="Test traceback",
        ),
    )


@pytest.fixture
def patch_worker_dependencies() -> Generator[None, None, None]:
    """Patch worker dependencies for testing."""
    _ = [
        patch("aiperf.services.worker.worker.CommunicationFactory.create_instance"),
        patch("aiperf.services.worker.worker.InferenceClientFactory.create_instance"),
        patch("aiperf.services.worker.worker.RequestConverterFactory.create_instance"),
        patch("aiperf.services.worker.worker.ModelEndpointInfo.from_user_config"),
    ]

    with patch.multiple(
        "aiperf.services.worker.worker",
        CommunicationFactory=MagicMock(),
        InferenceClientFactory=MagicMock(),
        RequestConverterFactory=MagicMock(),
        ModelEndpointInfo=MagicMock(),
    ):
        yield


@pytest.fixture
async def worker_instance(
    worker_service_config: ServiceConfig,
    worker_user_config: UserConfig,
    mock_communication: AsyncMock,
    mock_inference_client: AsyncMock,
    mock_request_converter: AsyncMock,
    mock_model_endpoint: ModelEndpointInfo,
) -> AsyncGenerator[Worker, None]:
    """Create a worker instance for testing with all dependencies mocked."""
    with patch.multiple(
        "aiperf.services.worker.worker",
        CommunicationFactory=MagicMock(return_value=mock_communication),
        InferenceClientFactory=MagicMock(return_value=mock_inference_client),
        RequestConverterFactory=MagicMock(return_value=mock_request_converter),
        ModelEndpointInfo=MagicMock(return_value=mock_model_endpoint),
    ):
        worker = Worker(
            service_config=worker_service_config,
            user_config=worker_user_config,
            service_id="test-worker",
        )

        # Override the created instances with our mocks
        worker.comms = mock_communication
        worker.inference_client = mock_inference_client
        worker.request_converter = mock_request_converter
        worker.model_endpoint = mock_model_endpoint

        yield worker


@pytest.fixture
async def initialized_worker(
    worker_instance: Worker,
    mock_communication_clients: dict[str, AsyncMock],
) -> AsyncGenerator[Worker, None]:
    """Create an initialized worker instance for testing."""
    worker = await worker_instance.__anext__()

    # Set up the communication clients
    worker.credit_drop_client = mock_communication_clients["credit_drop"]
    worker.credit_return_client = mock_communication_clients["credit_return"]
    worker.inference_results_client = mock_communication_clients["inference_results"]
    worker.conversation_data_client = mock_communication_clients["conversation_data"]
    worker.pub_client = mock_communication_clients["pub"]

    # Initialize the worker
    await worker.initialize()

    yield worker

    # Cleanup
    await worker.stop()


@pytest.fixture
def mock_time_functions() -> Generator[dict[str, MagicMock], None, None]:
    """Mock time functions for consistent testing."""
    with patch.multiple(
        "time",
        time_ns=MagicMock(return_value=1000000000),
        perf_counter_ns=MagicMock(return_value=2000000000),
    ) as mocks:
        yield mocks


@pytest.fixture
def mock_asyncio_sleep() -> Generator[AsyncMock, None, None]:
    """Mock asyncio.sleep for testing."""
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        yield mock_sleep


@pytest.fixture
def command_message() -> CommandMessage:
    """Create a sample command message for testing."""
    return CommandMessage(
        service_id="test-service",
        service_type=ServiceType.WORKER,
        command="test-command",
        data={"test": "data"},
    )
