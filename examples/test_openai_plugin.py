# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Simple tests for the OpenAI Chat endpoint plugin."""

import pytest

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.config import UserConfig
from aiperf.common.models import (
    Audio,
    Image,
    RequestRecord,
    Text,
    TextResponse,
    Turn,
)
from aiperf.common.plugins.plugin_specs import TransportType
from examples.openai_chat_endpoint_plugin import (
    OpenAIChatEndpoint,
    OpenAIChatReasoningEndpoint,
    OpenAIChatStreamingEndpoint,
)


class TestOpenAIChatEndpoint:
    """Test cases for the OpenAI Chat endpoint plugin."""

    @pytest.fixture
    def endpoint(self):
        """Create a basic OpenAI chat endpoint for testing."""
        config = UserConfig()
        model_endpoint = ModelEndpointInfo.from_user_config(config)
        return OpenAIChatEndpoint(model_endpoint)

    def test_endpoint_info(self, endpoint):
        """Test that endpoint info is correctly configured."""
        info = endpoint.get_endpoint_info()

        assert info.endpoint_tag == "openai-chat"
        assert info.service_kind == "openai"
        assert info.supports_streaming is True
        assert info.produces_tokens is True
        assert info.supports_audio is True
        assert info.supports_images is True
        assert info.endpoint_path == "/v1/chat/completions"
        assert info.transport_config.default_transport == TransportType.HTTP

    @pytest.mark.asyncio
    async def test_simple_text_formatting(self, endpoint):
        """Test formatting a simple text message."""
        turn = Turn(
            texts=[Text(contents=["Hello, world!"])],
            role="user",
            model="gpt-4o",
        )

        payload = await endpoint.format_payload(turn)

        assert payload["model"] == "gpt-4o"
        assert payload["messages"][0]["role"] == "user"
        assert payload["messages"][0]["content"] == "Hello, world!"
        assert "stream" in payload

    @pytest.mark.asyncio
    async def test_multimodal_formatting(self, endpoint):
        """Test formatting multi-modal content."""
        turn = Turn(
            texts=[Text(contents=["Describe this image"])],
            images=[Image(contents=["data:image/jpeg;base64,fake_image_data"])],
            role="user",
            model="gpt-4o",
        )

        payload = await endpoint.format_payload(turn)

        assert len(payload["messages"]) == 1
        message_content = payload["messages"][0]["content"]
        assert isinstance(message_content, list)
        assert len(message_content) == 2

        # Check text content
        text_content = next(item for item in message_content if item["type"] == "text")
        assert text_content["text"] == "Describe this image"

        # Check image content
        image_content = next(
            item for item in message_content if item["type"] == "image_url"
        )
        assert (
            "data:image/jpeg;base64,fake_image_data"
            in image_content["image_url"]["url"]
        )

    @pytest.mark.asyncio
    async def test_audio_formatting(self, endpoint):
        """Test formatting audio content."""
        turn = Turn(
            texts=[Text(contents=["Transcribe this audio"])],
            audios=[Audio(contents=["mp3,fake_audio_data"])],
            role="user",
            model="gpt-4o-audio",
        )

        payload = await endpoint.format_payload(turn)

        message_content = payload["messages"][0]["content"]
        audio_content = next(
            item for item in message_content if item["type"] == "input_audio"
        )

        assert audio_content["input_audio"]["format"] == "mp3"
        assert audio_content["input_audio"]["data"] == "fake_audio_data"

    @pytest.mark.asyncio
    async def test_max_tokens_parameter(self, endpoint):
        """Test that max_tokens is correctly mapped to max_completion_tokens."""
        turn = Turn(
            texts=[Text(contents=["Hello"])],
            max_tokens=1000,
            model="gpt-4o",
        )

        payload = await endpoint.format_payload(turn)
        assert payload["max_completion_tokens"] == 1000

    def test_response_parsing_text_response(self, endpoint):
        """Test parsing a regular text response."""
        response_text = '{"object": "chat.completion", "choices": [{"message": {"content": "Hello there!"}}]}'
        text_response = TextResponse(text=response_text, perf_ns=1000000)

        record = RequestRecord(
            request_time_ns=1000000,
            model_name="gpt-4o",
            responses=[text_response],
            error_details=None,
        )

        # This would normally be called by the transport layer
        # For testing, we'll test the internal parsing method directly
        parsed_data = endpoint._parse_raw_text(response_text)
        assert parsed_data is not None

    def test_response_parsing_sse_done(self, endpoint):
        """Test parsing SSE [DONE] marker."""
        parsed_data = endpoint._parse_raw_text("[DONE]")
        assert parsed_data is None

    def test_response_parsing_empty(self, endpoint):
        """Test parsing empty response."""
        parsed_data = endpoint._parse_raw_text("")
        assert parsed_data is None

    def test_custom_headers(self, endpoint):
        """Test that custom headers are properly set."""
        headers = endpoint.get_custom_headers()

        assert "OpenAI-Beta" in headers
        assert "User-Agent" in headers
        assert "aiperf-openai-plugin" in headers["User-Agent"]

    def test_url_params(self, endpoint):
        """Test URL parameters."""
        params = endpoint.get_url_params()
        assert "version" in params


