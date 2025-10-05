# Chapter 23: HTTP Client Architecture

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Navigation
- Previous: [Chapter 22: Aggregate and Derived Metrics](chapter-22-aggregate-derived-metrics.md)
- Next: [Chapter 24: OpenAI Client](chapter-24-openai-client.md)
- [Table of Contents](README.md)

## Overview

AIPerf's HTTP client layer provides high-performance, low-latency request handling with nanosecond-precision timing measurements. Built on `aiohttp`, the `AioHttpClientMixin` class is optimized specifically for benchmarking workloads, supporting both streaming and non-streaming responses while maintaining accurate timing data critical for performance analysis.

This chapter provides a comprehensive examination of the HTTP client architecture, covering connection management, timing precision, error handling, and performance optimizations.

## Architecture

### AioHttpClientMixin Class

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/clients/http/aiohttp_client.py`

```python
class AioHttpClientMixin(AIPerfLoggerMixin):
    """A high-performance HTTP client for communicating with HTTP based REST APIs using aiohttp.

    This class is optimized for maximum performance and accurate timing measurements,
    making it ideal for benchmarking scenarios.
    """

    def __init__(self, model_endpoint: ModelEndpointInfo, **kwargs) -> None:
        self.model_endpoint = model_endpoint
        super().__init__(model_endpoint=model_endpoint, **kwargs)
        self.tcp_connector = create_tcp_connector()

        # Configure timeouts
        self.timeout = aiohttp.ClientTimeout(
            total=self.model_endpoint.endpoint.timeout,
            connect=self.model_endpoint.endpoint.timeout,
            sock_connect=self.model_endpoint.endpoint.timeout,
            sock_read=self.model_endpoint.endpoint.timeout,
            ceil_threshold=self.model_endpoint.endpoint.timeout,
        )
```

### Key Design Principles

1. **Mixin Architecture**: Composable design for client implementations
2. **Connection Pooling**: Reusable TCP connections across requests
3. **Timing Precision**: Nanosecond-resolution timestamps at critical points
4. **Async/Await**: Non-blocking I/O for maximum concurrency
5. **Error Resilience**: Comprehensive error handling and recovery

## Connection Management

### TCP Connector Creation

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/clients/http/aiohttp_client.py`

```python
def create_tcp_connector(**kwargs) -> aiohttp.TCPConnector:
    """Create a new connector with the given configuration."""

    def socket_factory(addr_info):
        """Custom socket factory optimized for SSE streaming performance."""
        family, sock_type, proto, _, _ = addr_info
        sock = socket.socket(family=family, type=sock_type, proto=proto)
        SocketDefaults.apply_to_socket(sock)
        return sock

    default_kwargs: dict[str, Any] = {
        "limit": AioHttpDefaults.LIMIT,
        "limit_per_host": AioHttpDefaults.LIMIT_PER_HOST,
        "ttl_dns_cache": AioHttpDefaults.TTL_DNS_CACHE,
        "use_dns_cache": AioHttpDefaults.USE_DNS_CACHE,
        "enable_cleanup_closed": AioHttpDefaults.ENABLE_CLEANUP_CLOSED,
        "force_close": AioHttpDefaults.FORCE_CLOSE,
        "keepalive_timeout": AioHttpDefaults.KEEPALIVE_TIMEOUT,
        "happy_eyeballs_delay": AioHttpDefaults.HAPPY_EYEBALLS_DELAY,
        "family": AioHttpDefaults.SOCKET_FAMILY,
        "socket_factory": socket_factory,
    }

    default_kwargs.update(kwargs)

    return aiohttp.TCPConnector(**default_kwargs)
```

### Connection Pool Configuration

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/clients/http/defaults.py`

```python
@dataclass(frozen=True)
class AioHttpDefaults:
    """Default values for aiohttp.ClientSession."""

    LIMIT = constants.AIPERF_HTTP_CONNECTION_LIMIT  # Maximum concurrent connections
    LIMIT_PER_HOST = 0  # Max per host (0 = use LIMIT)
    TTL_DNS_CACHE = 300  # DNS cache TTL in seconds
    USE_DNS_CACHE = True  # Enable DNS caching
    ENABLE_CLEANUP_CLOSED = False  # Disable closed connection cleanup
    FORCE_CLOSE = False  # Don't force-close connections
    KEEPALIVE_TIMEOUT = 300  # Keepalive timeout in seconds
    HAPPY_EYEBALLS_DELAY = None  # Disable happy eyeballs
    SOCKET_FAMILY = socket.AF_INET  # IPv4
