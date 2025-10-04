<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 24: OpenAI Client

## Navigation
- Previous: [Chapter 23: HTTP Client Architecture](chapter-23-http-client-architecture.md)
- Next: [Chapter 25: SSE Stream Handling](chapter-25-sse-stream-handling.md)
- [Table of Contents](README.md)

## Overview

The OpenAI client layer builds upon the HTTP client architecture to provide specialized support for OpenAI-compatible endpoints. It handles authentication, payload formatting, endpoint routing, and response parsing for chat, completions, embeddings, rankings, and responses endpoints. This chapter explores the OpenAI client implementation, covering endpoint integration, request conversion, and response extraction.

## Architecture

### OpenAIClientAioHttp Class

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/clients/openai/openai_aiohttp.py`

```python
@InferenceClientFactory.register_all(
    EndpointType.CHAT,
    EndpointType.COMPLETIONS,
    EndpointType.EMBEDDINGS,
    EndpointType.RANKINGS,
    EndpointType.RESPONSES,
)
class OpenAIClientAioHttp(AioHttpClientMixin, AIPerfLoggerMixin, ABC):
    """Inference client for OpenAI based requests using aiohttp."""

    def __init__(self, model_endpoint: ModelEndpointInfo, **kwargs) -> None:
        super().__init__(model_endpoint, **kwargs)
        self.model_endpoint = model_endpoint

    def get_headers(
        self,
        model_endpoint: ModelEndpointInfo,
        x_request_id: str | None = None,
        x_correlation_id: str | None = None,
    ) -> dict[str, str]:
        """Get the headers for the given endpoint."""
        accept = (
            "text/event-stream"
            if model_endpoint.endpoint.streaming
            else "application/json"
        )

        headers = {
            "User-Agent": "aiperf/1.0",
            "Content-Type": "application/json",
            "Accept": accept,
        }
        if model_endpoint.endpoint.api_key:
            headers["Authorization"] = f"Bearer {model_endpoint.endpoint.api_key}"
        if x_request_id:
            headers["X-Request-ID"] = x_request_id
        if x_correlation_id:
            headers["X-Correlation-ID"] = x_correlation_id

        if model_endpoint.endpoint.headers:
            headers.update(model_endpoint.endpoint.headers)
        return headers

    def get_url(self, model_endpoint: ModelEndpointInfo) -> str:
        """Get the URL for the given endpoint."""
        url = model_endpoint.url
        if not url.startswith("http"):
            url = f"http://{url}"
        return url

    async def send_request(
        self,
        model_endpoint: ModelEndpointInfo,
        payload: dict[str, Any],
        x_request_id: str | None = None,
        x_correlation_id: str | None = None,
    ) -> RequestRecord:
        """Send OpenAI request using aiohttp."""
        start_perf_ns = time.perf_counter_ns()
        try:
            self.debug(
                lambda: f"Sending OpenAI request to {model_endpoint.url}, payload: {payload}"
            )

            record = await self.post_request(
                self.get_url(model_endpoint),
                json.dumps(payload),
                self.get_headers(
                    model_endpoint,
                    x_request_id=x_request_id,
                    x_correlation_id=x_correlation_id,
                ),
            )

        except Exception as e:
            record = RequestRecord(
                start_perf_ns=start_perf_ns,
                end_perf_ns=time.perf_counter_ns(),
                error=ErrorDetails(type=e.__class__.__name__, message=str(e)),
            )
            self.exception(f"Error in OpenAI request: {e.__class__.__name__} {str(e)}")

        return record
```

### Endpoint Registration

The `@InferenceClientFactory.register_all` decorator registers the client for multiple endpoint types:

```python
@InferenceClientFactory.register_all(
    EndpointType.CHAT,              # /v1/chat/completions
    EndpointType.COMPLETIONS,       # /v1/completions
    EndpointType.EMBEDDINGS,        # /v1/embeddings
    EndpointType.RANKINGS,          # /v1/rankings
    EndpointType.RESPONSES,         # Custom responses endpoint
)
```

**Benefits**:
- Single client handles all OpenAI endpoint types
- Factory pattern enables easy endpoint switching
- Consistent interface across endpoints
- Simplified client management

## Authentication

### API Key Authentication

```python
if model_endpoint.endpoint.api_key:
    headers["Authorization"] = f"Bearer {model_endpoint.endpoint.api_key}"
