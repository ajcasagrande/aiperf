# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive tests for the multimodal chat completions request converter.

This module demonstrates the modern AIPerf approach to testing with pytest,
fixtures, parameterization, and comprehensive coverage.
"""

import base64
import json

import pytest

from aiperf.clients.model_endpoint_info import (
    EndpointInfo,
    ModelEndpointInfo,
    ModelInfo,
    ModelListInfo,
)
from aiperf.clients.openai.openai_multimodal_chat import (
    AudioFormat,
    ChatMessage,
    ImageDetail,
    ImageUrlContent,
    InputAudioContent,
    MessageRole,
    MultimodalChatCompletionsRequest,
    OpenAIMultimodalChatCompletionsRequestConverter,
    TextContent,
)
from aiperf.common.dataset_models import Audio, Image, Text, Turn
from aiperf.common.enums import EndpointType, ModelSelectionStrategy
from aiperf.common.exceptions import AIPerfError


class TestMultimodalConverter:
    """Test suite for the multimodal chat completions converter."""

    @pytest.fixture
    def converter(self):
        """Create a converter instance for testing."""
        return OpenAIMultimodalChatCompletionsRequestConverter()

    @pytest.fixture
    def model_endpoint(self):
        """Create a mock model endpoint for testing."""
        return ModelEndpointInfo(
            models=ModelListInfo(
                models=[ModelInfo(name="gpt-4o-mini")],
                model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
            ),
            endpoint=EndpointInfo(
                type=EndpointType.OPENAI_MULTIMODAL,
                streaming=True,
                extra={"temperature": 0.7, "max_tokens": 1000},
            ),
        )

    @pytest.fixture
    def sample_audio_base64(self):
        """Create sample base64 audio data for testing."""
        # Create a simple WAV header + some data
        wav_header = b"RIFF\x24\x08\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x44\xac\x00\x00\x44\xac\x00\x00\x01\x00\x08\x00data\x00\x08\x00\x00"
        sample_data = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        wav_data = wav_header + sample_data
        return base64.b64encode(wav_data).decode()

    class TestTextContent:
        """Test text content handling."""

        def test_text_content_creation(self):
            """Test creating text content."""
            content = TextContent(text="Hello, world!")
            assert content.type == "text"
            assert content.text == "Hello, world!"

        def test_text_content_validation(self):
            """Test text content validation."""
            with pytest.raises(ValueError):
                TextContent(text="")

    class TestImageContent:
        """Test image content handling."""

        def test_image_url_content_creation(self):
            """Test creating image URL content."""
            content = ImageUrlContent.from_url("https://example.com/image.jpg")
            assert content.type == "image_url"
            assert content.image_url["url"] == "https://example.com/image.jpg"
            assert content.image_url["detail"] == ImageDetail.AUTO

        def test_image_url_content_with_detail(self):
            """Test creating image URL content with detail level."""
            content = ImageUrlContent.from_url(
                "https://example.com/image.jpg", ImageDetail.HIGH
            )
            assert content.image_url["detail"] == ImageDetail.HIGH

        def test_image_url_validation(self):
            """Test image URL validation."""
            with pytest.raises(ValueError):
                ImageUrlContent(image_url={"invalid": "structure"})

    class TestAudioContent:
        """Test audio content handling."""

        def test_audio_content_creation(self, sample_audio_base64):
            """Test creating audio content."""
            content = InputAudioContent.from_base64(
                sample_audio_base64, AudioFormat.WAV
            )
            assert content.type == "input_audio"
            assert content.input_audio["data"] == sample_audio_base64
            assert content.input_audio["format"] == AudioFormat.WAV

        def test_audio_content_validation(self):
            """Test audio content validation."""
            with pytest.raises(ValueError):
                InputAudioContent(input_audio={"invalid": "structure"})

    class TestChatMessage:
        """Test chat message creation and validation."""

        def test_chat_message_from_text_turn(self):
            """Test creating chat message from text-only turn."""
            turn = Turn(
                text=[Text(content=["Hello", "How are you?"])],
                role="user",
            )

            message = ChatMessage.from_turn(turn)
            assert message.role == MessageRole.USER
            assert len(message.content) == 2
            assert all(isinstance(c, TextContent) for c in message.content)
            assert message.content[0].text == "Hello"
            assert message.content[1].text == "How are you?"

        def test_chat_message_from_multimodal_turn(self, sample_audio_base64):
            """Test creating chat message from multimodal turn."""
            turn = Turn(
                text=[Text(content=["Describe this image and audio"])],
                image=[Image(content=["https://example.com/image.jpg"])],
                audio=[Audio(content=[f"wav,{sample_audio_base64}"])],
            )

            message = ChatMessage.from_turn(turn)
            assert len(message.content) == 3
            assert isinstance(message.content[0], TextContent)
            assert isinstance(message.content[1], ImageUrlContent)
            assert isinstance(message.content[2], InputAudioContent)

        def test_chat_message_empty_turn(self):
            """Test handling empty turn."""
            turn = Turn()
            with pytest.raises(
                AIPerfError, match="Turn must contain at least one content item"
            ):
                ChatMessage.from_turn(turn)

        def test_chat_message_invalid_audio_format(self):
            """Test handling invalid audio format."""
            turn = Turn(
                audio=[Audio(content=["invalid_format,data"])],
            )
            with pytest.raises(AIPerfError, match="Unsupported audio format"):
                ChatMessage.from_turn(turn)

        def test_chat_message_malformed_audio_content(self):
            """Test handling malformed audio content."""
            turn = Turn(
                audio=[Audio(content=["no_comma_separator"])],
            )
            with pytest.raises(AIPerfError, match="Invalid audio content format"):
                ChatMessage.from_turn(turn)

    class TestMultimodalRequest:
        """Test multimodal request creation and validation."""

        def test_request_creation(self):
            """Test creating multimodal request."""
            message = ChatMessage(
                role=MessageRole.USER,
                content=[TextContent(text="Hello")],
            )

            request = MultimodalChatCompletionsRequest(
                model="gpt-4o-mini",
                messages=[message],
                stream=True,
                max_tokens=1000,
                temperature=0.7,
            )

            assert request.model == "gpt-4o-mini"
            assert len(request.messages) == 1
            assert request.stream is True
            assert request.max_tokens == 1000
            assert request.temperature == 0.7

        def test_request_validation(self):
            """Test request validation."""
            with pytest.raises(ValueError):
                MultimodalChatCompletionsRequest(
                    model="gpt-4o-mini",
                    messages=[],  # Empty messages should fail
                )

        def test_request_parameter_validation(self):
            """Test parameter validation."""
            message = ChatMessage(
                role=MessageRole.USER,
                content=[TextContent(text="Hello")],
            )

            # Test temperature validation
            with pytest.raises(ValueError):
                MultimodalChatCompletionsRequest(
                    model="gpt-4o-mini",
                    messages=[message],
                    temperature=3.0,  # Should be <= 2.0
                )

            # Test max_tokens validation
            with pytest.raises(ValueError):
                MultimodalChatCompletionsRequest(
                    model="gpt-4o-mini",
                    messages=[message],
                    max_tokens=0,  # Should be > 0
                )

    class TestConverter:
        """Test the main converter functionality."""

        @pytest.mark.asyncio
        async def test_text_only_conversion(self, converter, model_endpoint):
            """Test converting text-only content."""
            turn = Turn(
                text=[Text(content=["Hello, world!"])],
            )

            payload = await converter.format_payload(model_endpoint, turn)

            assert payload["model"] == "gpt-4o-mini"
            assert payload["stream"] is True
            assert len(payload["messages"]) == 1
            assert payload["messages"][0]["role"] == "user"
            assert len(payload["messages"][0]["content"]) == 1
            assert payload["messages"][0]["content"][0]["type"] == "text"
            assert payload["messages"][0]["content"][0]["text"] == "Hello, world!"

            # Check extra parameters
            assert payload["temperature"] == 0.7
            assert payload["max_tokens"] == 1000

        @pytest.mark.asyncio
        async def test_multimodal_conversion(
            self, converter, model_endpoint, sample_audio_base64
        ):
            """Test converting multimodal content."""
            turn = Turn(
                text=[Text(content=["Describe this"])],
                image=[Image(content=["https://example.com/image.jpg"])],
                audio=[Audio(content=[f"wav,{sample_audio_base64}"])],
            )

            payload = await converter.format_payload(model_endpoint, turn)

            assert len(payload["messages"][0]["content"]) == 3

            # Check text content
            text_content = payload["messages"][0]["content"][0]
            assert text_content["type"] == "text"
            assert text_content["text"] == "Describe this"

            # Check image content
            image_content = payload["messages"][0]["content"][1]
            assert image_content["type"] == "image_url"
            assert image_content["image_url"]["url"] == "https://example.com/image.jpg"

            # Check audio content
            audio_content = payload["messages"][0]["content"][2]
            assert audio_content["type"] == "input_audio"
            assert audio_content["input_audio"]["format"] == "wav"
            assert audio_content["input_audio"]["data"] == sample_audio_base64

        @pytest.mark.asyncio
        async def test_converter_error_handling(self, converter, model_endpoint):
            """Test converter error handling."""
            turn = Turn()  # Empty turn

            with pytest.raises(
                AIPerfError, match="Failed to format multimodal payload"
            ):
                await converter.format_payload(model_endpoint, turn)

        @pytest.mark.asyncio
        async def test_multiple_content_items(self, converter, model_endpoint):
            """Test handling multiple content items of the same type."""
            turn = Turn(
                text=[Text(content=["First message", "Second message"])],
                image=[
                    Image(
                        content=[
                            "https://example.com/image1.jpg",
                            "https://example.com/image2.jpg",
                        ]
                    )
                ],
            )

            payload = await converter.format_payload(model_endpoint, turn)

            assert len(payload["messages"][0]["content"]) == 4

            # Check that all content is preserved
            content_types = [c["type"] for c in payload["messages"][0]["content"]]
            assert content_types.count("text") == 2
            assert content_types.count("image_url") == 2

        @pytest.mark.asyncio
        async def test_empty_content_filtering(self, converter, model_endpoint):
            """Test that empty content is filtered out."""
            turn = Turn(
                text=[
                    Text(content=["Hello", "", "World"])
                ],  # Empty string should be filtered
                image=[
                    Image(content=["https://example.com/image.jpg", ""])
                ],  # Empty string should be filtered
            )

            payload = await converter.format_payload(model_endpoint, turn)

            # Should only have 3 content items (2 text + 1 image)
            assert len(payload["messages"][0]["content"]) == 3

    class TestValidationMethods:
        """Test validation helper methods."""

        def test_validate_image_content(self, converter):
            """Test image content validation."""
            # Valid URLs
            converter._validate_image_content("https://example.com/image.jpg")
            converter._validate_image_content("http://example.com/image.png")
            converter._validate_image_content(
                "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEA..."
            )

            # Invalid URLs
            with pytest.raises(AIPerfError):
                converter._validate_image_content("invalid-url")

        def test_validate_audio_content(self, converter, sample_audio_base64):
            """Test audio content validation."""
            # Valid audio content
            converter._validate_audio_content(f"wav,{sample_audio_base64}")

            # Invalid format
            with pytest.raises(AIPerfError):
                converter._validate_audio_content("invalid_format,data")

            # Missing comma
            with pytest.raises(AIPerfError):
                converter._validate_audio_content("wav_no_comma")

            # Invalid base64
            with pytest.raises(AIPerfError):
                converter._validate_audio_content("wav,invalid_base64!")

        def test_get_content_statistics(self, converter):
            """Test content statistics calculation."""
            turn = Turn(
                text=[Text(content=["Hello", "World"])],
                image=[Image(content=["image1.jpg"])],
                audio=[Audio(content=["audio1.wav", "audio2.mp3"])],
            )

            stats = converter._get_content_statistics(turn)

            assert stats["text_items"] == 2
            assert stats["image_items"] == 1
            assert stats["audio_items"] == 2

    @pytest.mark.parametrize("audio_format", ["wav", "mp3", "flac", "m4a", "ogg"])
    def test_supported_audio_formats(
        self, converter, audio_format, sample_audio_base64
    ):
        """Test all supported audio formats."""
        turn = Turn(
            audio=[Audio(content=[f"{audio_format},{sample_audio_base64}"])],
        )

        # Should not raise an exception
        message = ChatMessage.from_turn(turn)
        assert len(message.content) == 1
        assert message.content[0].input_audio["format"] == audio_format

    @pytest.mark.parametrize(
        "detail_level", [ImageDetail.LOW, ImageDetail.HIGH, ImageDetail.AUTO]
    )
    def test_image_detail_levels(self, detail_level):
        """Test different image detail levels."""
        content = ImageUrlContent.from_url(
            "https://example.com/image.jpg", detail_level
        )
        assert content.image_url["detail"] == detail_level

    @pytest.mark.parametrize(
        "role", [MessageRole.USER, MessageRole.ASSISTANT, MessageRole.SYSTEM]
    )
    def test_message_roles(self, role):
        """Test different message roles."""
        turn = Turn(
            text=[Text(content=["Hello"])],
            role=role.value,
        )

        message = ChatMessage.from_turn(turn, role)
        assert message.role == role


@pytest.mark.integration
class TestIntegration:
    """Integration tests for the multimodal converter."""

    @pytest.mark.asyncio
    async def test_end_to_end_conversion(self, sample_audio_base64):
        """Test end-to-end conversion flow."""
        # Setup
        converter = OpenAIMultimodalChatCompletionsRequestConverter()
        model_endpoint = ModelEndpointInfo(
            models=ModelListInfo(
                models=[ModelInfo(name="gpt-4o-mini")],
                model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
            ),
            endpoint=EndpointInfo(
                type=EndpointType.OPENAI_MULTIMODAL,
                streaming=True,
                extra={"temperature": 0.8, "max_tokens": 2000},
            ),
        )

        # Create complex multimodal turn
        turn = Turn(
            text=[Text(content=["Please analyze this image and audio file."])],
            image=[Image(content=["https://example.com/complex_image.jpg"])],
            audio=[Audio(content=[f"wav,{sample_audio_base64}"])],
        )

        # Convert
        payload = await converter.format_payload(model_endpoint, turn)

        # Verify structure
        assert "model" in payload
        assert "messages" in payload
        assert "stream" in payload
        assert "temperature" in payload
        assert "max_tokens" in payload

        # Verify content
        message = payload["messages"][0]
        assert message["role"] == "user"
        assert len(message["content"]) == 3

        # Verify the payload can be serialized to JSON
        json_payload = json.dumps(payload)
        assert json_payload is not None

        # Verify the payload can be deserialized back
        deserialized = json.loads(json_payload)
        assert deserialized == payload