```

**Key Parameters**:

- **LIMIT**: Controls total connection pool size
- **LIMIT_PER_HOST**: Per-host connection limit (0 means use LIMIT)
- **TTL_DNS_CACHE**: How long to cache DNS resolutions
- **KEEPALIVE_TIMEOUT**: How long to keep idle connections alive
- **FORCE_CLOSE**: Whether to close connections after each request

### Connection Reuse Strategy

```python
async with aiohttp.ClientSession(
    connector=self.tcp_connector,
    timeout=self.timeout,
    headers=headers,
    skip_auto_headers=[
        *list(headers.keys()),
        "User-Agent",
        "Accept-Encoding",
    ],
    connector_owner=False,  # Don't close connector when session closes
) as session:
    # Make request using shared connector
    async with session.request(method, url, data=data, headers=headers) as response:
        # Process response
        pass
```

**Why `connector_owner=False`**:
- Connector is owned by the client instance, not the session
- Allows connector reuse across multiple sessions
- Maintains connection pool across request batches
- Improves performance by avoiding connection recreation

## Request Execution

### Generic Request Method

```python
async def _request(
    self,
    method: str,
    url: str,
    headers: dict[str, str],
    data: str | None = None,
    **kwargs: Any,
) -> RequestRecord:
    """Generic request method that handles common logic for all HTTP methods.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: The URL to send the request to
        headers: Request headers
        data: Request payload (for POST, PUT, etc.)
        **kwargs: Additional arguments to pass to the request

    Returns:
        RequestRecord with the response data
    """
    self.debug(lambda: f"Sending {method} request to {url}")

    record: RequestRecord = RequestRecord(
        start_perf_ns=time.perf_counter_ns(),
    )

    try:
        # Make raw HTTP request with precise timing using aiohttp
        async with aiohttp.ClientSession(
            connector=self.tcp_connector,
            timeout=self.timeout,
            headers=headers,
            skip_auto_headers=[
                *list(headers.keys()),
                "User-Agent",
                "Accept-Encoding",
            ],
            connector_owner=False,
        ) as session:
            record.start_perf_ns = time.perf_counter_ns()
            async with session.request(
                method, url, data=data, headers=headers, **kwargs
            ) as response:
                record.status = response.status
                # Check for HTTP errors
                if response.status != 200:
                    error_text = await response.text()
                    record.error = ErrorDetails(
                        code=response.status,
                        type=response.reason,
                        message=error_text,
                    )
                    return record

                record.recv_start_perf_ns = time.perf_counter_ns()

                if (
                    method == "POST"
                    and response.content_type == "text/event-stream"
                ):
                    # Parse SSE stream with optimal performance
                    messages = await AioHttpSSEStreamReader(
                        response
                    ).read_complete_stream()
                    record.responses.extend(messages)
                else:
                    raw_response = await response.text()
                    record.end_perf_ns = time.perf_counter_ns()
                    record.responses.append(
                        TextResponse(
                            perf_ns=record.end_perf_ns,
                            content_type=response.content_type,
                            text=raw_response,
                        )
                    )
                record.end_perf_ns = time.perf_counter_ns()

    except Exception as e:
        record.end_perf_ns = time.perf_counter_ns()
        self.error(f"Error in aiohttp request: {e!r}")
        record.error = ErrorDetails(type=e.__class__.__name__, message=str(e))

    return record
```

### Timing Capture Points

The client captures timestamps at critical points:

```python
# 1. Request initiation
record = RequestRecord(start_perf_ns=time.perf_counter_ns())

# 2. Actual request start (after session creation)
record.start_perf_ns = time.perf_counter_ns()

# 3. First byte received
record.recv_start_perf_ns = time.perf_counter_ns()

