# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import json

import pytest

from aiperf.clients.model_endpoint_info import (
    EndpointInfo,
    ModelEndpointInfo,
    ModelInfo,
    ModelListInfo,
)
from aiperf.clients.openai import OpenAIClientAioHttp
from aiperf.clients.solido import SolidoRequestConverter
from aiperf.common.enums import EndpointType, ModelSelectionStrategy
from aiperf.common.factories import (
    InferenceClientFactory,
    RequestConverterFactory,
    ResponseExtractorFactory,
)
from aiperf.common.models import (
    ParsedResponse,
    RequestRecord,
    SolidoResponseData,
    Text,
    TextResponse,
    Turn,
)
from aiperf.parsers.openai_parsers import OpenAIResponseExtractor


class TestSolidoEndpointType:
    """Test suite for Solido endpoint type implementation."""

    def _create_model_endpoint_info(
        self, endpoint_info: EndpointInfo
    ) -> ModelEndpointInfo:
        """Helper to create a ModelEndpointInfo with required fields."""
        models = ModelListInfo(
            models=[ModelInfo(name="test-model")],
            model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
        )
        return ModelEndpointInfo(models=models, endpoint=endpoint_info)

    def test_solido_endpoint_type_registration(self):
        """Test that the Solido endpoint type is properly registered."""
        from aiperf.common.enums import EndpointType

        # Check that SOLIDO endpoint type exists
        assert hasattr(EndpointType, "SOLIDO")
        assert EndpointType.SOLIDO.info.tag == "solido"
        assert (
            EndpointType.SOLIDO.service_kind.value == "openai"
        )  # Uses OpenAI service kind
        assert EndpointType.SOLIDO.supports_streaming is True
        assert EndpointType.SOLIDO.produces_tokens is True
        assert EndpointType.SOLIDO.endpoint_path == "/rag/api/prompt"
        assert EndpointType.SOLIDO.metrics_title == "Solido RAG Metrics"

    def test_solido_response_data_model(self):
        """Test the SolidoResponseData model."""
        response_data = SolidoResponseData(
            content="This is a test response from Solido RAG.",
            query="What is the weather like?",
            inference_model="meta-llama/Llama-3.1-70B-Instruct",
        )

        assert response_data.content == "This is a test response from Solido RAG."
        assert response_data.query == "What is the weather like?"
        assert response_data.inference_model == "meta-llama/Llama-3.1-70B-Instruct"
        assert response_data.get_text() == "This is a test response from Solido RAG."

    def test_solido_factories_registration(self):
        """Test that Solido components are properly registered in factories."""
        # Test RequestConverterFactory registration
        converter_class = RequestConverterFactory.get_class_from_type(
            EndpointType.SOLIDO
        )
        assert converter_class == SolidoRequestConverter

        # Test InferenceClientFactory registration (uses OpenAI client)
        client_class = InferenceClientFactory.get_class_from_type(EndpointType.SOLIDO)
        assert client_class == OpenAIClientAioHttp

        # Test ResponseExtractorFactory registration (uses OpenAI extractor)
        extractor_class = ResponseExtractorFactory.get_class_from_type(
            EndpointType.SOLIDO
        )
        assert extractor_class == OpenAIResponseExtractor

    @pytest.mark.asyncio
    async def test_solido_request_converter(self):
        """Test the SolidoRequestConverter formats payloads correctly."""
        converter = SolidoRequestConverter()

        # Create test data
        turn = Turn(
            texts=[Text(contents=["What is the capital of France?"])],
            model="custom-model",
        )

        endpoint_info = EndpointInfo(type=EndpointType.SOLIDO)
        model_endpoint = self._create_model_endpoint_info(endpoint_info)

        # Format payload
        payload = await converter.format_payload(model_endpoint, turn)

        # Validate payload structure
        assert "query" in payload
        assert "filters" in payload
        assert "inference_model" in payload

        assert payload["query"] == ["What is the capital of France?"]
        assert payload["filters"] == {"family": "Solido", "tool": "SDE"}
        assert payload["inference_model"] == "custom-model"

    @pytest.mark.asyncio
    async def test_solido_request_converter_with_extras(self):
        """Test the SolidoRequestConverter with extra parameters."""
        converter = SolidoRequestConverter()

        turn = Turn(texts=[Text(contents=["Test query"])])

        endpoint_info = EndpointInfo(
            type=EndpointType.SOLIDO,
            extra=[
                ("filters", {"family": "CustomFamily", "tool": "CustomTool"}),
                ("custom_param", "custom_value"),
            ],
        )
        model_endpoint = self._create_model_endpoint_info(endpoint_info)

        payload = await converter.format_payload(model_endpoint, turn)

        # Check that custom filters override defaults
        assert payload["filters"]["family"] == "CustomFamily"
        assert payload["filters"]["tool"] == "CustomTool"
        assert payload["custom_param"] == "custom_value"

    @pytest.mark.asyncio
    async def test_solido_response_extractor(self):
        """Test the SolidoResponseExtractor parses responses correctly."""
        endpoint_info = EndpointInfo(type=EndpointType.SOLIDO)
        model_endpoint = ModelEndpointInfo(
            models=ModelListInfo(
                models=[ModelInfo(name="test-model")],
                model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
            ),
            endpoint=endpoint_info,
        )

        extractor = OpenAIResponseExtractor(model_endpoint)

        # Create test response
        response_json = {
            "content": "Paris is the capital of France.",
            "query": "What is the capital of France?",
            "inference_model": "meta-llama/Llama-3.1-70B-Instruct",
        }

        text_response = TextResponse(
            perf_ns=1000000,
            content_type="application/json",
            text=json.dumps(response_json),
        )

        record = RequestRecord(responses=[text_response])

        # Extract response data
        parsed_responses = await extractor.extract_response_data(record)

        assert len(parsed_responses) == 1
        parsed_response = parsed_responses[0]
        assert isinstance(parsed_response, ParsedResponse)
        assert isinstance(parsed_response.data, SolidoResponseData)
        assert parsed_response.data.content == "Paris is the capital of France."
        assert parsed_response.data.query == "What is the capital of France?"
        assert (
            parsed_response.data.inference_model == "meta-llama/Llama-3.1-70B-Instruct"
        )

    def test_solido_uses_openai_infrastructure(self):
        """Test that Solido reuses OpenAI client infrastructure."""
        endpoint_info = EndpointInfo(
            type=EndpointType.SOLIDO, base_url="localhost:8080"
        )
        model_endpoint = self._create_model_endpoint_info(endpoint_info)

        # Test that URL generation works correctly with Solido endpoint
        expected_url = "localhost:8080/rag/api/prompt"
        assert model_endpoint.url == expected_url

        # Test that Solido uses OpenAI service kind
        assert EndpointType.SOLIDO.service_kind == EndpointType.CHAT.service_kind

    @pytest.mark.asyncio
    async def test_solido_response_extractor_streaming(self):
        """Test the SolidoResponseExtractor with streaming responses."""
        endpoint_info = EndpointInfo(type=EndpointType.SOLIDO)
        model_endpoint = self._create_model_endpoint_info(endpoint_info)

        extractor = OpenAIResponseExtractor(model_endpoint)

        # Test streaming response with delta content
        response_json = {
            "delta": {"content": "Streaming response chunk"},
            "query": "Test query",
            "inference_model": "test-model",
        }

        text_response = TextResponse(
            perf_ns=1000000,
            content_type="application/json",
            text=json.dumps(response_json),
        )

        record = RequestRecord(responses=[text_response])
        parsed_responses = await extractor.extract_response_data(record)

        assert len(parsed_responses) == 1
        parsed_response = parsed_responses[0]
        assert isinstance(parsed_response.data, SolidoResponseData)
        assert parsed_response.data.content == "Streaming response chunk"

    @pytest.mark.asyncio
    async def test_solido_request_converter_empty_query(self):
        """Test SolidoRequestConverter handles empty queries gracefully."""
        converter = SolidoRequestConverter()

        turn = Turn(texts=[])  # Empty texts

        endpoint_info = EndpointInfo(type=EndpointType.SOLIDO)
        model_endpoint = self._create_model_endpoint_info(endpoint_info)

        payload = await converter.format_payload(model_endpoint, turn)

        # Should add empty query with warning
        assert payload["query"] == [""]