```

**Format**: `Bearer {api_key}`

**Example Headers**:
```python
{
    "Authorization": "Bearer sk-proj-1234567890abcdef",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
```

### Custom Headers

```python
if model_endpoint.endpoint.headers:
    headers.update(model_endpoint.endpoint.headers)
```

**Usage**:
```python
endpoint_config = EndpointConfig(
    url="https://api.openai.com/v1/chat/completions",
    api_key="sk-...",
    headers={
        "OpenAI-Organization": "org-...",
        "Custom-Header": "value",
    }
)
```

## Traceability Headers

### Request Tracking

AIPerf supports distributed tracing headers:

```python
def get_headers(
    self,
    model_endpoint: ModelEndpointInfo,
    x_request_id: str | None = None,
    x_correlation_id: str | None = None,
) -> dict[str, str]:
    # ...
    if x_request_id:
        headers["X-Request-ID"] = x_request_id
    if x_correlation_id:
        headers["X-Correlation-ID"] = x_correlation_id
    return headers
```

**X-Request-ID**: Unique identifier for this specific request
**X-Correlation-ID**: Identifier linking related requests together

**Use Cases**:
- End-to-end request tracing
- Debugging distributed systems
- Performance correlation analysis
- Log aggregation and search

**Example**:
```python
record = await client.send_request(
    model_endpoint,
    payload,
    x_request_id="req_abc123",
    x_correlation_id="session_xyz789",
)
```

## URL Construction

### Protocol Handling

```python
def get_url(self, model_endpoint: ModelEndpointInfo) -> str:
    """Get the URL for the given endpoint."""
    url = model_endpoint.url
    if not url.startswith("http"):
        url = f"http://{url}"
    return url
```

**Behavior**:
- Allows URL without protocol: `api.openai.com/v1/chat/completions`
- Adds `http://` prefix if missing
- Preserves `https://` if provided
- Enables simple configuration

**Examples**:
```python
# Input: "api.openai.com/v1/chat/completions"
# Output: "http://api.openai.com/v1/chat/completions"

# Input: "https://api.openai.com/v1/chat/completions"
# Output: "https://api.openai.com/v1/chat/completions"
```

## Request Handling

### Send Request Flow

```python
async def send_request(
    self,
    model_endpoint: ModelEndpointInfo,
    payload: dict[str, Any],
    x_request_id: str | None = None,
    x_correlation_id: str | None = None,
) -> RequestRecord:
    """Send OpenAI request using aiohttp."""

    # Capture start time before any work
    start_perf_ns = time.perf_counter_ns()

    try:
        # Log request details
        self.debug(
            lambda: f"Sending OpenAI request to {model_endpoint.url}, payload: {payload}"
        )

        # Use HTTP client to send request
        record = await self.post_request(
            self.get_url(model_endpoint),
            json.dumps(payload),
            self.get_headers(
                model_endpoint,
                x_request_id=x_request_id,
                x_correlation_id=x_correlation_id,
            ),
        )

    except Exception as e:
        # Capture end time for error case
        record = RequestRecord(
            start_perf_ns=start_perf_ns,
            end_perf_ns=time.perf_counter_ns(),
            error=ErrorDetails(
                type=e.__class__.__name__,
                message=str(e)
            ),
        )
        self.exception(f"Error in OpenAI request: {e.__class__.__name__} {str(e)}")

    return record
```

### Payload Serialization

```python
# Payload is serialized to JSON string
json.dumps(payload)

# Example:
payload = {
    "model": "gpt-4",
    "messages": [
        {"role": "user", "content": "Hello!"}
    ],
    "stream": True,
}

# Serialized:
'{"model":"gpt-4","messages":[{"role":"user","content":"Hello!"}],"stream":true}'
```

## Response Handling

### Content Type Determination

```python
accept = (
    "text/event-stream"
    if model_endpoint.endpoint.streaming
    else "application/json"
)
```

**Non-Streaming**:
```python
headers = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}
```

**Streaming**:
```python
headers = {
    "Accept": "text/event-stream",
    "Content-Type": "application/json",
}
```

### Response Processing

The HTTP client automatically detects response type:

```python
if method == "POST" and response.content_type == "text/event-stream":
    # SSE streaming response
    messages = await AioHttpSSEStreamReader(response).read_complete_stream()
    record.responses.extend(messages)
else:
    # Regular JSON response
    raw_response = await response.text()
    record.responses.append(
        TextResponse(
            perf_ns=record.end_perf_ns,
            content_type=response.content_type,
            text=raw_response,
        )
    )
```

## Endpoint Types

### Chat Completions

**Endpoint**: `/v1/chat/completions`

**Payload Format**:
```python
{
    "model": "gpt-4",
    "messages": [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ],
    "stream": true,
    "max_completion_tokens": 100
}
```

**Non-Streaming Response**:
```json
{
    "id": "chatcmpl-123",
    "object": "chat.completion",
    "model": "gpt-4",
    "choices": [{
        "index": 0,
        "message": {
            "role": "assistant",
            "content": "Hello! How can I help you today?"
        },
        "finish_reason": "stop"
    }]
}
```

**Streaming Response** (SSE):
```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"delta":{"content":"Hello"}}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","choices":[{"delta":{"content":"!"}}]}

data: [DONE]
```

### Completions

**Endpoint**: `/v1/completions`

**Payload Format**:
```python
{
    "model": "gpt-3.5-turbo-instruct",
    "prompt": "Once upon a time",
    "max_tokens": 50,
    "stream": false
}
```

**Response**:
```json
{
    "id": "cmpl-123",
    "object": "text_completion",
    "model": "gpt-3.5-turbo-instruct",
    "choices": [{
        "text": " there was a brave knight...",
        "index": 0,
        "finish_reason": "length"
    }]
}
```

### Embeddings

**Endpoint**: `/v1/embeddings`

**Payload Format**:
```python
{
    "model": "text-embedding-ada-002",
    "input": "The quick brown fox"
}
```

**Response**:
```json
{
    "object": "list",
    "data": [{
        "object": "embedding",
        "embedding": [0.0023, -0.009, 0.015, ...],
        "index": 0
    }],
    "model": "text-embedding-ada-002"
}
```

### Rankings

**Endpoint**: `/v1/rankings` (Custom)

**Payload Format**:
```python
{
    "model": "rerank-model",
    "query": "search query",
    "documents": ["doc1", "doc2", "doc3"]
}
```

**Response**:
```json
{
    "rankings": [
        {"index": 0, "score": 0.95},
        {"index": 2, "score": 0.82},
        {"index": 1, "score": 0.71}
    ]
}
```

### Responses

**Endpoint**: Custom endpoint for responses

**Payload Format**:
```python
{
    "model": "response-model",
    "input": "..."
}
```

**Response**:
```json
{
    "object": "response",
    "output_text": "..."
}
```

## Error Handling

### Exception Capture

```python
try:
    record = await self.post_request(...)
except Exception as e:
    record = RequestRecord(
        start_perf_ns=start_perf_ns,
        end_perf_ns=time.perf_counter_ns(),
        error=ErrorDetails(
            type=e.__class__.__name__,
            message=str(e)
        ),
    )
    self.exception(f"Error in OpenAI request: {e.__class__.__name__} {str(e)}")
```

### Common Error Types

**Network Errors**:
```python
aiohttp.ClientConnectorError: Cannot connect to host
aiohttp.ServerDisconnectedError: Server disconnected
```

**Timeout Errors**:
```python
asyncio.TimeoutError: Request timeout
aiohttp.ClientTimeout: Timeout reached
```

**HTTP Errors**:
```python
# Captured in RequestRecord with status code
record.status = 429  # Rate limit
record.error = ErrorDetails(
    code=429,
    type="Too Many Requests",
    message='{"error": {"message": "Rate limit exceeded"}}'
)
```

## Integration with Request Converters

The OpenAI client works with request converters to format payloads:

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/clients/openai/openai_chat.py`

```python
@RequestConverterFactory.register(EndpointType.CHAT)
class OpenAIChatCompletionRequestConverter(AIPerfLoggerMixin):
    """Request converter for OpenAI chat completion requests."""

    async def format_payload(
        self,
        model_endpoint: ModelEndpointInfo,
        turn: Turn,
    ) -> dict[str, Any]:
        """Format payload for a chat completion request."""
        messages = self._create_messages(turn)

        payload = {
            "messages": messages,
            "model": turn.model or model_endpoint.primary_model_name,
            "stream": model_endpoint.endpoint.streaming,
        }

        if turn.max_tokens is not None:
            payload["max_completion_tokens"] = turn.max_tokens

        if model_endpoint.endpoint.extra:
            payload.update(model_endpoint.endpoint.extra)

        return payload
```

**Usage Flow**:
```
Turn → RequestConverter → Payload Dict → OpenAIClient → JSON String → HTTP Request
```

## Integration with Response Parsers

The OpenAI client works with response extractors to parse responses:

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
```

**Usage Flow**:
```
RequestRecord → ResponseExtractor → ParsedResponse List → Metrics
```

## Performance Considerations

### Connection Reuse

The OpenAI client inherits connection pooling from `AioHttpClientMixin`:

```python
# Connector created once and reused
self.tcp_connector = create_tcp_connector()

# All requests use the same connector
async with aiohttp.ClientSession(
    connector=self.tcp_connector,
    connector_owner=False,  # Don't close on session end
) as session:
    # Make request
    pass
```

### Timing Precision

Timing is captured at critical points:

```python
# Capture start time immediately
start_perf_ns = time.perf_counter_ns()

try:
    # Make request (timed internally)
    record = await self.post_request(...)
except Exception as e:
    # Capture end time for errors
    end_perf_ns = time.perf_counter_ns()
```

### Payload Optimization

JSON serialization uses the standard library for compatibility:

```python
import json
json.dumps(payload)  # Standard library

# For performance-critical scenarios, consider:
import orjson
orjson.dumps(payload)  # Faster JSON serialization
```

## Usage Examples

### Basic Chat Request

```python
from aiperf.clients.openai.openai_aiohttp import OpenAIClientAioHttp
from aiperf.clients.model_endpoint_info import ModelEndpointInfo

# Create client
model_endpoint = ModelEndpointInfo(
    url="https://api.openai.com/v1/chat/completions",
    endpoint=EndpointConfig(
        type=EndpointType.CHAT,
        streaming=False,
        api_key="sk-...",
    ),
)

client = OpenAIClientAioHttp(model_endpoint)

# Send request
payload = {
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello!"}],
}

record = await client.send_request(model_endpoint, payload)

# Check result
if record.error:
    print(f"Error: {record.error.message}")
else:
    print(f"Latency: {(record.end_perf_ns - record.start_perf_ns) / 1_000_000} ms")
    print(f"Responses: {len(record.responses)}")
```

### Streaming Chat Request

```python
# Enable streaming
model_endpoint = ModelEndpointInfo(
    endpoint=EndpointConfig(
        type=EndpointType.CHAT,
        streaming=True,
        api_key="sk-...",
    ),
)

payload = {
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Tell me a story"}],
    "stream": True,
}

record = await client.send_request(model_endpoint, payload)

# Process streaming responses
for response in record.responses:
    if isinstance(response, SSEMessage):
        print(f"Chunk at {response.perf_ns}: {response.extract_data_content()}")
```

### With Traceability Headers

```python
record = await client.send_request(
    model_endpoint,
    payload,
    x_request_id="req_abc123",
    x_correlation_id="session_xyz789",
)
```

## Key Takeaways

1. **Unified Interface**: Single client handles all OpenAI endpoint types

2. **Authentication**: Bearer token authentication with custom header support

3. **Traceability**: X-Request-ID and X-Correlation-ID headers for distributed tracing

4. **Streaming Support**: Automatic detection and handling of SSE responses

5. **Error Handling**: Comprehensive error capture for both exceptions and HTTP errors

6. **Performance**: Inherits connection pooling and optimizations from HTTP client

7. **Timing Precision**: Nanosecond-resolution timing for accurate measurements

8. **Factory Integration**: Registered with factory pattern for easy instantiation

9. **Converter Integration**: Works with request converters for payload formatting

10. **Parser Integration**: Works with response extractors for response parsing

## What's Next

- **Chapter 25: SSE Stream Handling** - Learn how streaming responses are parsed with precise timing
- **Chapter 27: Request Converters** - Explore payload formatting for different endpoint types
- **Chapter 28: Response Parsers** - Understand response extraction and parsing

---

**Remember**: The OpenAI client provides a clean interface for OpenAI-compatible endpoints while maintaining the performance and precision required for accurate benchmarking.