# 4. Request completion
record.end_perf_ns = time.perf_counter_ns()
```

**Timing Metrics**:
- **Request Latency**: `end_perf_ns - start_perf_ns`
- **Network Latency**: `recv_start_perf_ns - start_perf_ns`
- **Processing Time**: `end_perf_ns - recv_start_perf_ns`

## Timing Precision

### Nanosecond Resolution

AIPerf uses `time.perf_counter_ns()` for maximum timing precision:

```python
import time

# Nanosecond precision (Python 3.7+)
start = time.perf_counter_ns()  # e.g., 1234567890123456789
# ... operation ...
end = time.perf_counter_ns()    # e.g., 1234567890223456789
duration = end - start           # 100000000 ns = 100 ms
```

**Why Nanoseconds**:
- Sub-millisecond precision for fast operations
- No floating-point rounding errors
- Integer arithmetic is exact
- Suitable for high-frequency measurements

### Timing Best Practices

```python
# Good: Capture timestamp immediately before operation
start_ns = time.perf_counter_ns()
result = await perform_operation()

# Bad: Delay between timestamp and operation
start_ns = time.perf_counter_ns()
await asyncio.sleep(0)  # Introduces delay
result = await perform_operation()

# Good: Capture timestamp immediately after operation
result = await perform_operation()
end_ns = time.perf_counter_ns()

# Bad: Operations between result and timestamp
result = await perform_operation()
process_result(result)  # Introduces delay
end_ns = time.perf_counter_ns()
```

### First Byte Timing

For streaming responses, AIPerf captures the first byte timestamp:

```python
# First byte of response received
record.recv_start_perf_ns = time.perf_counter_ns()

# Then process the stream
messages = await AioHttpSSEStreamReader(response).read_complete_stream()
```

This enables calculation of:
- **Time to First Byte (TTFB)**: Network + server processing time
- **Stream Processing Time**: Client-side parsing duration
- **Total Latency**: End-to-end request time

## Response Handling

### Content Type Detection

```python
async with session.request(method, url, data=data, headers=headers) as response:
    record.status = response.status

    if response.status != 200:
        # Handle error responses
        error_text = await response.text()
        record.error = ErrorDetails(
            code=response.status,
            type=response.reason,
            message=error_text,
        )
        return record

    record.recv_start_perf_ns = time.perf_counter_ns()

    if method == "POST" and response.content_type == "text/event-stream":
        # SSE streaming response
        messages = await AioHttpSSEStreamReader(response).read_complete_stream()
        record.responses.extend(messages)
    else:
        # Regular text response
        raw_response = await response.text()
        record.end_perf_ns = time.perf_counter_ns()
        record.responses.append(
            TextResponse(
                perf_ns=record.end_perf_ns,
                content_type=response.content_type,
                text=raw_response,
            )
        )
```

### Response Types

**TextResponse**: Non-streaming responses

```python
@dataclass
class TextResponse:
    perf_ns: int              # Timestamp when received
    content_type: str         # MIME type
    text: str                 # Response body
```

**SSEMessage**: Streaming responses

```python
@dataclass
class SSEMessage:
    perf_ns: int              # Timestamp of first byte
    packets: list[SSEField]   # Parsed SSE fields
```

## Error Handling

### HTTP Error Detection

```python
if response.status != 200:
    error_text = await response.text()
    record.error = ErrorDetails(
        code=response.status,
        type=response.reason,
        message=error_text,
    )
    return record
```

**Captured Information**:
- **code**: HTTP status code (404, 500, etc.)
- **type**: HTTP reason phrase ("Not Found", "Internal Server Error")
- **message**: Response body containing error details

### Exception Handling

```python
try:
    # Make request
    async with session.request(...) as response:
        # Process response
        pass

except Exception as e:
    record.end_perf_ns = time.perf_counter_ns()
    self.error(f"Error in aiohttp request: {e!r}")
    record.error = ErrorDetails(
        type=e.__class__.__name__,
        message=str(e)
    )
```

**Common Exception Types**:
- `aiohttp.ClientError`: Base for all aiohttp errors
- `aiohttp.ClientConnectorError`: Connection failures
- `aiohttp.ClientTimeout`: Timeout errors
- `asyncio.TimeoutError`: General async timeouts
- `aiohttp.ServerDisconnectedError`: Server closed connection

### Error Record Structure

```python
@dataclass
class ErrorDetails:
    code: int | None = None          # HTTP status code
    type: str | None = None          # Error type/class
    message: str | None = None       # Error message
