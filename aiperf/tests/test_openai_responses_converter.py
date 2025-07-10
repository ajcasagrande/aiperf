# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Tests for OpenAI Responses converter."""

import base64
from unittest.mock import Mock

import pytest

from aiperf.clients.openai.openai_responses import (
    OpenAIResponsesRequestConverter,
    ReasoningEffort,
    ResponsesImageUrlContent,
    ResponsesInputAudioContent,
    ResponsesInputType,
    ResponsesRequest,
    ResponsesTextContent,
)
from aiperf.common.dataset_models import Audio, Image, Text, Turn
from aiperf.common.enums import EndpointType
from aiperf.common.exceptions import AIPerfError


class TestResponsesEnums:
    """Test reasoning effort and input type enums."""

    def test_reasoning_effort_values(self):
        """Test ReasoningEffort enum values."""
        assert ReasoningEffort.LOW == "low"
        assert ReasoningEffort.MEDIUM == "medium"
        assert ReasoningEffort.HIGH == "high"

    def test_reasoning_effort_case_insensitive(self):
        """Test ReasoningEffort case insensitivity."""
        assert ReasoningEffort("LOW") == ReasoningEffort.LOW
        assert ReasoningEffort("Medium") == ReasoningEffort.MEDIUM
        assert ReasoningEffort("HiGh") == ReasoningEffort.HIGH

    def test_responses_input_type_values(self):
        """Test ResponsesInputType enum values."""
        assert ResponsesInputType.TEXT == "text"
        assert ResponsesInputType.IMAGE_URL == "image_url"
        assert ResponsesInputType.INPUT_AUDIO == "input_audio"


class TestResponsesContentModels:
    """Test responses content model classes."""

    def test_responses_text_content(self):
        """Test ResponsesTextContent model."""
        content = ResponsesTextContent(text="Hello world")
        assert content.type == ResponsesInputType.TEXT
        assert content.text == "Hello world"

    def test_responses_image_url_content_valid(self):
        """Test ResponsesImageUrlContent with valid data."""
        content = ResponsesImageUrlContent(
            image_url={"url": "https://example.com/image.jpg", "detail": "high"}
        )
        assert content.type == ResponsesInputType.IMAGE_URL
        assert content.image_url["url"] == "https://example.com/image.jpg"
        assert content.image_url["detail"] == "high"

    def test_responses_image_url_content_invalid_dict(self):
        """Test ResponsesImageUrlContent with invalid dict."""
        with pytest.raises(ValueError, match="image_url must be a dictionary"):
            ResponsesImageUrlContent(image_url="not a dict")

    def test_responses_image_url_content_missing_url(self):
        """Test ResponsesImageUrlContent with missing URL."""
        with pytest.raises(ValueError, match="image_url must contain 'url' field"):
            ResponsesImageUrlContent(image_url={"detail": "high"})

    def test_responses_input_audio_content_valid(self):
        """Test ResponsesInputAudioContent with valid data."""
        content = ResponsesInputAudioContent(
            input_audio={"data": "base64data", "format": "wav"}
        )
        assert content.type == ResponsesInputType.INPUT_AUDIO
        assert content.input_audio["data"] == "base64data"
        assert content.input_audio["format"] == "wav"

    def test_responses_input_audio_content_invalid_dict(self):
        """Test ResponsesInputAudioContent with invalid dict."""
        with pytest.raises(ValueError, match="input_audio must be a dictionary"):
            ResponsesInputAudioContent(input_audio="not a dict")

    def test_responses_input_audio_content_missing_data(self):
        """Test ResponsesInputAudioContent with missing data."""
        with pytest.raises(ValueError, match="input_audio must contain 'data' field"):
            ResponsesInputAudioContent(input_audio={"format": "wav"})

    def test_responses_input_audio_content_missing_format(self):
        """Test ResponsesInputAudioContent with missing format."""
        with pytest.raises(ValueError, match="input_audio must contain 'format' field"):
            ResponsesInputAudioContent(input_audio={"data": "base64data"})