class TestOpenAIChatStreamingEndpoint:
    """Test cases for the streaming variant."""

    @pytest.fixture
    def endpoint(self):
        """Create a streaming OpenAI chat endpoint for testing."""
        config = UserConfig()
        model_endpoint = ModelEndpointInfo.from_user_config(config)
        return OpenAIChatStreamingEndpoint(model_endpoint)

    def test_endpoint_info(self, endpoint):
        """Test streaming endpoint info."""
        info = endpoint.get_endpoint_info()
        assert info.endpoint_tag == "openai-chat-streaming"
        assert "streaming" in info.description.lower()

    @pytest.mark.asyncio
    async def test_streaming_payload(self, endpoint):
        """Test that streaming is forced enabled."""
        turn = Turn(
            texts=[Text(contents=["Hello"])],
            model="gpt-4o",
        )

        payload = await endpoint.format_payload(turn)
        assert payload["stream"] is True
        assert "stream_options" in payload

    def test_streaming_headers(self, endpoint):
        """Test streaming-specific headers."""
        headers = endpoint.get_custom_headers()
        assert headers["Accept"] == "text/event-stream"
        assert "Cache-Control" in headers


class TestOpenAIChatReasoningEndpoint:
    """Test cases for the reasoning variant."""

    @pytest.fixture
    def endpoint(self):
        """Create a reasoning OpenAI chat endpoint for testing."""
        config = UserConfig()
        model_endpoint = ModelEndpointInfo.from_user_config(config)
        return OpenAIChatReasoningEndpoint(model_endpoint)

    def test_endpoint_info(self, endpoint):
        """Test reasoning endpoint info."""
        info = endpoint.get_endpoint_info()
        assert info.endpoint_tag == "openai-chat-reasoning"
        assert "reasoning" in info.description.lower()

    @pytest.mark.asyncio
    async def test_o1_model_parameters(self, endpoint):
        """Test that o1 models have restricted parameters."""
        turn = Turn(
            texts=[Text(contents=["Solve this problem"])],
            model="o1-preview",
        )

        payload = await endpoint.format_payload(turn)

        # These parameters should be removed for o1 models
        assert "temperature" not in payload
        assert "top_p" not in payload
        assert "frequency_penalty" not in payload
        assert "presence_penalty" not in payload

        # Reasoning-specific parameters should be added
        assert "reasoning_effort" in payload

    @pytest.mark.asyncio
    async def test_non_o1_model_parameters(self, endpoint):
        """Test that non-o1 models keep all parameters."""
        turn = Turn(
            texts=[Text(contents=["Hello"])],
            model="gpt-4o",
        )

        # Add some parameters via extra config
        endpoint.model_endpoint.endpoint.extra = [("temperature", 0.8)]

        payload = await endpoint.format_payload(turn)

        # Parameters should be preserved for non-o1 models
        assert payload.get("temperature") == 0.8


# Integration test
@pytest.mark.asyncio
async def test_plugin_integration():
    """Test that the plugin integrates properly with AIPerf patterns."""
    config = UserConfig()
    model_endpoint = ModelEndpointInfo.from_user_config(config)

    # Test all three variants
    endpoints = [
        OpenAIChatEndpoint(model_endpoint),
        OpenAIChatStreamingEndpoint(model_endpoint),
        OpenAIChatReasoningEndpoint(model_endpoint),
    ]

    for endpoint in endpoints:
        # Test endpoint info
        info = endpoint.get_endpoint_info()
        assert info.endpoint_tag.startswith("openai-chat")
        assert info.service_kind == "openai"

        # Test payload formatting
        turn = Turn(
            texts=[Text(contents=["Test message"])],
            model="gpt-4o",
        )
        payload = await endpoint.format_payload(turn)
        assert "messages" in payload
        assert "model" in payload

        # Test headers and params
        headers = endpoint.get_custom_headers()
        params = endpoint.get_url_params()
        assert isinstance(headers, dict)
        assert isinstance(params, dict)
