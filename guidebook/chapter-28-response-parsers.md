<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 28: Response Parsers

## Navigation
- Previous: [Chapter 27: Request Converters](chapter-27-request-converters.md)
- Next: [Chapter 29: Configuration Architecture](chapter-29-configuration-architecture.md)
- [Table of Contents](README.md)

## Overview

Response parsers extract structured data from raw API responses, handling multiple response formats (JSON, SSE), object types (chat completions, embeddings, rankings), and content types (text, reasoning, embeddings). AIPerf's parsing architecture uses factory patterns and polymorphism to provide consistent data extraction across different endpoint types.

This chapter explores response parsing, object type detection, content extraction, and error handling.

## Architecture

### Response Parsing Flow

```
RequestRecord (Raw Responses)
    ↓
ResponseExtractor
    ↓
ParsedResponse List
    ↓
Metrics & Analysis
```

**RequestRecord**: Contains raw HTTP responses (TextResponse or SSEMessage)
**ResponseExtractor**: Extracts and parses response data
**ParsedResponse**: Structured response data with timestamps
**Metrics**: Compute performance metrics from parsed data

### Factory Registration

```python
from aiperf.common.factories import ResponseExtractorFactory
from aiperf.common.enums import EndpointType

@ResponseExtractorFactory.register_all(
    EndpointType.CHAT,
    EndpointType.COMPLETIONS,
    EndpointType.EMBEDDINGS,
    EndpointType.RANKINGS,
    EndpointType.RESPONSES,
)
class OpenAIResponseExtractor(AIPerfLoggerMixin):
    """Extractor for OpenAI responses."""
    pass
```

## OpenAI Response Extractor

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/parsers/openai_parsers.py`

```python
@ResponseExtractorFactory.register_all(
    EndpointType.CHAT,
    EndpointType.COMPLETIONS,
    EndpointType.EMBEDDINGS,
    EndpointType.RANKINGS,
    EndpointType.RESPONSES,
)
class OpenAIResponseExtractor(AIPerfLoggerMixin):
    """Extractor for OpenAI responses."""

    def __init__(self, model_endpoint: ModelEndpointInfo) -> None:
        """Create a new response extractor based on the provided configuration."""
        super().__init__()
        self.model_endpoint = model_endpoint

    async def extract_response_data(
        self, record: RequestRecord
    ) -> list[ParsedResponse]:
        """Extract the text from a server response message."""
        results = []
        for response in record.responses:
            response_data = self._parse_response(response)
            if not response_data:
                continue
            results.append(response_data)
        return results

    def _parse_response(
        self, response: InferenceServerResponse
    ) -> ParsedResponse | None:
        """Parse a response into a ParsedResponse object."""
        parsed_data = None
        # Note, this uses Python 3.10+ pattern matching, no new objects are created
        match response:
            case TextResponse():
                parsed_data = self._parse_raw_text(response.text)
            case SSEMessage():
                parsed_data = self._parse_raw_text(response.extract_data_content())
            case _:
                self.warning(f"Unsupported response type: {type(response)}")
        if not parsed_data:
            return None

        return ParsedResponse(
            perf_ns=response.perf_ns,
            data=parsed_data,
        )

    def _parse_raw_text(self, raw_text: str) -> BaseResponseData | None:
        """Parse the raw text of the response using the appropriate parser from OpenAIObjectParserFactory.

        Returns:
            ParsedResponse | None: The parsed response, or None if the response is not a valid or supported OpenAI object.
        """
        if raw_text in ("", None, "[DONE]"):
            return None

        try:
            json_str = load_json_str(raw_text)
        except orjson.JSONDecodeError as e:
            self.warning(f"Invalid JSON: {raw_text} - {e!r}")
            return None

        if "object" in json_str:
            try:
                object_type = OpenAIObjectType(json_str["object"])
            except ValueError:
                self.warning(
                    f"Unsupported OpenAI object type received: {json_str['object']}"
                )
                return None
        else:
            object_type = self._infer_object_type(json_str)
            if object_type is None:
                return None

        try:
            parser = OpenAIObjectParserFactory.get_or_create_instance(object_type)
            return parser.parse(json_str)
        except FactoryCreationError:
            self.warning(f"No parser found for object type: {object_type!r}")
            return None

    def _infer_object_type(self, json_obj: dict[str, Any]) -> OpenAIObjectType | None:
        """Infer the object type from the JSON structure for responses without explicit 'object' field."""
        if "rankings" in json_obj:
            return OpenAIObjectType.RANKINGS

        self.warning(f"Could not infer object type from response: {json_obj}")
        return None