class TestResponsesRequest:
    """Test ResponsesRequest model."""

    def test_responses_request_minimal(self):
        """Test ResponsesRequest with minimal parameters."""
        request = ResponsesRequest(
            model="o1-preview", input="What is the capital of France?"
        )
        assert request.model == "o1-preview"
        assert request.input == "What is the capital of France?"
        assert request.max_output_tokens is None
        assert request.reasoning_effort is None
        assert request.stream is False

    def test_responses_request_full(self):
        """Test ResponsesRequest with all parameters."""
        request = ResponsesRequest(
            model="o1-preview",
            input="Solve this complex math problem",
            max_output_tokens=1000,
            reasoning_effort=ReasoningEffort.HIGH,
            stream=True,
            store=True,
            metadata={"user": "test"},
        )
        assert request.model == "o1-preview"
        assert request.input == "Solve this complex math problem"
        assert request.max_output_tokens == 1000
        assert request.reasoning_effort == ReasoningEffort.HIGH
        assert request.stream is True
        assert request.store is True
        assert request.metadata == {"user": "test"}

    def test_responses_request_empty_string_input(self):
        """Test ResponsesRequest with empty string input."""
        with pytest.raises(ValueError, match="Input string cannot be empty"):
            ResponsesRequest(model="o1-preview", input="")

    def test_responses_request_empty_list_input(self):
        """Test ResponsesRequest with empty list input."""
        with pytest.raises(ValueError, match="Input array cannot be empty"):
            ResponsesRequest(model="o1-preview", input=[])

    def test_responses_request_invalid_input_type(self):
        """Test ResponsesRequest with invalid input type."""
        with pytest.raises(
            ValueError, match="Input must be a string or array of content objects"
        ):
            ResponsesRequest(model="o1-preview", input=123)

    def test_responses_request_list_input(self):
        """Test ResponsesRequest with list input."""
        content = ResponsesTextContent(text="Hello")
        request = ResponsesRequest(model="o1-preview", input=[content])
        assert request.input == [content]


