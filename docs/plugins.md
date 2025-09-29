<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Plugin System

AIPerf features a comprehensive plugin system that allows you to extend its capabilities with custom endpoint implementations. The plugin system is built on top of [pluggy](https://pluggy.readthedocs.io/) and uses Python entry points for automatic discovery.

## Overview

The plugin system allows you to:

- **Add custom endpoints**: Implement support for any API endpoint
- **Unified interface**: Single class handles all operations (request formatting, HTTP communication, response parsing)
- **Dynamic discovery**: Plugins are automatically discovered via entry points
- **Full feature support**: Streaming, authentication, custom headers, metrics, etc.
- **Type safety**: Full Pydantic model validation and type hints

## Architecture

### Core Components

1. **`DynamicEndpoint`**: Base class that plugins inherit from
2. **`PluginManager`**: Discovers and manages plugin instances
3. **`EndpointPluginInfo`**: Pydantic model defining endpoint metadata
4. **Entry Points**: Standard Python mechanism for plugin discovery

### Plugin Structure

Each plugin is a single class that inherits from `DynamicEndpoint` and implements:

- **Endpoint metadata**: Information about capabilities and configuration
- **Request formatting**: Convert AIPerf data structures to API payloads
- **HTTP communication**: Send requests and handle responses
- **Response parsing**: Extract and structure response data

## Creating a Plugin

### 1. Basic Plugin Structure

```python
from aiperf.common.plugins import DynamicEndpoint, EndpointPluginInfo
from aiperf.common.models import RequestRecord, ParsedResponse, Turn

class MyCustomEndpoint(DynamicEndpoint):
    """Custom endpoint implementation."""

    def get_endpoint_info(self) -> EndpointPluginInfo:
        """Return endpoint metadata."""
        return EndpointPluginInfo(
            endpoint_tag="my-custom-endpoint",
            service_kind="custom",
            supports_streaming=False,
            produces_tokens=True,
            endpoint_path="/v1/completions",
            metrics_title="Custom API Metrics",
            description="My custom API endpoint",
        )

    async def format_payload(self, turn: Turn) -> dict[str, Any]:
        """Format conversation turn into API payload."""
        # Extract text from turn and format for your API
        pass

    async def send_request(self, payload: dict[str, Any]) -> RequestRecord:
        """Send request to your API."""
        # Implement HTTP communication
        pass

    async def extract_response_data(self, record: RequestRecord) -> list[ParsedResponse]:
        """Parse API response into structured data."""
        # Parse response and extract relevant data
        pass
```

### 2. Endpoint Metadata

The `EndpointPluginInfo` model defines your endpoint's capabilities:

```python
EndpointPluginInfo(
    endpoint_tag="anthropic-messages",           # Unique identifier
    service_kind="anthropic",                    # Service provider
    supports_streaming=True,                     # Streaming support
    produces_tokens=True,                        # Token-based responses
    supports_audio=False,                        # Audio input support
    supports_images=True,                        # Image input support
    endpoint_path="/v1/messages",                # Default API path
    metrics_title="Anthropic Metrics",          # Display title
    description="Anthropic Messages API",       # Human description
    version="1.0.0",                            # Plugin version
)
```

### 3. Request Formatting

Convert AIPerf's `Turn` objects into your API's expected format:

```python
async def format_payload(self, turn: Turn) -> dict[str, Any]:
    """Format turn data for the API."""

    # Extract text content
    messages = []
    for text in turn.texts:
        for content in text.contents:
            if content:
                messages.append({
                    "role": turn.role or "user",
                    "content": content,
                })

    # Build API payload
    payload = {
        "model": turn.model or self.model_endpoint.primary_model_name,
        "messages": messages,
        "max_tokens": turn.max_tokens,
        "stream": self.model_endpoint.endpoint.streaming,
    }

    # Add custom parameters
    if self.model_endpoint.endpoint.extra:
        payload.update(dict(self.model_endpoint.endpoint.extra))

    return payload
```

### 4. HTTP Communication

Handle the actual HTTP request/response cycle:

```python
async def send_request(self, payload: dict[str, Any]) -> RequestRecord:
    """Send HTTP request to the API."""

    url = self.get_url()          # Built-in URL construction
    headers = self.get_headers()  # Built-in header management
    data = json.dumps(payload)

    start_time = time.perf_counter_ns()

    # Use aiohttp or your preferred HTTP client
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, data=data) as response:
            end_time = time.perf_counter_ns()

            if response.status == 200:
                response_text = await response.text()
                return RequestRecord(
                    request_time_ns=start_time,
                    model_name=payload.get("model"),
                    responses=[TextResponse(
                        text=response_text,
                        perf_ns=end_time - start_time,
                    )],
                    error_details=None,
                )
            else:
                # Handle errors appropriately
                pass
```

### 5. Response Parsing

Extract structured data from API responses:

```python
async def extract_response_data(self, record: RequestRecord) -> list[ParsedResponse]:
    """Parse API responses into structured data."""

    results = []
    for response in record.responses:
        if isinstance(response, TextResponse):
            parsed_data = self._parse_response(response.text)
            if parsed_data:
                results.append(ParsedResponse(
                    perf_ns=response.perf_ns,
                    data=parsed_data,
                ))
    return results

def _parse_response(self, response_text: str) -> BaseResponseData | None:
    """Parse individual response."""
    try:
        json_data = json.loads(response_text)

        # Extract content based on your API format
        if "choices" in json_data:
            content = json_data["choices"][0]["message"]["content"]
            return TextResponseData(text=content)

    except Exception:
        # Handle parsing errors
        return None
```

## Plugin Registration

### 1. Package Structure

```
my_aiperf_plugin/
├── pyproject.toml
├── my_aiperf_plugin/
│   ├── __init__.py
│   └── endpoints.py
└── README.md
```

### 2. Entry Point Configuration

In your plugin's `pyproject.toml`:

```toml
[project.entry-points."aiperf.plugins"]
my-custom-endpoint = "my_aiperf_plugin.endpoints:MyCustomEndpoint"
anthropic-messages = "my_aiperf_plugin.endpoints:AnthropicMessagesEndpoint"
```

### 3. Plugin Installation

```bash
# Install your plugin package
pip install my-aiperf-plugin

# AIPerf will automatically discover it
aiperf --endpoint-type my-custom-endpoint --url https://api.example.com
```

## Advanced Features

### Streaming Support

```python
async def send_request(self, payload: dict[str, Any]) -> RequestRecord:
    """Handle streaming responses."""

    if self.model_endpoint.endpoint.streaming:
        # Handle SSE streaming
        responses = []
        async with session.post(url, headers=headers, data=data) as response:
            async for line in response.content:
                if line.startswith(b"data: "):
                    sse_message = SSEMessage(...)
                    responses.append(sse_message)

        return RequestRecord(responses=responses, ...)
    else:
        # Handle regular responses
        pass
```

### Authentication

```python
def get_headers(self) -> dict[str, str]:
    """Add custom authentication."""
    headers = super().get_headers()

    # Custom API key format
    if self.model_endpoint.endpoint.api_key:
        headers["X-API-Key"] = self.model_endpoint.endpoint.api_key

    return headers
```

### Custom URL Construction

```python
def get_url(self) -> str:
    """Build custom URL format."""
    base_url = self.model_endpoint.endpoint.base_url

    # Add custom path construction logic
    if self.model_endpoint.endpoint.custom_endpoint:
        return f"{base_url}/{self.model_endpoint.endpoint.custom_endpoint}"

    return f"{base_url}/v2/chat/completions"
```

## Usage Examples

### Using Custom Endpoints

```bash
# Use a plugin-provided endpoint
aiperf --endpoint-type anthropic-messages \
       --url https://api.anthropic.com \
       --api-key $ANTHROPIC_API_KEY \
       --model claude-3-sonnet-20240229

# List available endpoints (including plugins)
aiperf --list-endpoints
```

### Plugin Development Workflow

1. **Create plugin class** inheriting from `DynamicEndpoint`
2. **Implement required methods** (metadata, formatting, communication, parsing)
3. **Add entry point** in `pyproject.toml`
4. **Install and test** with AIPerf
5. **Publish** as a Python package

## Best Practices

### Error Handling

- Always handle HTTP errors gracefully
- Provide meaningful error messages
- Use AIPerf's `ErrorDetails` model for consistency

### Performance

- Reuse HTTP connections when possible
- Implement proper resource cleanup in `close()`
- Use async/await throughout

### Compatibility

- Follow AIPerf's data models (`Turn`, `RequestRecord`, etc.)
- Implement all required methods
- Provide comprehensive endpoint metadata

### Testing

```python
import pytest
from aiperf.common.config import UserConfig
from aiperf.clients.model_endpoint_info import ModelEndpointInfo

@pytest.mark.asyncio
async def test_my_endpoint():
    config = UserConfig()
    model_endpoint = ModelEndpointInfo.from_user_config(config)
    endpoint = MyCustomEndpoint(model_endpoint)

    # Test endpoint info
    info = endpoint.get_endpoint_info()
    assert info.endpoint_tag == "my-custom-endpoint"

    # Test payload formatting
    turn = Turn(...)
    payload = await endpoint.format_payload(turn)
    assert "model" in payload
```

## Plugin Examples

See the `examples/` directory for complete plugin implementations:

- **`custom_endpoint_plugin.py`**: Basic custom chat endpoint
- **`anthropic_plugin.py`**: Anthropic Messages API integration
- **`streaming_plugin.py`**: Streaming response handling

## Troubleshooting

### Plugin Not Found

- Verify entry point configuration in `pyproject.toml`
- Ensure plugin package is installed in the same environment as AIPerf
- Check AIPerf logs for plugin loading errors

### Import Errors

- Ensure all dependencies are properly declared
- Check Python path and virtual environment
- Verify AIPerf version compatibility

### Runtime Errors

- Check endpoint URL and authentication
- Verify API response format matches your parsing logic
- Use AIPerf's logging system for debugging

## Contributing

We welcome community plugins! Consider:

- Publishing useful plugins as separate packages
- Contributing examples to the AIPerf repository
- Sharing plugin implementations with the community

For questions or support, please open an issue on the AIPerf GitHub repository.
