# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Integration test examples using command strings."""

import pytest

from tests.integration.helpers import AIPerfCLI, parse_command
from tests.integration.test_models import FakeAIServer


@pytest.mark.integration
@pytest.mark.asyncio
async def test_simple_chat_benchmark(cli: AIPerfCLI, fakeai_server: FakeAIServer):
    """Simple chat benchmark with streaming."""
    result = await cli.run(
        f"""
        aiperf profile \
            --model Qwen/Qwen3-0.6B \
            --url {fakeai_server.url} \
            --endpoint-type chat \
            --concurrency 10 \
            --request-count 100 \
            --streaming
        """
    )

    assert result.request_count >= 100
    assert "ttft" in result.metrics


@pytest.mark.integration
@pytest.mark.asyncio
async def test_embeddings_benchmark(cli: AIPerfCLI, fakeai_server: FakeAIServer):
    """Embeddings benchmark example."""
    result = await cli.run(
        f"""
        aiperf profile \
            --model text-embedding-3-small \
            --url {fakeai_server.url} \
            --endpoint-type embeddings \
            --concurrency 50 \
            --request-count 200
        """
    )

    assert result.request_count >= 200
    assert "request_latency" in result.metrics


@pytest.mark.integration
@pytest.mark.asyncio
async def test_with_multiple_variables(cli: AIPerfCLI, fakeai_server: FakeAIServer):
    """Use f-string variables for flexibility."""
    model_name = "gpt-4-turbo"
    concurrency = 25

    result = await cli.run(
        f"""
        aiperf profile \
            --model {model_name} \
            --url {fakeai_server.url} \
            --endpoint-type chat \
            --concurrency {concurrency} \
            --request-count 50
        """
    )

    assert result.request_count >= 50


def test_parse_command_standalone():
    """Use parse_command directly for custom workflows."""
    model = "gpt-4"
    base_url = "http://localhost:8000"

    args = parse_command(
        f"""
        aiperf profile \
            --model {model} \
            --url {base_url} \
            --streaming
        """
    )

    assert args == [
        "profile",
        "--model",
        "gpt-4",
        "--url",
        "http://localhost:8000",
        "--streaming",
    ]


def test_parse_command_no_backslashes():
    """Works with single-line commands too."""
    url = "http://test:9000"
    args = parse_command(f"aiperf profile --model gpt-4 --url {url} --streaming")

    assert "--url" in args
    assert "http://test:9000" in args