class TestOpenAIResponsesRequestConverter:
    """Test OpenAIResponsesRequestConverter."""

    @pytest.fixture
    def converter(self):
        """Create a converter instance."""
        return OpenAIResponsesRequestConverter()

    @pytest.fixture
    def mock_model_endpoint(self):
        """Create a mock model endpoint."""
        endpoint = Mock()
        endpoint.max_tokens = 1000
        endpoint.streaming = False
        endpoint.extra = {}

        model_endpoint = Mock()
        model_endpoint.primary_model_name = "o1-preview"
        model_endpoint.endpoint = endpoint

        return model_endpoint

    @pytest.fixture
    def sample_audio_base64(self):
        """Sample base64 audio data."""
        return base64.b64encode(b"fake audio data").decode("utf-8")

    def test_converter_registration(self):
        """Test that converter is properly registered."""
        from aiperf.clients.client_interfaces import RequestConverterFactory

        converter = RequestConverterFactory.create(EndpointType.OPENAI_RESPONSES)
        assert isinstance(converter, OpenAIResponsesRequestConverter)

    def test_format_payload_text_only(self, converter, mock_model_endpoint):
        """Test formatting payload with text only."""
        turn = Turn(
            text=[Text(content=["What is quantum computing?"])], images=[], audio=[]
        )

        payload = converter.format_payload(mock_model_endpoint, turn)

        assert payload["model"] == "o1-preview"
        assert payload["input"] == "What is quantum computing?"
        assert payload["max_output_tokens"] == 1000
        assert payload["stream"] is False

    def test_format_payload_multiple_text_items(self, converter, mock_model_endpoint):
        """Test formatting payload with multiple text items."""
        turn = Turn(
            text=[Text(content=["First question"]), Text(content=["Second question"])],
            images=[],
            audio=[],
        )

        payload = converter.format_payload(mock_model_endpoint, turn)

        assert payload["model"] == "o1-preview"
        assert isinstance(payload["input"], list)
        assert len(payload["input"]) == 2
        assert payload["input"][0]["type"] == "text"
        assert payload["input"][0]["text"] == "First question"
        assert payload["input"][1]["type"] == "text"
        assert payload["input"][1]["text"] == "Second question"

    def test_format_payload_with_images(self, converter, mock_model_endpoint):
        """Test formatting payload with images."""
        turn = Turn(
            text=[Text(content=["Describe this image"])],
            images=[Image(url="https://example.com/image.jpg")],
            audio=[],
        )

        payload = converter.format_payload(mock_model_endpoint, turn)

        assert payload["model"] == "o1-preview"
        assert isinstance(payload["input"], list)
        assert len(payload["input"]) == 2

        # Check text content
        text_content = next(item for item in payload["input"] if item["type"] == "text")
        assert text_content["text"] == "Describe this image"

        # Check image content
        image_content = next(
            item for item in payload["input"] if item["type"] == "image_url"
        )
        assert image_content["image_url"]["url"] == "https://example.com/image.jpg"
        assert image_content["image_url"]["detail"] == "auto"

    def test_format_payload_with_base64_image(self, converter, mock_model_endpoint):
        """Test formatting payload with base64 image."""
        turn = Turn(
            text=[Text(content=["Analyze this image"])],
            images=[
                Image(
                    base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
                )
            ],
            audio=[],
        )

        payload = converter.format_payload(mock_model_endpoint, turn)

        # Check image content
        image_content = next(
            item for item in payload["input"] if item["type"] == "image_url"
        )
        assert image_content["image_url"]["url"].startswith("data:image/jpeg;base64,")
        assert (
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            in image_content["image_url"]["url"]
        )

    def test_format_payload_with_audio(
        self, converter, mock_model_endpoint, sample_audio_base64
    ):
        """Test formatting payload with audio."""
        turn = Turn(
            text=[Text(content=["Transcribe this audio"])],
            images=[],
            audio=[Audio(base64=sample_audio_base64, format="wav")],
        )

        payload = converter.format_payload(mock_model_endpoint, turn)

        # Check audio content
        audio_content = next(
            item for item in payload["input"] if item["type"] == "input_audio"
        )
        assert audio_content["input_audio"]["data"] == sample_audio_base64
        assert audio_content["input_audio"]["format"] == "wav"

    def test_format_payload_multimodal(
        self, converter, mock_model_endpoint, sample_audio_base64
    ):
        """Test formatting payload with all content types."""
        turn = Turn(
            text=[Text(content=["Analyze this multimodal content"])],
            images=[Image(url="https://example.com/image.jpg")],
            audio=[Audio(base64=sample_audio_base64, format="wav")],
        )

        payload = converter.format_payload(mock_model_endpoint, turn)

        assert isinstance(payload["input"], list)
        assert len(payload["input"]) == 3

        # Check all content types are present
        content_types = [item["type"] for item in payload["input"]]
        assert "text" in content_types
        assert "image_url" in content_types
        assert "input_audio" in content_types

    def test_format_payload_with_reasoning_effort(self, converter, mock_model_endpoint):
        """Test formatting payload with reasoning effort."""
        mock_model_endpoint.endpoint.extra = {"reasoning_effort": "high"}

        turn = Turn(
            text=[Text(content=["Solve this complex problem"])], images=[], audio=[]
        )

        payload = converter.format_payload(mock_model_endpoint, turn)

        assert payload["reasoning_effort"] == "high"

    def test_format_payload_with_store_parameter(self, converter, mock_model_endpoint):
        """Test formatting payload with store parameter."""
        mock_model_endpoint.endpoint.extra = {"store": True}

        turn = Turn(text=[Text(content=["Store this completion"])], images=[], audio=[])

        payload = converter.format_payload(mock_model_endpoint, turn)

        assert payload["store"] is True

    def test_format_payload_with_metadata(self, converter, mock_model_endpoint):
        """Test formatting payload with metadata."""
        mock_model_endpoint.endpoint.extra = {"metadata": {"user": "test_user"}}

        turn = Turn(text=[Text(content=["Test request"])], images=[], audio=[])

        payload = converter.format_payload(mock_model_endpoint, turn)

        assert payload["metadata"] == {"user": "test_user"}

    def test_format_payload_empty_turn(self, converter, mock_model_endpoint):
        """Test formatting payload with empty turn."""
        turn = Turn(text=[], images=[], audio=[])

        with pytest.raises(AIPerfError):
            converter.format_payload(mock_model_endpoint, turn)

    def test_format_payload_invalid_reasoning_effort(
        self, converter, mock_model_endpoint
    ):
        """Test formatting payload with invalid reasoning effort."""
        mock_model_endpoint.endpoint.extra = {"reasoning_effort": "invalid"}

        turn = Turn(text=[Text(content=["Test request"])], images=[], audio=[])

        payload = converter.format_payload(mock_model_endpoint, turn)

        # Invalid reasoning effort should be ignored
        assert "reasoning_effort" not in payload

    def test_validate_o1_model_compatibility(self, converter):
        """Test o1 model compatibility validation."""
        # Should not raise warnings for o1 models
        converter._validate_o1_model_compatibility("o1-preview")
        converter._validate_o1_model_compatibility("o1-mini")
        converter._validate_o1_model_compatibility("o3-mini")

        # Should log warning for non-o1 models
        with pytest.raises(AttributeError):
            # This will trigger the warning log
            converter._validate_o1_model_compatibility("gpt-4")

    @pytest.mark.parametrize("reasoning_effort", ["low", "medium", "high"])
    def test_reasoning_effort_values(
        self, converter, mock_model_endpoint, reasoning_effort
    ):
        """Test different reasoning effort values."""
        mock_model_endpoint.endpoint.extra = {"reasoning_effort": reasoning_effort}

        turn = Turn(text=[Text(content=["Test reasoning"])], images=[], audio=[])

        payload = converter.format_payload(mock_model_endpoint, turn)

        assert payload["reasoning_effort"] == reasoning_effort

    def test_convert_turn_to_input_single_text(self, converter):
        """Test converting turn with single text to input."""
        turn = Turn(text=[Text(content=["Single text"])], images=[], audio=[])

        input_content = converter._convert_turn_to_input(turn)

        assert isinstance(input_content, str)
        assert input_content == "Single text"

    def test_convert_turn_to_input_multiple_content(self, converter):
        """Test converting turn with multiple content items to input."""
        turn = Turn(
            text=[Text(content=["First"]), Text(content=["Second"])],
            images=[],
            audio=[],
        )

        input_content = converter._convert_turn_to_input(turn)

        assert isinstance(input_content, list)
        assert len(input_content) == 2
        assert input_content[0].text == "First"
        assert input_content[1].text == "Second"

    def test_convert_turn_to_input_empty_content(self, converter):
        """Test converting turn with empty content."""
        turn = Turn(text=[], images=[], audio=[])

        with pytest.raises(
            ValueError, match="Turn must contain at least one type of content"
        ):
            converter._convert_turn_to_input(turn)

    def test_convert_turn_to_input_filters_empty_strings(self, converter):
        """Test that empty strings are filtered out."""
        turn = Turn(
            text=[Text(content=["Valid text", "", "   ", "Another valid text"])],
            images=[],
            audio=[],
        )

        input_content = converter._convert_turn_to_input(turn)

        assert isinstance(input_content, list)
        assert len(input_content) == 2
        assert input_content[0].text == "Valid text"
        assert input_content[1].text == "Another valid text"


