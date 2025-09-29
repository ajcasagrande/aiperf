# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for OpenAI plugins."""

import pytest

from aiperf.clients.openai.plugins import (
    OpenAIChatPlugin,
    OpenAICompletionsPlugin,
    OpenAIEmbeddingsPlugin,
    OpenAIRankingsPlugin,
    OpenAIResponsesPlugin,
)
from aiperf.common.enums import EndpointType
from aiperf.common.models import Text, Turn


class TestOpenAIChatPlugin:
    """Test the OpenAI Chat plugin."""

    @pytest.fixture
    def chat_plugin(self):
        return OpenAIChatPlugin()

    @pytest.fixture
    def chat_turn(self):
        return Turn(
            texts=[Text(contents=["Hello, how are you?"])],
            images=[],
            audios=[],
            role="user",
            max_tokens=150,
        )

    async def test_format_payload_basic(
        self, chat_plugin, sample_model_endpoint, chat_turn
    ):
        """Test basic chat payload formatting."""
        result = await chat_plugin.format_payload(
            EndpointType.CHAT, sample_model_endpoint, chat_turn
        )

        assert result is not None
        assert "messages" in result
        assert "model" in result
        assert "stream" in result
        assert result["max_completion_tokens"] == 150

    async def test_format_payload_wrong_endpoint_type(
        self, chat_plugin, sample_model_endpoint, chat_turn
    ):
        """Test that plugin returns None for wrong endpoint type."""
        result = await chat_plugin.format_payload(
            EndpointType.EMBEDDINGS, sample_model_endpoint, chat_turn
        )

        assert result is None

    async def test_format_payload_with_images_and_audio(
        self, chat_plugin, sample_model_endpoint
    ):
        """Test chat payload with images and audio."""
        from aiperf.common.models import Audio, Image

        turn = Turn(
            texts=[Text(contents=["Describe this image"])],
            images=[Image(contents=["http://example.com/image.jpg"])],
            audios=[Audio(contents=["wav,base64audiodata"])],
            role="user",
        )

        result = await chat_plugin.format_payload(
            EndpointType.CHAT, sample_model_endpoint, turn
        )

        assert result is not None
        messages = result["messages"]
        assert len(messages) == 1

        content = messages[0]["content"]
        assert any(item["type"] == "text" for item in content)
        assert any(item["type"] == "image_url" for item in content)
        assert any(item["type"] == "input_audio" for item in content)

    async def test_invalid_audio_format(self, chat_plugin, sample_model_endpoint):
        """Test error handling for invalid audio format."""
        from aiperf.common.models import Audio

        turn = Turn(
            texts=[Text(contents=["Test"])],
            images=[],
            audios=[Audio(contents=["invalid_audio_format"])],
            role="user",
        )

        with pytest.raises(ValueError, match="Audio content must be in the format"):
            await chat_plugin.format_payload(
                EndpointType.CHAT, sample_model_endpoint, turn
            )


class TestOpenAICompletionsPlugin:
    """Test the OpenAI Completions plugin."""

    @pytest.fixture
    def completions_plugin(self):
        return OpenAICompletionsPlugin()

    async def test_format_payload_basic(
        self, completions_plugin, sample_model_endpoint, sample_turn
    ):
        """Test basic completions payload formatting."""
        result = await completions_plugin.format_payload(
            EndpointType.COMPLETIONS, sample_model_endpoint, sample_turn
        )

        assert result is not None
        assert "prompt" in result
        assert "model" in result
        assert "stream" in result
        assert result["max_tokens"] == 100

    async def test_format_payload_wrong_endpoint_type(
        self, completions_plugin, sample_model_endpoint, sample_turn
    ):
        """Test that plugin returns None for wrong endpoint type."""
        result = await completions_plugin.format_payload(
            EndpointType.CHAT, sample_model_endpoint, sample_turn
        )

        assert result is None


class TestOpenAIEmbeddingsPlugin:
    """Test the OpenAI Embeddings plugin."""

    @pytest.fixture
    def embeddings_plugin(self):
        return OpenAIEmbeddingsPlugin()

    async def test_format_payload_basic(
        self, embeddings_plugin, sample_model_endpoint, sample_turn
    ):
        """Test basic embeddings payload formatting."""
        result = await embeddings_plugin.format_payload(
            EndpointType.EMBEDDINGS, sample_model_endpoint, sample_turn
        )

        assert result is not None
        assert "input" in result
        assert "model" in result
        assert (
            "max_tokens" not in result
        )  # Should not include max_tokens for embeddings

    async def test_format_payload_wrong_endpoint_type(
        self, embeddings_plugin, sample_model_endpoint, sample_turn
    ):
        """Test that plugin returns None for wrong endpoint type."""
        result = await embeddings_plugin.format_payload(
            EndpointType.CHAT, sample_model_endpoint, sample_turn
        )

        assert result is None


class TestOpenAIRankingsPlugin:
    """Test the OpenAI Rankings plugin."""

    @pytest.fixture
    def rankings_plugin(self):
        return OpenAIRankingsPlugin()

    @pytest.fixture
    def rankings_turn(self):
        return Turn(
            texts=[
                Text(name="query", contents=["What is machine learning?"]),
                Text(
                    name="passages",
                    contents=[
                        "Machine learning is a subset of AI",
                        "Deep learning uses neural networks",
                        "Supervised learning uses labeled data",
                    ],
                ),
            ],
            images=[],
            audios=[],
            role="user",
        )

    async def test_format_payload_basic(
        self, rankings_plugin, sample_model_endpoint, rankings_turn
    ):
        """Test basic rankings payload formatting."""
        result = await rankings_plugin.format_payload(
            EndpointType.RANKINGS, sample_model_endpoint, rankings_turn
        )

        assert result is not None
        assert "query" in result
        assert "passages" in result
        assert "model" in result

        assert result["query"]["text"] == "What is machine learning?"
        assert len(result["passages"]) == 3

    async def test_format_payload_missing_query(
        self, rankings_plugin, sample_model_endpoint
    ):
        """Test error when query is missing."""
        turn = Turn(
            texts=[Text(name="passages", contents=["Some passage"])],
            images=[],
            audios=[],
            role="user",
        )

        with pytest.raises(
            ValueError, match="Rankings request requires a text with name 'query'"
        ):
            await rankings_plugin.format_payload(
                EndpointType.RANKINGS, sample_model_endpoint, turn
            )

    async def test_format_payload_wrong_endpoint_type(
        self, rankings_plugin, sample_model_endpoint, rankings_turn
    ):
        """Test that plugin returns None for wrong endpoint type."""
        result = await rankings_plugin.format_payload(
            EndpointType.CHAT, sample_model_endpoint, rankings_turn
        )

        assert result is None


class TestOpenAIResponsesPlugin:
    """Test the OpenAI Responses plugin."""

    @pytest.fixture
    def responses_plugin(self):
        return OpenAIResponsesPlugin()

    async def test_format_payload_basic(
        self, responses_plugin, sample_model_endpoint, sample_turn
    ):
        """Test basic responses payload formatting."""
        result = await responses_plugin.format_payload(
            EndpointType.RESPONSES, sample_model_endpoint, sample_turn
        )

        assert result is not None
        assert "input" in result
        assert "model" in result
        assert "stream" in result
        assert result["max_output_tokens"] == 100

    async def test_format_payload_wrong_endpoint_type(
        self, responses_plugin, sample_model_endpoint, sample_turn
    ):
        """Test that plugin returns None for wrong endpoint type."""
        result = await responses_plugin.format_payload(
            EndpointType.CHAT, sample_model_endpoint, sample_turn
        )

        assert result is None
