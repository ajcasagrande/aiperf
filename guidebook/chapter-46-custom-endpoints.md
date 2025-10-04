<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 46: Custom Endpoints

## Overview

This chapter covers adding support for new API endpoints in AIPerf. Learn how to create request converters, response extractors, and integrate new endpoint types with the benchmarking system.

## Table of Contents

- [Endpoint Architecture](#endpoint-architecture)
- [Request Converters](#request-converters)
- [Response Extractors](#response-extractors)
- [Streaming Support](#streaming-support)
- [Error Handling](#error-handling)
- [Testing](#testing)
- [Complete Examples](#complete-examples)

---

## Endpoint Architecture

### Endpoint Processing Flow

```
┌────────────────────────────────────────────────────────────┐
│                  Endpoint Processing Flow                   │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Turn (from Dataset)                                        │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────────┐                                          │
│  │  Request     │ ← Convert Turn to API request            │
│  │  Converter   │                                          │
│  └───────┬──────┘                                          │
│          │                                                  │
│          ▼                                                  │
│  ┌──────────────┐                                          │
│  │  HTTP Client │ ← Send request to endpoint               │
│  └───────┬──────┘                                          │
│          │                                                  │
│          ▼                                                  │
│  ┌──────────────┐                                          │
│  │  Response    │ ← Parse and extract data                 │
│  │  Extractor   │                                          │
│  └───────┬──────┘                                          │
│          │                                                  │
│          ▼                                                  │
│  ParsedResponseRecord                                       │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### Key Components

**Location**: `/home/anthony/nvidia/projects/aiperf/aiperf/clients/`

- **Request Converter**: Format Turn → API request
- **Response Extractor**: Parse API response → ParsedResponseRecord
- **Inference Client**: HTTP communication
- **OpenAI Parsers**: Parse OpenAI-compatible responses

---

## Request Converters

### Request Converter Protocol

```python
from typing import Any, Protocol
from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.models import Turn


class RequestConverterProtocol(Protocol):
    """Protocol for request converters"""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn
    ) -> dict[str, Any]:
        """Convert Turn to API request payload"""
        ...
```

### Basic Request Converter

**Example**: Custom chat endpoint

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/clients/openai/openai_chat.py`

```python
from aiperf.common.factories import RequestConverterFactory
from aiperf.common.enums import EndpointType
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.models import Turn
from typing import Any


@RequestConverterFactory.register(EndpointType.CUSTOM_CHAT)
class CustomChatRequestConverter(AIPerfLoggerMixin):
    """Convert Turn to custom chat API format"""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn
    ) -> dict[str, Any]:
        """Format custom chat request"""

        # Extract text content
        messages = []
        for text in turn.texts:
            for content in text.contents:
                messages.append({
                    "role": turn.role or "user",
                    "content": content
                })

        # Build payload
        payload = {
            "messages": messages,
            "model": turn.model or model_endpoint.primary_model_name,
            "stream": model_endpoint.endpoint.streaming
        }

        # Add optional parameters
        if turn.max_tokens is not None:
            payload["max_tokens"] = turn.max_tokens

        # Add endpoint-specific extras
        if model_endpoint.endpoint.extra:
            payload.update(model_endpoint.endpoint.extra)

        self.debug(lambda: f"Formatted payload: {payload}")
        return payload
```

### Advanced Request Converter

**Example**: Multi-modal support

```python
from aiperf.common.factories import RequestConverterFactory
from aiperf.common.enums import EndpointType
from aiperf.common.mixins import AIPerfLoggerMixin


@RequestConverterFactory.register(EndpointType.CUSTOM_MULTIMODAL)
class CustomMultiModalRequestConverter(AIPerfLoggerMixin):
    """Convert Turn with text, images, and audio"""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn
    ) -> dict[str, Any]:
        """Format multimodal request"""

        content = []

        # Add text
        for text in turn.texts:
            for text_content in text.contents:
                content.append({
                    "type": "text",
                    "text": text_content
                })

        # Add images
        for image in turn.images:
            for image_content in image.contents:
                content.append({
                    "type": "image",
                    "image": {
                        "url": image_content
                    }
                })

        # Add audio
        for audio in turn.audios:
            for audio_content in audio.contents:
                # Parse "format,data" pattern
                if "," in audio_content:
                    format_type, data = audio_content.split(",", 1)
                    content.append({
                        "type": "audio",
                        "audio": {
                            "format": format_type,
                            "data": data
                        }
                    })

        payload = {
            "model": turn.model or model_endpoint.primary_model_name,
            "messages": [{
                "role": turn.role or "user",
                "content": content
            }],
            "stream": model_endpoint.endpoint.streaming
        }

        # Add extras
        if turn.max_tokens is not None:
            payload["max_tokens"] = turn.max_tokens

        if model_endpoint.endpoint.extra:
            payload.update(model_endpoint.endpoint.extra)

        return payload
```

---

## Response Extractors

### Response Extractor Protocol

```python
from typing import Protocol
from aiperf.common.models import ParsedResponseRecord
from aiperf.clients.model_endpoint_info import ModelEndpointInfo


class ResponseExtractorProtocol(Protocol):
    """Protocol for response extractors"""

    async def extract(
        self,
        model_endpoint: ModelEndpointInfo,
        response: Any
    ) -> ParsedResponseRecord:
        """Extract data from API response"""
        ...
```

### Basic Response Extractor

**Example**: Extract from JSON response

```python
from aiperf.common.factories import ResponseExtractorFactory
from aiperf.common.enums import EndpointType
from aiperf.common.models import ParsedResponseRecord
from aiperf.clients.model_endpoint_info import ModelEndpointInfo
import time


@ResponseExtractorFactory.register(EndpointType.CUSTOM_CHAT)
class CustomChatResponseExtractor:
    """Extract response data for custom chat endpoint"""

    def __init__(self, model_endpoint: ModelEndpointInfo):
        self.model_endpoint = model_endpoint

    async def extract(
        self,
        response: dict
    ) -> ParsedResponseRecord:
        """Extract response data"""

        # Extract message content
        message = response.get("message", {})
        content = message.get("content", "")

        # Extract token counts (if provided)
        usage = response.get("usage", {})
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")

        # Create record
        record = ParsedResponseRecord(
            response_text=content,
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            valid=True,
            error_message=None
        )

        return record
```

### Streaming Response Extractor

**Example**: Handle SSE streaming

```python
from aiperf.common.factories import ResponseExtractorFactory
from aiperf.common.enums import EndpointType
from aiperf.common.models import ParsedResponseRecord
import json


@ResponseExtractorFactory.register(EndpointType.CUSTOM_STREAMING)
class CustomStreamingResponseExtractor:
    """Extract streaming response with timing data"""

    def __init__(self, model_endpoint: ModelEndpointInfo):
        self.model_endpoint = model_endpoint

    async def extract(
        self,
        chunks: list[dict]
    ) -> ParsedResponseRecord:
        """Extract data from streaming chunks"""

        # Accumulate text
        full_text = ""
        inter_token_times = []
        last_time = None

        for chunk in chunks:
            delta = chunk.get("delta", {})
            content = delta.get("content", "")

            if content:
                full_text += content

                # Track inter-token timing
                current_time = chunk.get("timestamp", time.time())
                if last_time is not None:
                    inter_token_times.append(current_time - last_time)
                last_time = current_time

        # Extract final token counts
        last_chunk = chunks[-1] if chunks else {}
        usage = last_chunk.get("usage", {})

        record = ParsedResponseRecord(
            response_text=full_text,
            input_token_count=usage.get("prompt_tokens"),
            output_token_count=usage.get("completion_tokens"),
            inter_token_times=inter_token_times,
            valid=True,
            error_message=None
        )

        return record
```

---

## Streaming Support

### Streaming Pattern

```python
import aiohttp
import json
from typing import AsyncIterator


class StreamingResponseHandler:
    """Handle Server-Sent Events streaming"""

    @staticmethod
    async def parse_sse_stream(
        response: aiohttp.ClientResponse
    ) -> AsyncIterator[dict]:
        """Parse SSE stream into chunks"""

        async for line in response.content:
            line = line.decode('utf-8').strip()

            # Skip empty lines and comments
            if not line or line.startswith(':'):
                continue

            # Parse data field
            if line.startswith('data: '):
                data = line[6:]  # Remove 'data: ' prefix

                # Check for stream end
                if data == '[DONE]':
                    break

                try:
                    # Parse JSON chunk
                    chunk = json.loads(data)
                    yield chunk
                except json.JSONDecodeError:
                    continue
```

### Streaming Inference Client

```python
from aiperf.clients.http.aiohttp_client import AIOHttpClient


class CustomStreamingClient:
    """Client for streaming endpoints"""

    def __init__(self, base_url: str):
        self.client = AIOHttpClient(base_url)

    async def send_streaming_request(
        self,
        payload: dict
    ) -> list[dict]:
        """Send streaming request and collect chunks"""

        chunks = []

        async with self.client.post_stream(
            "/v1/chat/completions",
            json=payload
        ) as response:
            async for chunk in StreamingResponseHandler.parse_sse_stream(response):
                # Add timestamp
                chunk["timestamp"] = time.time()
                chunks.append(chunk)

        return chunks
```

---

## Error Handling

### Error Response Handling

```python
from aiperf.common.exceptions import InferenceClientError


class ErrorHandlingExtractor:
    """Extract error information from responses"""

    async def extract_with_error_handling(
        self,
        response: dict | None
    ) -> ParsedResponseRecord:
        """Extract with comprehensive error handling"""

        # Handle null response
        if response is None:
            return ParsedResponseRecord(
                valid=False,
                error_message="No response received"
            )

        # Check for error field
        if "error" in response:
            error = response["error"]
            error_message = error.get("message", "Unknown error")
            error_code = error.get("code", "unknown")

            return ParsedResponseRecord(
                valid=False,
                error_message=f"[{error_code}] {error_message}"
            )

        # Validate required fields
        if "message" not in response:
            return ParsedResponseRecord(
                valid=False,
                error_message="Missing 'message' field in response"
            )

        # Extract successful response
        try:
            return await self.extract(response)
        except Exception as e:
            return ParsedResponseRecord(
                valid=False,
                error_message=f"Extraction error: {e}"
            )
```

---

## Testing

### Unit Tests

```python
import pytest
from aiperf.common.models import Turn, Text


@pytest.mark.asyncio
async def test_custom_request_converter():
    """Test request converter"""
    converter = CustomChatRequestConverter()

    turn = Turn(
        texts=[Text(contents=["Hello, world!"])],
        role="user"
    )

    model_endpoint = ModelEndpointInfo(
        primary_model_name="test-model",
        endpoint=EndpointConfig(
            url="http://localhost:8000",
            type="custom_chat",
            streaming=False
        )
    )

    payload = await converter.format_payload(model_endpoint, turn)

    assert "messages" in payload
    assert payload["messages"][0]["content"] == "Hello, world!"
    assert payload["model"] == "test-model"
    assert payload["stream"] is False


@pytest.mark.asyncio
async def test_custom_response_extractor():
    """Test response extractor"""
    extractor = CustomChatResponseExtractor(model_endpoint)

    response = {
        "message": {
            "content": "Hello back!"
        },
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5
        }
    }

    record = await extractor.extract(response)

    assert record.valid
    assert record.response_text == "Hello back!"
    assert record.input_token_count == 10
    assert record.output_token_count == 5
```

### Integration Tests

```python
@pytest.mark.integration
async def test_custom_endpoint_integration(mock_server):
    """Test full endpoint integration"""
    from aiperf.cli_runner import run_system_controller

    endpoint_config = EndpointConfig(
        model_names=["test-model"],
        url=mock_server.url,
        type="custom_chat",
        streaming=False
    )

    loadgen_config = LoadGeneratorConfig(
        request_count=10,
        concurrency=1
    )

    user_config = UserConfig(
        endpoint=endpoint_config,
        loadgen=loadgen_config
    )

    # Run benchmark
    results = run_system_controller(user_config, service_config)

    # Verify results
    assert results.total_requests == 10
    assert results.error_count == 0
```

---

## Complete Examples

### Example 1: Embeddings Endpoint

```python
from aiperf.common.factories import (
    RequestConverterFactory,
    ResponseExtractorFactory
)
from aiperf.common.enums import EndpointType


@RequestConverterFactory.register(EndpointType.CUSTOM_EMBEDDINGS)
class EmbeddingsRequestConverter:
    """Convert to embeddings request"""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn
    ) -> dict:
        # Extract text
        text = turn.texts[0].contents[0] if turn.texts else ""

        return {
            "model": turn.model or model_endpoint.primary_model_name,
            "input": text,
            "encoding_format": "float"
        }


@ResponseExtractorFactory.register(EndpointType.CUSTOM_EMBEDDINGS)
class EmbeddingsResponseExtractor:
    """Extract embeddings response"""

    def __init__(self, model_endpoint: ModelEndpointInfo):
        self.model_endpoint = model_endpoint

    async def extract(self, response: dict) -> ParsedResponseRecord:
        # Extract embedding
        data = response.get("data", [])
        embedding = data[0].get("embedding", []) if data else []

        # Extract usage
        usage = response.get("usage", {})

        return ParsedResponseRecord(
            response_text=f"Embedding (dim={len(embedding)})",
            input_token_count=usage.get("prompt_tokens"),
            output_token_count=0,  # No output for embeddings
            valid=True
        )
```

### Example 2: Custom Authentication

```python
from aiperf.clients.http.aiohttp_client import AIOHttpClient


class AuthenticatedRequestConverter:
    """Request converter with authentication"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn
    ) -> dict:
        payload = {
            # ... standard payload ...
        }

        # Add authentication headers
        payload["_headers"] = {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Version": "2024-01"
        }

        return payload
```

---

## Key Takeaways

1. **Request Converters**: Transform Turn → API request
2. **Response Extractors**: Parse API response → ParsedResponseRecord
3. **Factory Registration**: Register with endpoint type
4. **Streaming Support**: Handle SSE and chunked responses
5. **Error Handling**: Gracefully handle API errors
6. **Testing**: Unit and integration tests required
7. **Multi-Modal**: Support text, images, audio

---

## Navigation

- [Previous Chapter: Chapter 45 - Custom Dataset Development](chapter-45-custom-dataset-development.md)
- [Next Chapter: Chapter 47 - Extending AIPerf](chapter-47-extending-aiperf.md)
- [Return to Index](INDEX.md)

---

**Document Information**
- **File**: `/home/anthony/nvidia/projects/aiperf/guidebook/chapter-46-custom-endpoints.md`
- **Purpose**: Guide to adding custom endpoint support
- **Target Audience**: Developers adding API endpoints
- **Related Files**:
  - `/home/anthony/nvidia/projects/aiperf/aiperf/clients/openai/`
  - `/home/anthony/nvidia/projects/aiperf/aiperf/common/factories.py`
