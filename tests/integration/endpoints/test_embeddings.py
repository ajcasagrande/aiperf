# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import pytest

from tests.integration.helpers import AIPerfCLI, MockLLMServer


@pytest.mark.integration
@pytest.mark.asyncio
class TestEmbeddingsEndpoint:
    """Tests for /v1/embeddings endpoint."""

    async def test_basic_embeddings(
        self, cli: AIPerfCLI, mock_llm_server: MockLLMServer
    ):
        """Basic embeddings."""
        result = await cli.run(
            f"""
            aiperf profile \
                --model text-embedding-3-small \
                --tokenizer gpt2 \
                --url {mock_llm_server.url} \
                --endpoint-type embeddings \
                --request-count 10 \
                --concurrency 2 \
                --ui simple
            """
        )
        assert result.request_count == 10
        assert "ttft" not in result.metrics

    async def test_high_concurrency(
        self, cli: AIPerfCLI, mock_llm_server: MockLLMServer
    ):
        """High concurrency embeddings."""
        result = await cli.run(
            f"""
            aiperf profile \
                --model text-embedding-3-small \
                --tokenizer gpt2 \
                --url {mock_llm_server.url} \
                --endpoint-type embeddings \
                --concurrency 50 \
                --request-count 200 \
                --ui simple
            """
        )
        assert result.request_count == 200