```

All errors are captured in the RequestRecord, allowing:
- Error rate calculation
- Error type analysis
- Debugging failed requests
- SLA compliance tracking

## Header Management

### Skip Auto-Headers

AIPerf controls all headers explicitly:

```python
async with aiohttp.ClientSession(
    connector=self.tcp_connector,
    headers=headers,
    skip_auto_headers=[
        *list(headers.keys()),  # Skip duplicates
        "User-Agent",           # Custom User-Agent
        "Accept-Encoding",      # No automatic compression
    ],
) as session:
    # ...
```

**Why Skip Auto-Headers**:
- **Full Control**: Benchmarking requires exact header control
- **No Surprises**: Avoid automatic header injection
- **Reproducibility**: Same headers across all requests
- **Debugging**: Know exactly what was sent

### Common Headers

```python
headers = {
    "User-Agent": "aiperf/1.0",
    "Content-Type": "application/json",
    "Accept": "text/event-stream" if streaming else "application/json",
    "Authorization": f"Bearer {api_key}" if api_key else None,
}
```

## Performance Optimizations

### 1. Connection Pooling

Reuse connections across requests:

```python
# Create connector once
self.tcp_connector = create_tcp_connector()

# Use across multiple requests
for i in range(1000):
    record = await self._request("POST", url, headers, data)
```

**Benefits**:
- Avoid TCP handshake overhead
- Reduce DNS lookups
- Better resource utilization
- Lower latency

### 2. DNS Caching

Cache DNS resolutions:

```python
TTL_DNS_CACHE = 300  # 5 minutes
USE_DNS_CACHE = True
```

**Benefits**:
- Eliminate repeated DNS queries
- Consistent IP addresses
- Lower latency
- Reduced network load

### 3. Socket Reuse

Enable socket address reuse:

```python
SO_REUSEADDR = 1  # Enable reuse address
SO_REUSEPORT = 1  # Enable reuse port
```

**Benefits**:
- Faster socket binding
- Support for high connection rates
- Better resource utilization

### 4. Keep-Alive

Maintain persistent connections:

```python
SO_KEEPALIVE = 1        # Enable keepalive
TCP_KEEPIDLE = 60       # Start keepalive after 60s idle
TCP_KEEPINTVL = 30      # Keepalive interval: 30s
TCP_KEEPCNT = 1         # 1 failed probe = dead
```

**Benefits**:
- Detect dead connections
- Maintain long-lived streams
- Reduce reconnection overhead

### 5. Buffer Sizing

Optimize buffer sizes for streaming:

```python
SO_RCVBUF = 1024 * 1024 * 10  # 10MB receive buffer
SO_SNDBUF = 1024 * 1024 * 10  # 10MB send buffer
```

**Benefits**:
- Handle burst traffic
- Reduce packet loss
- Smooth streaming performance
- Better throughput

## Usage Patterns

### POST Request

```python
async def post_request(
    self,
    url: str,
    payload: str,
    headers: dict[str, str],
    **kwargs: Any,
) -> RequestRecord:
    """Send a streaming or non-streaming POST request."""
    return await self._request("POST", url, headers, data=payload, **kwargs)
```

**Example**:

```python
client = AioHttpClientMixin(model_endpoint)

record = await client.post_request(
    url="https://api.example.com/v1/chat/completions",
    payload='{"model": "gpt-4", "messages": [...]}',
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer sk-...",
    },
)

print(f"Status: {record.status}")
print(f"Latency: {(record.end_perf_ns - record.start_perf_ns) / 1_000_000} ms")
```

### GET Request

```python
async def get_request(
    self,
    url: str,
    headers: dict[str, str],
    **kwargs: Any,
) -> RequestRecord:
    """Send a GET request."""
    return await self._request("GET", url, headers, **kwargs)
```

**Example**:

```python
record = await client.get_request(
    url="https://api.example.com/v1/models",
    headers={"Authorization": "Bearer sk-..."},
)
```

### Cleanup

```python
async def close(self) -> None:
    """Close the client."""
    if self.tcp_connector:
        await self.tcp_connector.close()
        self.tcp_connector = None
