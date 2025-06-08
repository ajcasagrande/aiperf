<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# OpenAI Client HttpX Performance Optimizations

This document outlines the performance optimizations implemented in the `OpenAIBackendClientHttpx` class for maximum performance and accurate timing measurements in benchmarking scenarios.

## Key Performance Optimizations

### 1. Pre-configured Client with Connection Pooling
- **Persistent Client Instance**: Single httpx.AsyncClient reused across requests instead of creating new clients
- **Connection Pool Limits**: 100 keep-alive connections, 200 total connections maximum
- **Keep-alive Optimization**: 30-second keep-alive expiry for connection reuse
- **Connection Reuse**: Eliminates connection setup overhead for subsequent requests

### 2. HTTP/2 Support and Network Optimizations
- **HTTP/2 Enabled**: Automatic protocol negotiation for better multiplexing and performance
- **Compression**: gzip and deflate encoding enabled for reduced bandwidth usage
- **Keep-alive Headers**: Explicit connection keep-alive instructions
- **Redirect Disabled**: Faster responses by preventing redirect following

### 3. Granular Timeout Configuration
- **Connect Timeout**: 5-second connection establishment limit
- **Read Timeout**: Configurable based on client settings
- **Write Timeout**: 5-second write operation limit
- **Pool Timeout**: 1-second pool acquisition timeout

### 4. Optimized Streaming and Buffering
- **Larger Chunk Sizes**: 16KB default chunk size (vs 8KB) for better throughput
- **Efficient Buffering**: Optimized string operations for SSE parsing
- **Memory-efficient Processing**: Minimal memory allocations during streaming

### 5. Precise Timing Measurements
- **Nanosecond Precision**: Uses `time.perf_counter_ns()` for sub-millisecond accuracy
- **Multiple Timing Points**: REQUEST_START, SEND_START, SEND_END, RECV_START, RECV_END, REQUEST_END
- **Per-chunk Timestamps**: Individual timestamps for each response chunk
- **Minimal Timing Overhead**: Strategic placement to avoid measurement interference

### 6. Environment and Security Optimizations
- **Environment Trust Disabled**: Faster startup by not reading proxy/auth environment variables
- **SSL Verification Maintained**: Security preserved while optimizing handshake
- **Minimal Header Processing**: Only essential headers included

## Implementation Details

### Pre-configured Client Setup
```python
def _configure_httpx_client(self):
    limits = httpx.Limits(
        max_keepalive_connections=100,
        max_connections=200,
        keepalive_expiry=30.0,
    )

    timeout = httpx.Timeout(
        connect=5.0,
        read=self.client_config.timeout_ms / 1000.0,
        write=5.0,
        pool=1.0,
    )

    self._httpx_client = httpx.AsyncClient(
        limits=limits,
        timeout=timeout,
        http2=True,
        follow_redirects=False,
        verify=True,
        trust_env=False,
    )
```

### Optimized Request Headers
```python
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}",
    "Accept": "text/event-stream",
    "Connection": "keep-alive",
    "Accept-Encoding": "gzip, deflate",
}
```

### Enhanced Streaming Processing
```python
async def aiter_raw_optimized(self, response, chunk_size=16384):
    # Larger chunk size for better performance
    chunker = ByteChunker(chunk_size=chunk_size)
    # ... optimized processing
```

## Performance Benefits

### Latency Improvements
- **Connection Reuse**: 50-200ms saved per request by avoiding TCP handshake
- **HTTP/2**: Reduced head-of-line blocking and better multiplexing
- **Persistent Client**: Eliminates client initialization overhead

### Throughput Enhancements
- **Larger Chunks**: Better CPU utilization and reduced syscall overhead
- **Compression**: Reduced network bandwidth usage
- **Keep-alive**: Multiple requests over single connection

### Timing Accuracy
- **Nanosecond Resolution**: Sub-millisecond timing precision
- **Multiple Measurement Points**: Detailed breakdown of request phases
- **Minimal Overhead**: Timing code optimized to not affect measurements

## Usage

```python
from aiperf.backend.openai_client_httpx import OpenAIBackendClientHttpx

# The client automatically uses optimized settings
client = OpenAIBackendClientHttpx(config)

# Use as async context manager for proper cleanup
async with client:
    record = await client.send_request(endpoint, payload)
```

## Comparison with Standard HttpX Usage

### Standard httpx (per-request client):
```python
async with httpx.AsyncClient() as client:
    response = await client.post(url, json=data)
```

### Optimized version:
- Pre-configured connection pool
- HTTP/2 enabled by default
- Persistent connections across requests
- Optimized timeouts and limits
- Enhanced error handling and resource management

## Benchmarking Results

Expected improvements over naive httpx usage:
- **20-40% lower latency** for subsequent requests due to connection reuse
- **Higher accuracy timing** with nanosecond precision measurements
- **Better resource utilization** through optimized connection pooling
- **Improved error resilience** with proper timeout configuration
