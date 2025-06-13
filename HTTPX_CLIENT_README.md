<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# HTTPX OpenAI Inference Client

A high-performance HTTP/2-enabled OpenAI inference client implementation using `httpx` for maximum concurrent request performance and timestamp accuracy.

## Features

### 🚀 Performance Optimizations
- **HTTP/2 Support**: Leverages HTTP/2 multiplexing for better connection efficiency
- **Advanced Connection Pooling**: Optimized for high concurrency with 2500 max connections
- **SSL/TLS Optimizations**: Optimized cipher suites and ALPN protocol negotiation
- **Precise Timing**: Nanosecond-level timestamp accuracy for benchmarking
- **Streaming Support**: Efficient Server-Sent Events (SSE) processing

### 🔧 Technical Features
- **Granular Timeouts**: Separate connect, read, write, and pool timeouts
- **Compression Support**: Automatic gzip, deflate, and Brotli compression
- **Error Handling**: Comprehensive error handling with detailed timing information
- **Memory Efficient**: Optimized chunk processing for streaming responses

## Usage

### Basic Usage

```python
import asyncio
from aiperf.backend.openai_client_httpx import OpenAIClientHttpx
from aiperf.backend.openai_common import OpenAIClientConfig, OpenAIChatCompletionRequest

async def main():
    # Create client configuration
    config = OpenAIClientConfig(
        url="http://127.0.0.1:8080",
        api_key="your-api-key",
        model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
        max_tokens=100,
    )

    # Create the client
    client = OpenAIClientHttpx(config)

    # Create a request
    request = OpenAIChatCompletionRequest(
        model=config.model,
        max_tokens=config.max_tokens,
        messages=[{"role": "user", "content": "Hello!"}],
    )

    # Send the request
    response = await client.send_chat_completion_request(request)

    # Check timing metrics
    print(f"TTFT: {response.time_to_first_response_ns / 1_000_000:.1f}ms")
    print(f"Response chunks: {len(response.responses)}")

    # Clean up
    await client.__aexit__(None, None, None)

asyncio.run(main())
```

### Factory Usage

```python
from aiperf.common.factories import InferenceClientFactory
from aiperf.common.enums import InferenceClientType
from aiperf.backend.openai_common import OpenAIClientConfig

# Create via factory
client = InferenceClientFactory.create_instance(
    InferenceClientType.OPENAI_HTTPX,
    config=OpenAIClientConfig(
        url="http://127.0.0.1:8080",
        api_key="your-api-key",
        model="your-model-name",
    )
)
```

### Concurrent Requests

```python
async def concurrent_example():
    client = OpenAIClientHttpx(config)

    async def send_request(prompt):
        request = OpenAIChatCompletionRequest(
            model=config.model,
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        return await client.send_chat_completion_request(request)

    # Send multiple requests concurrently
    prompts = ["Hello!", "How are you?", "What is AI?"]
    tasks = [send_request(prompt) for prompt in prompts]
    responses = await asyncio.gather(*tasks)

    # Process responses
    for i, response in enumerate(responses):
        print(f"Request {i+1}: {len(response.responses)} chunks")
```

## Configuration

### OpenAIClientConfig Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | `"http://localhost:8080"` | Server URL |
| `api_key` | `str` | `None` | API key for authentication |
| `model` | `str` | `"deepseek-ai/DeepSeek-R1-Distill-Llama-8B"` | Model name |
| `max_tokens` | `int` | `100` | Maximum tokens to generate |
| `temperature` | `float` | `0.7` | Sampling temperature |
| `organization` | `str` | `None` | OpenAI organization ID |
| `timeout_ms` | `int` | `300000` | Request timeout in milliseconds |

### HTTP/2 Configuration

The client automatically configures HTTP/2 with:
- **Connection Limits**: 2500 max connections, 2500 max keepalive
- **Timeouts**: 30s connect, 300s read, 30s write, 60s pool
- **SSL/TLS**: Optimized cipher suites, ALPN negotiation
- **Compression**: Automatic content encoding support

## Performance Comparison

Use the provided test scripts to compare performance:

```bash
# Run performance comparison
python integration_tests/httpx_vs_aiohttp_test.py

# Run basic example
python integration_tests/httpx_example.py
```

### Expected Performance Benefits

- **HTTP/2 Multiplexing**: Better connection utilization for concurrent requests
- **Reduced Latency**: Optimized SSL/TLS handshakes and connection reuse
- **Higher Throughput**: More efficient concurrent request handling
- **Better Accuracy**: More precise timestamp measurements

## Compatibility

### Full Compatibility with aiohttp Client

The HTTPX client is fully compatible with the existing aiohttp implementation:

- Same interface (`OpenAIClientConfigMixin`)
- Same request/response models
- Same factory registration pattern
- Same timing measurement APIs
- Same error handling

### Switching Between Clients

```python
# Use aiohttp client
client_aio = InferenceClientFactory.create_instance(
    InferenceClientType.OPENAI, config=config
)

# Use httpx client (drop-in replacement)
client_httpx = InferenceClientFactory.create_instance(
    InferenceClientType.OPENAI_HTTPX, config=config
)
```

## Implementation Details

### Architecture

```
OpenAIClientHttpx
├── _create_http_client()      # HTTP/2 client setup
├── _create_transport()        # SSL/TLS optimizations
├── send_chat_completion_request()  # Main request handler
├── _aiter_sse_chunks()       # Streaming response processor
└── Timing integration       # RequestTimers for accuracy
```

### Key Optimizations

1. **HTTP/2 Transport**: Custom transport with optimized SSL context
2. **Connection Pooling**: High-limit connection reuse
3. **Streaming Processing**: Efficient SSE chunk processing
4. **Error Handling**: Comprehensive error capture and timing
5. **Memory Management**: Optimized buffer sizes for streaming

### Dependencies

- `httpx[http2]>=0.28.1` - Core HTTP client with HTTP/2 support
- `h2` - HTTP/2 protocol implementation (included with httpx[http2])

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure `httpx` is installed with HTTP/2 support
   ```bash
   pip install 'httpx[http2]>=0.28.1'
   ```

2. **Connection Errors**: Check server HTTP/2 support
   ```python
   # Enable debug logging
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

3. **Performance Issues**: Verify concurrent connection limits
   ```python
   # Check connection pool utilization
   print(client.http_client._state)
   ```

### Debug Mode

```python
import logging
logging.getLogger('httpx').setLevel(logging.DEBUG)
logging.getLogger('aiperf.backend.openai_client_httpx').setLevel(logging.DEBUG)
```

## Future Enhancements

- [ ] Socket-level optimizations (when httpx supports custom socket factories)
- [ ] Advanced retry policies with exponential backoff
- [ ] Connection health monitoring
- [ ] Custom HTTP/2 flow control settings
- [ ] Metrics and monitoring integration