```

**Usage**:

```python
client = AioHttpClientMixin(model_endpoint)
try:
    # Make requests
    record = await client.post_request(...)
finally:
    # Clean up
    await client.close()
```

## Integration with Clients

### Mixin Composition

```python
class OpenAIClientAioHttp(AioHttpClientMixin, AIPerfLoggerMixin, ABC):
    """Inference client for OpenAI based requests using aiohttp."""

    def __init__(self, model_endpoint: ModelEndpointInfo, **kwargs) -> None:
        super().__init__(model_endpoint, **kwargs)
        self.model_endpoint = model_endpoint

    async def send_request(
        self,
        model_endpoint: ModelEndpointInfo,
        payload: dict[str, Any],
    ) -> RequestRecord:
        """Send OpenAI request using aiohttp."""
        return await self.post_request(
            self.get_url(model_endpoint),
            json.dumps(payload),
            self.get_headers(model_endpoint),
        )
```

**Benefits of Mixin Design**:
- Composable functionality
- Clear separation of concerns
- Reusable across different client types
- Easy to test independently

## Benchmarking Considerations

### Timing Accuracy

**Critical Factors**:
1. Use `perf_counter_ns()` for high precision
2. Capture timestamps immediately before/after operations
3. Minimize code between operations and timestamps
4. Account for Python overhead (typically < 1 microsecond)

### Connection Overhead

**First Request**:
```
TCP Handshake (1 RTT)
SSL/TLS Handshake (2-3 RTT)
DNS Resolution (1 RTT)
Request + Response
```

**Subsequent Requests (with keep-alive)**:
```
Request + Response only
```

**Mitigation**:
- Use warmup requests
- Enable connection pooling
- Configure appropriate keepalive timeouts

### Concurrent Requests

```python
# Process multiple requests concurrently
async def process_batch(requests):
    tasks = [
        client.post_request(url, payload, headers)
        for url, payload, headers in requests
    ]
    return await asyncio.gather(*tasks)
```

**Considerations**:
- Connection pool size limits concurrency
- TCP congestion control affects performance
- System file descriptor limits matter
- Network bandwidth is shared

## Debugging

### Logging

```python
self.debug(lambda: f"Sending {method} request to {url}")
self.error(f"Error in aiohttp request: {e!r}")
```

**Log Levels**:
- **debug**: Detailed request information
- **info**: General status updates
- **error**: Error conditions

### Request Inspection

```python
# Inspect request record
print(f"Status: {record.status}")
print(f"Start: {record.start_perf_ns}")
print(f"End: {record.end_perf_ns}")
print(f"Latency: {record.end_perf_ns - record.start_perf_ns} ns")
print(f"Responses: {len(record.responses)}")
if record.error:
    print(f"Error: {record.error.type} - {record.error.message}")
```

### Connection Monitoring

```python
# Monitor connector stats
connector_info = client.tcp_connector._conns
print(f"Active connections: {len(connector_info)}")
```

## Key Takeaways

1. **High Performance**: Connection pooling, keepalive, and optimized buffers ensure maximum throughput

2. **Timing Precision**: Nanosecond-resolution timestamps enable accurate performance analysis

3. **Error Resilience**: Comprehensive error handling captures all failure modes

4. **Mixin Architecture**: Composable design enables reuse across client implementations

5. **Streaming Support**: Transparent handling of SSE streams with per-chunk timing

6. **Connection Management**: Shared connector pool across requests reduces overhead

7. **Header Control**: Explicit header management ensures reproducible benchmarking

8. **Async/Await**: Non-blocking I/O enables high concurrency

9. **Resource Cleanup**: Proper cleanup prevents resource leaks

10. **Production-Ready**: Battle-tested optimizations for real-world workloads

## What's Next

- **Chapter 24: OpenAI Client** - Learn how the HTTP client is specialized for OpenAI endpoints
- **Chapter 25: SSE Stream Handling** - Explore SSE parsing with precise timing
- **Chapter 26: TCP Optimizations** - Deep dive into socket-level optimizations

---

**Remember**: The HTTP client is the foundation for accurate benchmarking. Precise timing, efficient connection management, and robust error handling are essential for reliable performance measurement.
