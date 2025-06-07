<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# OpenAI Client AioHttp Performance Optimizations

This document outlines the performance optimizations implemented in the `OpenAIBackendClientAioHttp` class for maximum performance and accurate timing measurements in benchmarking scenarios.

## Key Performance Optimizations

### 1. Connection Pool Management
- **Pre-configured TCPConnector**: Maintains persistent connections for reduced latency
- **Connection Pool Size**: 100 total connections, 30 per host
- **Keep-alive Optimization**: Connections remain open between requests
- **DNS Caching**: 300-second TTL to reduce DNS lookup overhead

### 2. Network Optimizations
- **IPv4-only Mode**: Forces IPv4 (`socket.AF_INET`) for consistent performance
- **Happy Eyeballs Disabled**: Eliminates dual-stack connection delay
- **Connection Cleanup**: Automatic cleanup of closed connections

### 3. HTTP Request Optimizations
- **Custom JSON Serializer**: Uses `json.dumps` directly for faster serialization
- **Minimal Headers**: Skips auto-generated headers that aren't needed
- **Optimal Chunk Size**: 8KB chunks for efficient streaming data processing

### 4. Precise Timing Measurements
- **Nanosecond Precision**: Uses `time.perf_counter_ns()` for sub-millisecond accuracy
- **Multiple Timing Points**: Captures REQUEST_START, SEND_START, SEND_END, RECV_START, RECV_END, REQUEST_END
- **Per-chunk Timestamps**: Each streaming response chunk gets its own timestamp
- **Minimal Timing Overhead**: Timing calls placed strategically to minimize impact on measurements

### 5. SSE Stream Processing
- **Efficient Buffering**: Processes complete lines to handle SSE format correctly
- **Error Resilience**: Graceful handling of encoding issues and malformed data
- **Early Termination**: Proper detection of `[DONE]` markers for stream completion

### 6. Memory Management
- **Async Context Management**: Proper cleanup of connections and resources
- **Buffer Optimization**: Efficient string concatenation and splitting for SSE parsing
- **Exception Safety**: Ensures resources are freed even on errors

## Usage

```python
from aiperf.backend.openai_client_aiohttp import OpenAIBackendClientAioHttp

# Register with factory using the specialized backend type
client = BackendClientFactory.create_instance(
    BackendClientType.OPENAI,
    config=OpenAIBackendClientConfig(...)
)

# Use as async context manager for proper cleanup
async with client:
    record = await client.send_request(endpoint, payload)
```

## Benchmarking Benefits

- **Lower Latency**: Connection reuse and optimized network settings
- **Higher Accuracy**: Nanosecond-precision timing measurements
- **Better Throughput**: Efficient streaming and buffering
- **Consistent Performance**: IPv4-only mode eliminates network variability
- **Resource Efficiency**: Proper cleanup and connection management

