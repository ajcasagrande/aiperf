# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Basic tests for the integration test server."""

import json

import pytest
from fastapi.testclient import TestClient

from mock_server.app import app, set_server_config
from mock_server.config import MockServerConfig


@pytest.fixture
def test_config():
    """Test configuration with fast latencies."""
    return MockServerConfig(
        port=8000,
        host="127.0.0.1",
        ttft=10.0,  # Fast for testing
        itl=5.0,  # Fast for testing
    )


@pytest.fixture
def client(test_config):
    """Test client with test configuration."""
    set_server_config(test_config)
    return TestClient(app)


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "config" in data


def test_root_endpoint(client):
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "endpoints" in data
    assert "config" in data


def test_non_streaming_completion(client):
    """Test non-streaming chat completion."""
    request_data = {
        "model": "gpt2",
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 5,
        "stream": False,
    }

    response = client.post("/v1/chat/completions", json=request_data)
    assert response.status_code == 200

    data = response.json()
    assert data["object"] == "chat.completion"
    assert data["model"] == "gpt2"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert "usage" in data
    assert data["usage"]["completion_tokens"] <= 5


def test_streaming_completion(client):
    """Test streaming chat completion."""
    request_data = {
        "model": "gpt2",
        "messages": [{"role": "user", "content": "Hi"}],
        "max_tokens": 3,
        "stream": True,
    }

    response = client.post("/v1/chat/completions", json=request_data)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    # Parse streaming response
    content = response.text
    lines = content.strip().split("\n")

    # Should have data lines and a final [DONE]
    data_lines = [line for line in lines if line.startswith("data: ")]
    assert len(data_lines) > 0
    assert any("[DONE]" in line for line in data_lines)

    # Parse first chunk
    first_data_line = data_lines[0]
    chunk_json = first_data_line.replace("data: ", "")
    chunk = json.loads(chunk_json)

    assert chunk["object"] == "chat.completion.chunk"
    assert chunk["model"] == "gpt2"
    assert len(chunk["choices"]) == 1


def test_max_tokens_limit(client):
    """Test that max_tokens limit is respected."""
    request_data = {
        "model": "gpt2",
        "messages": [
            {
                "role": "user",
                "content": "This is a longer message that should be truncated",
            }
        ],
        "max_tokens": 2,
        "stream": False,
    }

    response = client.post("/v1/chat/completions", json=request_data)
    assert response.status_code == 200

    data = response.json()
    assert data["usage"]["completion_tokens"] <= 2


@pytest.mark.asyncio
async def test_server_startup():
    """Test that the server can start up properly."""
    config = MockServerConfig(
        port=8001,  # Different port to avoid conflicts
        ttft=1.0,
        itl=1.0,
    )

    set_server_config(config)

    # Test that the app configuration was set
    from mock_server.app import server_config as app_config

    assert app_config.ttft == 1.0
    assert app_config.itl == 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