```

### Key Features

1. **Type Detection**: Pattern matching for TextResponse vs SSEMessage
2. **JSON Parsing**: Safe JSON deserialization with error handling
3. **Object Type Detection**: Explicit or inferred object types
4. **Parser Factory**: Dynamic parser selection based on object type
5. **Timestamp Preservation**: Maintains timing information

## Response Types

### TextResponse

Non-streaming HTTP responses:

```python
@dataclass
class TextResponse:
    perf_ns: int              # Response timestamp
    content_type: str         # MIME type
    text: str                 # Response body

# Example:
TextResponse(
    perf_ns=1234567890123456789,
    content_type="application/json",
    text='{"id":"chatcmpl-123","object":"chat.completion","choices":[...]}'
)
```

### SSEMessage

Streaming responses:

```python
@dataclass
class SSEMessage:
    perf_ns: int                 # First byte timestamp
    packets: list[SSEField]      # Parsed SSE fields

    def extract_data_content(self) -> str:
        """Extract the concatenated content of all 'data' fields."""
        data_fields = [
            packet.value
            for packet in self.packets
            if packet.name == SSEFieldType.DATA and packet.value is not None
        ]
        return "\n".join(data_fields)

# Example:
SSEMessage(
    perf_ns=1234567890123456789,
    packets=[
        SSEField(name="data", value='{"id":"chatcmpl-123","object":"chat.completion.chunk",...}')
    ]
)
```

### ParsedResponse

Extracted structured data:

```python
@dataclass
class ParsedResponse:
    perf_ns: int                    # Response timestamp
    data: BaseResponseData          # Parsed content
```

## OpenAI Object Types

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/enums/openai_enums.py`

```python
class OpenAIObjectType(CaseInsensitiveStrEnum):
    """OpenAI API object types."""

    CHAT_COMPLETION = "chat.completion"
    CHAT_COMPLETION_CHUNK = "chat.completion.chunk"
    COMPLETION = "completion"
    TEXT_COMPLETION = "text_completion"
    EMBEDDING = "embedding"
    LIST = "list"
    RANKINGS = "rankings"
    RESPONSE = "response"
```

### Object Type Detection

**Explicit** (preferred):
```json
{
    "object": "chat.completion",
    "id": "chatcmpl-123",
    ...
}
```

**Inferred** (fallback):
```json
{
    "rankings": [
        {"index": 0, "score": 0.95}
    ]
}
```

## Response Data Types

### TextResponseData

Simple text responses:

```python
@dataclass
class TextResponseData(BaseResponseData):
    text: str | None

# Example:
TextResponseData(text="Hello, world!")
```

### ReasoningResponseData

Responses with reasoning content:

```python
@dataclass
class ReasoningResponseData(BaseResponseData):
    content: str | None          # Generated text
    reasoning: str | None        # Reasoning process

# Example:
ReasoningResponseData(
    content="The answer is 42.",
    reasoning="I calculated this by analyzing the question..."
)
```

### EmbeddingResponseData

Vector embeddings:

```python
@dataclass
class EmbeddingResponseData(BaseResponseData):
    embeddings: list[list[float]]

# Example:
EmbeddingResponseData(
    embeddings=[
        [0.0023, -0.009, 0.015, ...],  # 1536 dimensions
    ]
)
```

### RankingsResponseData

Ranking results:

```python
@dataclass
class RankingsResponseData(BaseResponseData):
    rankings: list[dict[str, Any]]

# Example:
RankingsResponseData(
    rankings=[
        {"index": 0, "score": 0.95},
        {"index": 2, "score": 0.82},
        {"index": 1, "score": 0.71}
    ]
)
```

## Object Parsers

### ChatCompletionParser

**Non-Streaming**:

```python
@OpenAIObjectParserFactory.register(OpenAIObjectType.CHAT_COMPLETION)
class ChatCompletionParser(OpenAIObjectParserProtocol):
    """Parser for ChatCompletion objects."""

    def parse(self, obj: dict[str, Any]) -> BaseResponseData | None:
        """Parse a ChatCompletion into a ResponseData object."""
        return _parse_chat_common(obj.get("choices", [{}])[0].get("message", {}))

def _parse_chat_common(sub_obj: dict[str, Any]) -> BaseResponseData | None:
    """Parse the common ChatCompletion and ChatCompletionChunk objects into a ResponseData object."""
    content = sub_obj.get("content")
    reasoning = sub_obj.get("reasoning_content") or sub_obj.get("reasoning")
    if not content and not reasoning:
        return None
    if not reasoning:
        return _make_text_response_data(content)
    return ReasoningResponseData(
        content=content,
        reasoning=reasoning,
    )
```

**Input**:
```json
{
    "object": "chat.completion",
    "choices": [{
        "message": {
            "role": "assistant",
            "content": "Hello, how can I help?"
        }
    }]
}
```

**Output**:
```python
TextResponseData(text="Hello, how can I help?")
```

### ChatCompletionChunkParser

**Streaming**:

```python
@OpenAIObjectParserFactory.register(OpenAIObjectType.CHAT_COMPLETION_CHUNK)
class ChatCompletionChunkParser(OpenAIObjectParserProtocol):
    """Parser for ChatCompletionChunk objects."""

    def parse(self, obj: dict[str, Any]) -> BaseResponseData | None:
        """Parse a ChatCompletionChunk into a ResponseData object."""
        return _parse_chat_common(obj.get("choices", [{}])[0].get("delta", {}))
```

**Input**:
```json
{
    "object": "chat.completion.chunk",
    "choices": [{
        "delta": {
            "content": "Hello"
        }
    }]
}
```

**Output**:
```python
TextResponseData(text="Hello")
```

### CompletionParser

```python
@OpenAIObjectParserFactory.register(OpenAIObjectType.COMPLETION)
class CompletionParser(OpenAIObjectParserProtocol):
    """Parser for Completion objects."""

    def parse(self, obj: dict[str, Any]) -> BaseResponseData | None:
        """Parse a Completion object."""
        return _make_text_response_data(obj.get("choices", [{}])[0].get("text"))
```

**Input**:
```json
{
    "object": "completion",
    "choices": [{
        "text": "Once upon a time..."
    }]
}
```

**Output**:
```python
TextResponseData(text="Once upon a time...")
```

### ListParser (Embeddings)

```python
@OpenAIObjectParserFactory.register(OpenAIObjectType.LIST)
class ListParser(OpenAIObjectParserProtocol):
    """Parser for List objects."""

    def parse(self, obj: dict[str, Any]) -> BaseResponseData | None:
        """Parse a List object."""
        data = obj.get("data", [])
        if all(
            isinstance(item, dict) and item.get("object") == OpenAIObjectType.EMBEDDING
            for item in data
        ):
            return _make_embedding_response_data(data)
        else:
            raise ValueError(f"Received invalid list in response: {obj}")

def _make_embedding_response_data(
    data: list[dict[str, Any]],
) -> EmbeddingResponseData | None:
    """Make an EmbeddingResponseData object from a list of embedding dictionaries."""
    if not data:
        return None

    embeddings = []
    for item in data:
        embedding = item.get("embedding", [])
        if embedding:
            embeddings.append(embedding)

    return EmbeddingResponseData(embeddings=embeddings) if embeddings else None
```

