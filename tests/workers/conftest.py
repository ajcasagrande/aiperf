# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from unittest.mock import AsyncMock, MagicMock

import pytest

from aiperf.common.config import EndpointConfig, ServiceConfig, WorkersConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums import CreditPhase, EndpointType
from aiperf.common.messages import CreditDropMessage, WorkerHealthMessage
from aiperf.common.models import ProcessHealth, WorkerPhaseTaskStats
from tests.common.conftest import (
    BaseTestServiceWithMixins,
)


# Enhanced fixtures for worker-specific configurations
@pytest.fixture
def worker_service_config(mock_service_config: ServiceConfig):
    """Enhanced service config with worker-specific settings."""
    mock_service_config.workers = WorkersConfig(
        health_check_interval=1.0,
        max=4,
        min=1,
    )
    return mock_service_config


@pytest.fixture
def worker_user_config(mock_user_config: UserConfig):
    """Enhanced user config for worker tests."""
    mock_user_config.endpoint = EndpointConfig(
        model_names=["test-model"],
        type=EndpointType.OPENAI_CHAT_COMPLETIONS,
        url="http://localhost:8000",
    )
    return mock_user_config


@pytest.fixture
def sample_credit_drop_message() -> CreditDropMessage:
    """Sample credit drop message for testing."""
    return CreditDropMessage(
        service_id="test-service",
        conversation_id="test-conversation-1",
        phase=CreditPhase.PROFILING,
        credit_drop_ns=1000000000,
    )


@pytest.fixture
def sample_worker_health_message() -> WorkerHealthMessage:
    """Sample worker health message."""
    return WorkerHealthMessage(
        service_id="worker-123",
        process=ProcessHealth(
            create_time=1000.0,
            uptime=100.0,
            cpu_usage=10.5,
            memory_usage=256.0,
        ),
        task_stats={
            CreditPhase.PROFILING: WorkerPhaseTaskStats(total=10, completed=8, failed=2)
        },
    )


@pytest.fixture
def mock_inference_dependencies():
    """Mock all inference-related dependencies."""
    model_endpoint = MagicMock()
    model_endpoint.primary_model_name = "test-model"

    return {
        "inference_client": AsyncMock(),
        "request_converter": AsyncMock(),
        "model_endpoint": model_endpoint,
        "conversation_request_client": AsyncMock(),
        "inference_results_push_client": AsyncMock(),
    }


class WorkerTestBase(BaseTestServiceWithMixins):
    """Base test class for worker-related tests with worker-specific configurations."""

    pass
