# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging
import subprocess
import time
from collections.abc import Generator

import pytest
from aiperf.common.config import EndPointConfig, UserConfig
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.config.worker_config import WorkersConfig
from aiperf.common.enums import AIPerfLogLevel, EndpointType

logging.basicConfig(level=logging.DEBUG)


def pytest_addoption(parser):
    """Add custom command line options for pytest."""
    parser.addoption(
        "--integration",
        action="store_true",
        default=True,
        help="Run integration tests (disabled by default)",
    )


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (disabled by default, use --integration to enable)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip performance and integration tests unless their respective options are given."""
    integration_enabled = config.getoption("--integration")
    skip_integration = pytest.mark.skip(
        reason="integration tests disabled (use --integration to enable)"
    )

    for item in items:
        if "integration" in item.keywords and not integration_enabled:
            item.add_marker(skip_integration)


@pytest.fixture(scope="session")
def mock_server_port() -> int:
    """Port for the mock OpenAI server."""
    return 8999


@pytest.fixture(scope="session")
def mock_server_process(
    mock_server_port: int,
) -> Generator[subprocess.Popen, None, None]:
    """Start the mock OpenAI server as a subprocess for integration testing."""
    # Start the mock server with a simple model tokenizer
    cmd = [
        "aiperf-mock-server",
        "--port",
        str(mock_server_port),
        "--ttft",
        "10",  # 10ms time to first token
        "--itl",
        "5",  # 5ms inter-token latency
        "--tokenizer-models",
        "gpt2",  # Pre-load gpt2 tokenizer
        "--log-level",
        "INFO",
    ]

    process = subprocess.Popen(cmd)

    # Wait for server to start up
    import requests

    max_retries = 30
    for i in range(max_retries):
        try:
            response = requests.get(
                f"http://localhost:{mock_server_port}/health", timeout=1
            )
            if response.status_code == 200:
                break
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if i == max_retries - 1:
                process.terminate()
                process.wait()
                raise RuntimeError("Mock server failed to start")
            time.sleep(0.5)

    yield process

    # Cleanup
    process.terminate()
    process.wait()


@pytest.fixture
def mock_server_url(
    mock_server_port: int, mock_server_process: subprocess.Popen
) -> str:
    """URL for the mock OpenAI server."""
    return f"http://localhost:{mock_server_port}"


@pytest.fixture
def user_config_for_mock_server(mock_server_url: str) -> UserConfig:
    """Create UserConfig pointing to the mock server."""
    endpoint_config = EndPointConfig(
        type=EndpointType.OPENAI_CHAT_COMPLETIONS,
        url=mock_server_url,
        streaming=False,
    )

    return UserConfig(model_names=["gpt2"], endpoint=endpoint_config)


@pytest.fixture
def user_config_streaming(mock_server_url: str) -> UserConfig:
    """Create UserConfig for streaming tests with the mock server."""
    endpoint_config = EndPointConfig(
        type=EndpointType.OPENAI_CHAT_COMPLETIONS,
        url=mock_server_url,
        streaming=True,
    )

    return UserConfig(model_names=["gpt2"], endpoint=endpoint_config)


@pytest.fixture
def service_config_for_mock_server() -> ServiceConfig:
    """Create ServiceConfig for the mock server."""
    return ServiceConfig(
        disable_ui=True,
        log_level=AIPerfLogLevel.DEBUG,
        workers=WorkersConfig(min=1, max=1),
    )