**Input**:
```json
{
    "object": "list",
    "data": [
        {
            "object": "embedding",
            "embedding": [0.0023, -0.009, 0.015, ...],
            "index": 0
        }
    ]
}
```

**Output**:
```python
EmbeddingResponseData(
    embeddings=[[0.0023, -0.009, 0.015, ...]]
)
```

### RankingsParser

```python
@OpenAIObjectParserFactory.register(OpenAIObjectType.RANKINGS)
class RankingsParser(OpenAIObjectParserProtocol):
    """Parser for Rankings objects."""

    def parse(self, obj: dict[str, Any]) -> BaseResponseData | None:
        """Parse a Rankings object."""
        rankings = obj.get("rankings", [])
        if not rankings:
            return None
        return RankingsResponseData(rankings=rankings)
```

**Input**:
```json
{
    "rankings": [
        {"index": 0, "score": 0.95},
        {"index": 2, "score": 0.82},
        {"index": 1, "score": 0.71}
    ]
}
```

**Output**:
```python
RankingsResponseData(
    rankings=[
        {"index": 0, "score": 0.95},
        {"index": 2, "score": 0.82},
        {"index": 1, "score": 0.71}
    ]
)
```

## Error Handling

### JSON Parsing Errors

```python
try:
    json_str = load_json_str(raw_text)
except orjson.JSONDecodeError as e:
    self.warning(f"Invalid JSON: {raw_text} - {e!r}")
    return None
```

**Handling**: Log warning and skip malformed responses

### Unsupported Object Types

```python
try:
    object_type = OpenAIObjectType(json_str["object"])
except ValueError:
    self.warning(
        f"Unsupported OpenAI object type received: {json_str['object']}"
    )
    return None
```

**Handling**: Log warning for unknown object types

### Missing Parsers

```python
try:
    parser = OpenAIObjectParserFactory.get_or_create_instance(object_type)
    return parser.parse(json_str)
except FactoryCreationError:
    self.warning(f"No parser found for object type: {object_type!r}")
    return None
```

**Handling**: Log warning if no parser registered

### Empty or Done Messages

```python
if raw_text in ("", None, "[DONE]"):
    return None
```

**Handling**: Silently skip empty messages and stream terminators

## Usage Examples

### Parsing Non-Streaming Response

```python
extractor = OpenAIResponseExtractor(model_endpoint)

# Request record with text response
record = RequestRecord(
    responses=[
        TextResponse(
            perf_ns=1234567890123456789,
            content_type="application/json",
            text='{"id":"chatcmpl-123","object":"chat.completion","choices":[{"message":{"content":"Hello!"}}]}'
        )
    ]
)

# Extract parsed responses
parsed_responses = await extractor.extract_response_data(record)

# Access data
for parsed in parsed_responses:
    print(f"Timestamp: {parsed.perf_ns}")
    print(f"Content: {parsed.data.text}")
```

### Parsing Streaming Response

```python
# Request record with SSE messages
record = RequestRecord(
    responses=[
        SSEMessage(
            perf_ns=1234567890123456789,
            packets=[
                SSEField(name="data", value='{"object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello"}}]}')
            ]
        ),
        SSEMessage(
            perf_ns=1234567890223456789,
            packets=[
                SSEField(name="data", value='{"object":"chat.completion.chunk","choices":[{"delta":{"content":" world"}}]}')
            ]
        ),
    ]
)

# Extract parsed responses
parsed_responses = await extractor.extract_response_data(record)

# Reconstruct full text
full_text = "".join(parsed.data.text for parsed in parsed_responses if parsed.data.text)
print(f"Full response: {full_text}")  # "Hello world"
```

### Token Counting

```python
# Count output tokens from parsed responses
output_tokens = sum(
    len(parsed.data.text.split()) if parsed.data.text else 0
    for parsed in parsed_responses
)
print(f"Output tokens: {output_tokens}")
```

## Custom Response Parsers

### Creating a Custom Extractor

