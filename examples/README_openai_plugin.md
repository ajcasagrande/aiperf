<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# OpenAI Chat Endpoint Plugin for AIPerf

A comprehensive, fully-featured OpenAI Chat Completions API plugin for AIPerf's plugin system. This plugin provides complete compatibility with the OpenAI Chat Completions API while leveraging AIPerf's transport abstraction and plugin architecture.

## Features

### 🚀 **Complete OpenAI API Compatibility**
- Full OpenAI Chat Completions API support
- All standard parameters (`temperature`, `max_tokens`, `top_p`, etc.)
- Organization and project headers
- API versioning support

### 🎯 **Multi-Modal Support**
- **Text**: Standard text messages with role support
- **Images**: Base64 and URL image inputs
- **Audio**: Input audio with format specification
- **Mixed content**: Multiple content types in single messages

### ⚡ **Streaming & Non-Streaming**
- Real-time streaming responses
- Server-sent events (SSE) parsing
- Usage statistics in streaming mode
- Optimized streaming headers and settings

### 🧠 **Reasoning Model Support**
- Specialized support for OpenAI's reasoning models (o1-preview, o1-mini)
- Parameter filtering for reasoning models
- Enhanced reasoning token parsing
- Reasoning effort configuration

### 🔧 **Transport Abstraction**
- HTTP transport (primary)
- Extensible for gRPC and WebSocket
- Automatic transport selection
- Custom headers and parameters

### 📊 **Advanced Parsing**
- Complete OpenAI object type support
- Streaming chunk parsing
- Error handling and validation
- Response data extraction

## Plugin Variants

### 1. **OpenAIChatEndpoint** - Standard Implementation
```python
endpoint_tag: "openai-chat"
description: "OpenAI Chat Completions API with full multi-modal support"
```

### 2. **OpenAIChatStreamingEndpoint** - Streaming Optimized
```python
endpoint_tag: "openai-chat-streaming"
description: "OpenAI Chat Completions API optimized for streaming responses"
features:
  - Forced streaming enabled
  - Streaming-specific headers
  - Usage statistics included
```

### 3. **OpenAIChatReasoningEndpoint** - Reasoning Models
```python
endpoint_tag: "openai-chat-reasoning"
description: "OpenAI Chat Completions API with enhanced reasoning model support"
features:
  - o1 model parameter filtering
  - Reasoning effort configuration
  - Enhanced reasoning parsing
```

## Installation & Registration

### Plugin Package Structure
```
your-openai-plugin/
├── pyproject.toml
├── your_package/
│   ├── __init__.py
│   └── openai_plugins.py
└── README.md
```

### pyproject.toml Configuration
```toml
[project.entry-points."aiperf.plugins"]
openai-chat = "your_package.openai_plugins:OpenAIChatEndpoint"
openai-chat-streaming = "your_package.openai_plugins:OpenAIChatStreamingEndpoint"
openai-chat-reasoning = "your_package.openai_plugins:OpenAIChatReasoningEndpoint"
```

### Installation
```bash
# Install your plugin package
pip install your-aiperf-openai-plugin

# Verify installation
aiperf --list-endpoints
```

## Usage Examples

### Basic Chat Completion
```bash
aiperf \
  --endpoint-type openai-chat \
  --url https://api.openai.com \
  --api-key $OPENAI_API_KEY \
  --model gpt-4o \
  --input-text "Hello, how are you?"
```

### Streaming Chat
```bash
aiperf \
  --endpoint-type openai-chat-streaming \
  --url https://api.openai.com \
  --api-key $OPENAI_API_KEY \
  --model gpt-4o \
  --streaming \
  --input-text "Write a short story"
```

### Reasoning Model
```bash
aiperf \
  --endpoint-type openai-chat-reasoning \
  --url https://api.openai.com \
  --api-key $OPENAI_API_KEY \
  --model o1-preview \
  --input-text "Solve this complex math problem: ..."
```

### Multi-Modal Input
```bash
aiperf \
  --endpoint-type openai-chat \
  --url https://api.openai.com \
  --api-key $OPENAI_API_KEY \
  --model gpt-4o \
  --input-type mixed \
  --input-text "Describe this image" \
  --input-images ./image.jpg
```

### Custom Parameters
```bash
aiperf \
  --endpoint-type openai-chat \
  --url https://api.openai.com \
  --api-key $OPENAI_API_KEY \
  --model gpt-4o \
  --extra temperature:0.8 \
  --extra max_completion_tokens:2000 \
  --extra top_p:0.9
```

### Organization/Project Headers
```bash
aiperf \
  --endpoint-type openai-chat \
  --url https://api.openai.com \
  --api-key $OPENAI_API_KEY \
  --extra organization:org-123 \
  --extra project:proj-456
```

## API Compatibility

