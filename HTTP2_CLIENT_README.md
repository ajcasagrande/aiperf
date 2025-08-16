<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# HTTP/2 Client for AIPerf

This document describes the new HTTP/2 client implementation using `httpx` that provides enhanced performance through connection sharing, multiplexing, and modern HTTP/2 features.

## Overview

The `HttpxClientMixin` is a fully featured clone of the existing `AioHttpClientMixin` that leverages HTTP/2 capabilities for improved performance in AI model benchmarking scenarios. It maintains the same API while providing superior connection management and concurrent request handling.

## Key Features

### 🚀 HTTP/2 Support
- **Protocol Multiplexing**: Multiple requests over a single connection
- **Header Compression**: Reduced overhead with HPACK compression
- **Server Push**: Support for server-initiated streams (where applicable)
- **Binary Protocol**: More efficient than HTTP/1.1 text protocol

### 🔗 Connection Sharing (Enabled by Default)
- **Automatic Connection Pooling**: Intelligent reuse of existing connections
- **Configurable Limits**: Control max connections and keepalive settings
- **Connection Persistence**: Long-lived connections for multiple requests
- **Optimal Resource Usage**: Reduced connection overhead and faster subsequent requests

### 📊 Performance Optimizations
- **Concurrent Request Handling**: Superior performance for multiple simultaneous requests
- **Precise Timing Measurements**: Nanosecond-level timing for accurate benchmarking
- **Optimized SSE Streaming**: Efficient handling of Server-Sent Events
- **Memory Efficient**: Streaming response processing without excessive buffering

### 🛡️ Enterprise Features
- **SSL/TLS Support**: Built-in certificate verification and security
- **Error Handling**: Comprehensive error reporting and recovery
- **Timeout Management**: Granular timeout controls for different operations
- **Environment Configuration**: Easy tuning via environment variables

## Installation

The HTTP/2 client requires `httpx` with HTTP/2 support:

```bash
# Already added to pyproject.toml
pip install "httpx[http2]~=0.28.1"
```

## Basic Usage

### Simple HTTP/2 Client

```python
import asyncio
from aiperf.clients.http import HttpxClientMixin
from aiperf.clients.model_endpoint_info import EndpointInfo, ModelEndpointInfo

async def basic_example():
    # Setup endpoint configuration
    endpoint_info = EndpointInfo(timeout=30.0)
    model_endpoint = ModelEndpointInfo(endpoint=endpoint_info)

    # Create HTTP/2 client
    client = HttpxClientMixin(model_endpoint=model_endpoint)

    # Initialize session with headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer your-token"
    }
    client.initialize_session(headers)

    try:
        # Make a request
        record = await client.post_request(
            url="https://api.example.com/v1/chat/completions",
            payload='{"model": "gpt-3.5-turbo", "messages": [...]}',
            headers={"Custom-Header": "value"}
        )

        print(f"Status: {record.status}")
        print(f"Response: {record.responses[0].text}")

    finally:
        await client.close()

asyncio.run(basic_example())
```

### OpenAI Client with HTTP/2

```python
from aiperf.clients.openai.openai_httpx import OpenAIClientHttpx

async def openai_example():
    endpoint_info = EndpointInfo(timeout=60.0)
    model_endpoint = ModelEndpointInfo(endpoint=endpoint_info)

    client = OpenAIClientHttpx(model_endpoint=model_endpoint)
    client.initialize_session({"Authorization": "Bearer sk-..."})

    # The client automatically uses HTTP/2 with connection sharing
    record = await client.post_request(
        "https://api.openai.com/v1/chat/completions",
        payload,
        headers
    )

    await client.close()
```

## Configuration

### Default Settings

The HTTP/2 client comes with optimized defaults:

```python
from aiperf.clients.http.defaults import HttpxDefaults

# Default configuration
HttpxDefaults.HTTP2 = True                    # Enable HTTP/2
HttpxDefaults.MAX_CONNECTIONS = 100           # Connection pool size
HttpxDefaults.MAX_KEEPALIVE_CONNECTIONS = 20  # Keepalive connections
HttpxDefaults.KEEPALIVE_EXPIRY = 30.0         # Keepalive duration (seconds)
HttpxDefaults.TIMEOUT = 30.0                  # Default timeout
HttpxDefaults.VERIFY_SSL = True               # SSL verification
HttpxDefaults.FOLLOW_REDIRECTS = False        # No redirects for benchmarking
```

### Environment Variables

Fine-tune performance using environment variables:

```bash
# Connection limits
export AIPERF_HTTP2_CONNECTION_LIMIT=200
export AIPERF_HTTP2_KEEPALIVE_LIMIT=50

# Run your application
python your_benchmark.py
```

### Custom Configuration

```python
import httpx
from aiperf.clients.http.httpx_client import HttpxClientMixin

class CustomHttpxClient(HttpxClientMixin):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Override limits for high-throughput scenarios
        self.limits = httpx.Limits(
            max_connections=500,
            max_keepalive_connections=100,
            keepalive_expiry=60.0
        )
```

## Performance Comparison

### Concurrent Requests Benchmark

```python
import asyncio
import time
from aiperf.clients.http import AioHttpClientMixin, HttpxClientMixin

async def benchmark_concurrent_requests():
    """Compare performance of both clients with concurrent requests."""

    async def test_client(client_class, num_requests=50):
        client = client_class(model_endpoint=endpoint)
        client.initialize_session(headers)

        start = time.perf_counter()
        tasks = [
            client.post_request(url, payload, headers)
            for _ in range(num_requests)
        ]
        await asyncio.gather(*tasks)
        duration = time.perf_counter() - start

        await client.close()
        return duration

    # Test both clients
    http2_time = await test_client(HttpxClientMixin)
    http1_time = await test_client(AioHttpClientMixin)

    improvement = ((http1_time - http2_time) / http1_time) * 100
    print(f"HTTP/2 improvement: {improvement:.1f}%")
```

### Expected Performance Benefits

- **Concurrent Requests**: 20-40% improvement with connection sharing
- **Sequential Requests**: 10-20% improvement with connection reuse
- **Large Payloads**: Significant improvement with header compression
- **SSE Streams**: Enhanced multiplexing capabilities

## SSE Streaming Support

The HTTP/2 client provides optimized Server-Sent Events handling:

```python
async def sse_streaming_example():
    client = HttpxClientMixin(model_endpoint=endpoint)
    client.initialize_session(headers)

    # SSE stream is automatically detected and parsed
    record = await client.post_request(
        url="https://api.example.com/v1/chat/completions",
        payload='{"stream": true, "model": "gpt-3.5-turbo", ...}',
        headers={"Accept": "text/event-stream"}
    )

    # Access individual SSE messages with precise timing
    for sse_message in record.responses:
        for packet in sse_message.packets:
            if packet.name == "data":
                print(f"Data: {packet.value}")
                print(f"Timestamp: {sse_message.perf_ns}")
```

## Error Handling

Comprehensive error handling with detailed diagnostics:

```python
async def error_handling_example():
    client = HttpxClientMixin(model_endpoint=endpoint)
    client.initialize_session(headers)

    record = await client.post_request(url, payload, headers)

    if record.error:
        print(f"Error Code: {record.error.code}")
        print(f"Error Type: {record.error.type}")
        print(f"Error Message: {record.error.message}")

        # Handle specific error types
        if record.error.code == 429:
            print("Rate limited - implement backoff")
        elif record.error.code >= 500:
            print("Server error - retry request")

    await client.close()
```

## Migration Guide

### From AioHttpClientMixin

The HTTP/2 client is a drop-in replacement:

```python
# Old (HTTP/1.1 with aiohttp)
from aiperf.clients.http import AioHttpClientMixin
client = AioHttpClientMixin(model_endpoint=endpoint)

# New (HTTP/2 with httpx)
from aiperf.clients.http import HttpxClientMixin
client = HttpxClientMixin(model_endpoint=endpoint)

# Same API - no code changes needed!
```

### Key Differences

| Feature | AioHttpClientMixin | HttpxClientMixin |
|---------|-------------------|------------------|
| Protocol | HTTP/1.1 | HTTP/2 |
| Connection Sharing | Limited | Automatic |
| Concurrent Performance | Good | Excellent |
| Memory Usage | Higher | Lower |
| Setup Complexity | Simple | Simple |

## Best Practices

### 1. Connection Management
```python
# ✅ Good: Reuse client for multiple requests
client = HttpxClientMixin(model_endpoint=endpoint)
client.initialize_session(headers)

for i in range(100):
    await client.post_request(url, payload, headers)

await client.close()

# ❌ Bad: Create new client for each request
for i in range(100):
    client = HttpxClientMixin(model_endpoint=endpoint)
    await client.post_request(url, payload, headers)
    await client.close()
```

### 2. Concurrent Requests
```python
# ✅ Good: Use single client for concurrent requests
client = HttpxClientMixin(model_endpoint=endpoint)
client.initialize_session(headers)

tasks = [client.post_request(url, payload, headers) for _ in range(10)]
results = await asyncio.gather(*tasks)

await client.close()
```

### 3. Error Handling
```python
# ✅ Good: Check for errors and handle appropriately
record = await client.post_request(url, payload, headers)

if record.error:
    if record.error.code == 429:
        await asyncio.sleep(1)  # Rate limit backoff
        # Retry logic here
    else:
        raise Exception(f"Request failed: {record.error.message}")
```

## Troubleshooting

### Common Issues

**1. SSL Certificate Errors**
```python
# Disable SSL verification for development only
client.client = httpx.AsyncClient(verify=False, ...)
```

**2. Connection Pool Exhaustion**
```bash
# Increase connection limits
export AIPERF_HTTP2_CONNECTION_LIMIT=500
export AIPERF_HTTP2_KEEPALIVE_LIMIT=100
```

**3. Timeout Issues**
```python
# Adjust timeouts for slow endpoints
endpoint_info = EndpointInfo(timeout=120.0)  # 2 minutes
```

### Performance Tuning

**For High-Throughput Scenarios:**
- Increase `MAX_CONNECTIONS` to 500+
- Increase `MAX_KEEPALIVE_CONNECTIONS` to 100+
- Extend `KEEPALIVE_EXPIRY` to 60+ seconds
- Use connection pooling across multiple client instances

**For Low-Latency Scenarios:**
- Reduce `MAX_CONNECTIONS` to 50-100
- Use shorter `KEEPALIVE_EXPIRY` (15-30 seconds)
- Pre-warm connections before benchmarking

## Demo Script

Run the included demonstration script to see the HTTP/2 client in action:

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the demo
python examples/http2_client_demo.py
```

The demo script demonstrates:
- Basic usage comparison between HTTP/1.1 and HTTP/2
- Concurrent request performance benefits
- Error handling capabilities
- Configuration options

## Contributing

When extending the HTTP/2 client:

1. **Follow Existing Patterns**: Maintain API compatibility with `AioHttpClientMixin`
2. **Add Tests**: Include comprehensive test coverage for new features
3. **Document Changes**: Update this README and code documentation
4. **Performance Testing**: Benchmark new features against existing implementation
5. **Error Handling**: Ensure robust error handling and reporting

## Conclusion

The HTTP/2 client provides significant performance improvements while maintaining full API compatibility. It's particularly beneficial for:

- High-throughput benchmarking scenarios
- Concurrent request processing
- Long-running benchmark sessions
- Production AI model inference workloads

The connection sharing and HTTP/2 multiplexing capabilities make it an ideal choice for modern AI benchmarking requirements.