```python
from aiperf.common.factories import ResponseExtractorFactory
from aiperf.common.enums import EndpointType

@ResponseExtractorFactory.register(EndpointType.CUSTOM)
class CustomResponseExtractor(AIPerfLoggerMixin):
    """Custom response extractor for a specific API."""

    def __init__(self, model_endpoint: ModelEndpointInfo) -> None:
        super().__init__()
        self.model_endpoint = model_endpoint

    async def extract_response_data(
        self, record: RequestRecord
    ) -> list[ParsedResponse]:
        """Extract custom response data."""
        results = []

        for response in record.responses:
            # Extract text based on response type
            if isinstance(response, TextResponse):
                text = response.text
            elif isinstance(response, SSEMessage):
                text = response.extract_data_content()
            else:
                continue

            # Parse custom format
            data = self._parse_custom_format(text)
            if data:
                results.append(
                    ParsedResponse(
                        perf_ns=response.perf_ns,
                        data=data,
                    )
                )

        return results

    def _parse_custom_format(self, text: str) -> BaseResponseData | None:
        """Parse custom API response format."""
        try:
            json_obj = json.loads(text)

            # Extract text from custom format
            content = json_obj.get("result", {}).get("text")
            if content:
                return TextResponseData(text=content)

        except json.JSONDecodeError:
            self.warning(f"Invalid JSON: {text}")

        return None
```

## Testing

### Unit Testing Parsers

```python
import pytest
from aiperf.parsers.openai_parsers import ChatCompletionParser

def test_chat_completion_parser():
    """Test ChatCompletion parsing."""
    parser = ChatCompletionParser()

    response = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": "Hello, world!"
            }
        }]
    }

    result = parser.parse(response)

    assert isinstance(result, TextResponseData)
    assert result.text == "Hello, world!"

def test_chat_completion_chunk_parser():
    """Test ChatCompletionChunk parsing."""
    parser = ChatCompletionChunkParser()

    response = {
        "object": "chat.completion.chunk",
        "choices": [{
            "delta": {
                "content": "Hello"
            }
        }]
    }

    result = parser.parse(response)

    assert isinstance(result, TextResponseData)
    assert result.text == "Hello"
```

## Performance Considerations

### Lazy Parsing

```python
# Good: Parse only when needed
def _parse_response(self, response):
    if not response:
        return None

    parsed_data = self._parse_raw_text(response.text)
    if not parsed_data:
        return None

    return ParsedResponse(perf_ns=response.perf_ns, data=parsed_data)

# Avoid: Parsing everything upfront
def _parse_all_responses(self, responses):
    return [self._parse_response(r) for r in responses]  # May have nulls
```

### JSON Library Choice

```python
# Fast: orjson for performance
import orjson
json_str = orjson.loads(raw_text)

# Standard: json module for compatibility
import json
json_str = json.loads(raw_text)
```

**orjson benefits**:
- 2-3x faster than standard json
- Lower memory usage
- Better for benchmarking

## Key Takeaways

1. **Factory Pattern**: Dynamic parser selection based on object type

2. **Type Safety**: Structured response data types with clear semantics

3. **Error Resilience**: Graceful handling of malformed responses

4. **Timestamp Preservation**: Maintains timing information through parsing

5. **Streaming Support**: Handles both JSON and SSE responses

6. **Object Detection**: Explicit and inferred object type identification

7. **Extensible**: Easy to add custom parsers for new formats

8. **Performance**: Optimized parsing with lazy evaluation

9. **Testing**: Straightforward unit testing with mock responses

10. **Multimodal**: Supports text, reasoning, embeddings, and rankings

## What's Next

- **Chapter 29: Configuration Architecture** - Learn how AIPerf's configuration system works
- **Chapter 21: Record Metrics** - See how parsed responses feed into metrics

---

**Remember**: Response parsing transforms raw API responses into structured data suitable for metrics computation. Robust parsing with error handling ensures accurate benchmarking even with malformed responses.