### Supported Parameters
| Parameter | Standard | Streaming | Reasoning | Notes |
|-----------|----------|-----------|-----------|-------|
| `model` | ✅ | ✅ | ✅ | Required |
| `messages` | ✅ | ✅ | ✅ | Auto-generated from Turn |
| `max_completion_tokens` | ✅ | ✅ | ✅ | Maps from `max_tokens` |
| `temperature` | ✅ | ✅ | ❌ | Filtered for o1 models |
| `top_p` | ✅ | ✅ | ❌ | Filtered for o1 models |
| `stream` | ✅ | ✅ | ✅ | Auto-set based on config |
| `stream_options` | ❌ | ✅ | ❌ | Streaming variant only |
| `reasoning_effort` | ❌ | ❌ | ✅ | Reasoning variant only |

### Message Format Support
| Content Type | Support | Format |
|--------------|---------|---------|
| Text | ✅ | `{"type": "text", "text": "..."}` |
| Images | ✅ | `{"type": "image_url", "image_url": {"url": "..."}}` |
| Audio | ✅ | `{"type": "input_audio", "input_audio": {"data": "...", "format": "..."}}` |

### Response Parsing
| Object Type | Support | Description |
|-------------|---------|-------------|
| `chat.completion` | ✅ | Standard completion response |
| `chat.completion.chunk` | ✅ | Streaming chunk response |
| `text_completion` | ✅ | Legacy completion format |
| `list` | ✅ | List responses |
| Custom reasoning | ✅ | Enhanced reasoning parsing |

## Advanced Features

### Custom Headers
```python
def get_custom_headers(self) -> dict[str, str]:
    return {
        "OpenAI-Beta": "assistants=v2",
        "User-Agent": "aiperf-openai-plugin/1.0",
        "OpenAI-Organization": "org-123",  # If configured
    }
```

### Transport Configuration
```python
transport_config=MultiTransportConfig(
    supported_transports=[
        TransportConfig(
            transport_type=TransportType.HTTP,
            http_method=HttpMethod.POST,
            content_type="application/json",
            accept_type="application/json",
            streaming_accept_type="text/event-stream",
        ),
    ],
    default_transport=TransportType.HTTP,
)
```

### Error Handling
- JSON parsing errors with detailed logging
- Invalid object type handling
- Streaming end marker detection (`[DONE]`)
- Graceful fallback for unknown formats

## Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest examples/test_openai_plugin.py -v
```

### Code Structure
```python
class OpenAIChatEndpoint(DynamicEndpoint):
    def get_endpoint_info(self) -> EndpointPluginInfo: ...
    async def format_payload(self, turn: Turn) -> dict[str, Any]: ...
    async def extract_response_data(self, record: RequestRecord) -> list[ParsedResponse]: ...
    def get_custom_headers(self) -> dict[str, str]: ...
    def get_url_params(self) -> dict[str, str]: ...
```

### Key Methods
- **`_create_messages()`**: Converts Turn to OpenAI messages format
- **`_parse_raw_text()`**: Parses OpenAI JSON responses
- **`_infer_object_type()`**: Detects OpenAI object types
- **`_parse_response()`**: Handles different response types

## Performance Considerations

### Optimizations
- **Streaming**: Optimized headers and parameters for real-time responses
- **Reasoning**: Parameter filtering to avoid API errors
- **Multi-modal**: Efficient content type handling
- **Transport**: Reuses HTTP connections via transport layer

### Metrics Support
- Request/response latency tracking
- Token counting (input/output/reasoning)
- Error rate monitoring
- Throughput measurements

## Troubleshooting

### Common Issues

**1. "Unsupported OpenAI object type"**
```
Solution: Check API response format, ensure OpenAI compatibility
```

**2. "Audio content must be in format 'format,b64_audio'"**
```
Solution: Ensure audio content is formatted as "mp3,base64data"
```

**3. "Transport type not supported"**
```
Solution: Verify endpoint supports the requested transport type
```

**4. "o1 model parameter error"**
```
Solution: Use reasoning endpoint variant for o1 models
```

### Debug Mode
```bash
aiperf --endpoint-type openai-chat --debug --verbose
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
Licensed under the Apache-2.0 License.

---

## Summary

This OpenAI Chat endpoint plugin demonstrates:

✅ **Complete API Compatibility** - Full OpenAI Chat Completions support
✅ **Multi-Modal Capabilities** - Text, images, and audio in one plugin
✅ **Streaming Support** - Real-time response handling
✅ **Reasoning Models** - Specialized o1 model support
✅ **Transport Abstraction** - Clean separation of concerns
✅ **Comprehensive Parsing** - All OpenAI response types
✅ **Production Ready** - Error handling, logging, testing
✅ **Maintainable Code** - Clear structure and documentation

The plugin showcases the power and flexibility of AIPerf's new plugin system while providing a fully functional, production-ready implementation of one of the most important AI APIs.