class TestResponsesConverterIntegration:
    """Integration tests for the responses converter."""

    @pytest.fixture
    def converter(self):
        """Create a converter instance."""
        return OpenAIResponsesRequestConverter()

    def test_end_to_end_text_conversion(self, converter):
        """Test end-to-end text conversion."""
        # Create mock model endpoint
        endpoint = Mock()
        endpoint.max_tokens = 2000
        endpoint.streaming = True
        endpoint.extra = {
            "reasoning_effort": "medium",
            "store": True,
            "metadata": {"task": "reasoning"},
        }

        model_endpoint = Mock()
        model_endpoint.primary_model_name = "o1-preview"
        model_endpoint.endpoint = endpoint

        # Create turn
        turn = Turn(
            text=[Text(content=["Explain quantum entanglement in simple terms"])],
            images=[],
            audio=[],
        )

        # Convert
        payload = converter.format_payload(model_endpoint, turn)

        # Verify results
        assert payload["model"] == "o1-preview"
        assert payload["input"] == "Explain quantum entanglement in simple terms"
        assert payload["max_output_tokens"] == 2000
        assert payload["stream"] is True
        assert payload["reasoning_effort"] == "medium"
        assert payload["store"] is True
        assert payload["metadata"] == {"task": "reasoning"}

    def test_performance_benchmark(self, converter):
        """Test performance of the converter."""
        import time

        # Create test data
        endpoint = Mock()
        endpoint.max_tokens = 1000
        endpoint.streaming = False
        endpoint.extra = {}

        model_endpoint = Mock()
        model_endpoint.primary_model_name = "o1-preview"
        model_endpoint.endpoint = endpoint

        turn = Turn(text=[Text(content=["Test content"])], images=[], audio=[])

        # Benchmark conversion
        start_time = time.time()
        for _ in range(100):
            payload = converter.format_payload(model_endpoint, turn)
        end_time = time.time()

        # Should complete 100 conversions in under 1 second
        assert end_time - start_time < 1.0

        # Verify last conversion is correct
        assert payload["model"] == "o1-preview"
        assert payload["input"] == "Test content"
