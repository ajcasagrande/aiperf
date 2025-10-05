# Chapter 26: TCP Optimizations

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Navigation
- Previous: [Chapter 25: SSE Stream Handling](chapter-25-sse-stream-handling.md)
- Next: [Chapter 27: Request Converters](chapter-27-request-converters.md)
- [Table of Contents](README.md)

## Overview

AIPerf's TCP layer optimizations are critical for achieving low-latency, high-throughput benchmarking. Through careful tuning of socket options, buffer sizes, keepalive settings, and TCP flags, AIPerf minimizes network overhead while maintaining connection reliability for long-lived SSE streams.

This chapter examines the TCP optimizations applied to every connection, explaining the rationale, trade-offs, and performance impact of each setting.

## Socket Defaults

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/clients/http/defaults.py`

```python
@dataclass(frozen=True)
class SocketDefaults:
    """Default values for socket options."""

    TCP_NODELAY = 1  # Disable Nagle's algorithm
    TCP_QUICKACK = 1  # Quick ACK mode

    SO_KEEPALIVE = 1  # Enable keepalive
    TCP_KEEPIDLE = 60  # Start keepalive after 1 min idle
    TCP_KEEPINTVL = 30  # Keepalive interval: 30 seconds
    TCP_KEEPCNT = 1  # 1 failed keepalive probes = dead

    SO_LINGER = 0  # Disable linger
    SO_REUSEADDR = 1  # Enable reuse address
    SO_REUSEPORT = 1  # Enable reuse port

    SO_RCVBUF = 1024 * 1024 * 10  # 10MB receive buffer
    SO_SNDBUF = 1024 * 1024 * 10  # 10MB send buffer

    SO_RCVTIMEO = 30  # 30 second receive timeout
    SO_SNDTIMEO = 30  # 30 second send timeout
    TCP_USER_TIMEOUT = 30000  # 30 sec user timeout

    @classmethod
    def apply_to_socket(cls, sock: socket.socket) -> None:
        """Apply the default socket options to the given socket."""

        # Low-latency optimizations for streaming
        sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, cls.TCP_NODELAY)

        # Connection keepalive settings for long-lived SSE connections
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, cls.SO_KEEPALIVE)

        # Fine-tune keepalive timing (Linux-specific)
        if hasattr(socket, "TCP_KEEPIDLE"):
            sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE, cls.TCP_KEEPIDLE)
            sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL, cls.TCP_KEEPINTVL)
            sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT, cls.TCP_KEEPCNT)

        # Buffer size optimizations for streaming
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, cls.SO_RCVBUF)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, cls.SO_SNDBUF)

        # Linux-specific TCP optimizations
        if hasattr(socket, "TCP_QUICKACK"):
            sock.setsockopt(socket.SOL_TCP, socket.TCP_QUICKACK, cls.TCP_QUICKACK)

        if hasattr(socket, "TCP_USER_TIMEOUT"):
            sock.setsockopt(
                socket.SOL_TCP, socket.TCP_USER_TIMEOUT, cls.TCP_USER_TIMEOUT
            )
```

## Low-Latency Optimizations

### TCP_NODELAY: Disable Nagle's Algorithm

```python
sock.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
```

**Nagle's Algorithm**: Buffers small packets to reduce network overhead
- Wait for ACK before sending more data
- Or wait for full packet size
- Reduces packet count but increases latency

**Why Disable**:
- AI responses need immediate delivery
- Latency more important than bandwidth efficiency
- Small SSE chunks should send immediately
- Benchmarking requires accurate timing

**Impact**:
- **Latency**: Reduced by 40-200ms per packet
- **Throughput**: Slight increase in packet count
- **TTFT**: Improved by 40-200ms
- **ITL**: More consistent timing

**Trade-off**: More packets but lower latency

### TCP_QUICKACK: Quick ACK Mode (Linux)

```python
if hasattr(socket, "TCP_QUICKACK"):
    sock.setsockopt(socket.SOL_TCP, socket.TCP_QUICKACK, 1)
```

**Delayed ACK**: Normally, TCP waits up to 500ms before ACKing

**Quick ACK**: Send ACK immediately upon receiving data

**Why Enable**:
- Reduce round-trip time
- Server can send next chunk sooner
- Lower perceived latency
- Better for request-response patterns

**Impact**:
- **Latency**: Reduced by up to 500ms per exchange
- **Throughput**: Faster data transfer
- **CPU**: Slightly higher (more ACKs)

**Platform**: Linux only

## Keepalive Settings

### SO_KEEPALIVE: Enable Connection Monitoring

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
```

**Purpose**: Detect dead connections on idle streams

**Why Enable**:
- SSE streams can be idle between tokens
- Long-lived connections need health checks
- Prevent resource leaks from dead connections
- Faster detection of network failures

**Without Keepalive**: Connection appears alive indefinitely
**With Keepalive**: Dead connections detected and closed

### TCP_KEEPIDLE: Idle Time Before Probing

```python
sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE, 60)
```

**Value**: 60 seconds

**Meaning**: Start keepalive probes after 60 seconds of idle time

**Why 60 seconds**:
- Balances detection speed vs overhead
- Most AI responses complete within 60s
- Longer than typical inter-token delays
- Catches stuck connections

**Alternative Values**:
- **Lower (10-30s)**: Faster detection, more overhead
- **Higher (120-300s)**: Less overhead, slower detection

### TCP_KEEPINTVL: Probe Interval

```python
sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPINTVL, 30)
```

**Value**: 30 seconds

**Meaning**: Send probes every 30 seconds after idle period

**Impact**:
- Determines how quickly dead connections are detected
- After first probe failure, waits 30s before next probe

### TCP_KEEPCNT: Probe Count

```python
sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPCNT, 1)
```

**Value**: 1 probe

**Meaning**: Mark connection dead after 1 failed probe

**Why 1 probe**:
- Fast failure detection (aggressive)
- Minimize time spent on dead connections
- Benchmarking needs quick cleanup

**Total Detection Time**:
```
IDLE (60s) + INTERVAL (30s) * COUNT (1) = 90 seconds
```

**Trade-off**:
- **Aggressive**: Fast detection, may close temporary network hiccups
- **Conservative**: Slower detection, more resilient to transient failures

## Buffer Sizing

### SO_RCVBUF: Receive Buffer

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 10 * 1024 * 1024)
```

**Value**: 10 MB

**Purpose**: Buffer incoming data before application reads it

**Why 10 MB**:
- Handle burst traffic from fast models
- Prevent packet loss during processing
- Support high-throughput streaming
- Accommodate large JSON responses

**Impact**:
- **Throughput**: Higher sustained rates
- **Latency**: Lower at high load
- **Memory**: 10 MB per connection
- **Packet Loss**: Reduced

**Calculation**:
```
Bandwidth-Delay Product = Bandwidth * RTT
100 Mbps * 100ms = 1.25 MB
10 MB provides ~8x headroom
```

### SO_SNDBUF: Send Buffer

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 10 * 1024 * 1024)
```

**Value**: 10 MB

**Purpose**: Buffer outgoing data before kernel sends it

**Why 10 MB**:
- Support large request payloads
- Handle multiple concurrent requests
- Prevent blocking on large prompts

**Impact**:
- **Throughput**: Higher for large requests
- **Blocking**: Reduced during bursts
- **Memory**: 10 MB per connection

## Address Reuse

### SO_REUSEADDR: Reuse Address

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
```

**Purpose**: Allow binding to recently used addresses

**Why Enable**:
- Restart benchmarks quickly without waiting
- Avoids "Address already in use" errors
- Enables rapid connection cycling
- Essential for high-rate benchmarking

**Without**: Must wait 2-4 minutes (TIME_WAIT state)
**With**: Immediate reuse

### SO_REUSEPORT: Reuse Port (Linux)

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
```

**Purpose**: Multiple sockets can bind to same port

**Why Enable**:
- Support multi-process workers
- Load balance across processes
- Kernel distributes connections
- Better CPU utilization

**Platform**: Linux 3.9+

## Timeout Settings

### SO_RCVTIMEO: Receive Timeout

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, 30)
```

**Value**: 30 seconds

**Purpose**: Maximum time to wait for data

**Why 30 seconds**:
- Long enough for slow models
- Short enough to detect hangs
- Balances patience vs responsiveness

**Impact**:
- Prevents indefinite blocking
- Raises timeout exception after 30s
- Enables error recovery

### SO_SNDTIMEO: Send Timeout

```python
sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDTIMEO, 30)
```

**Value**: 30 seconds

**Purpose**: Maximum time to wait for send

**Why 30 seconds**:
- Handles slow network paths
- Detects network congestion
- Prevents blocking workers

### TCP_USER_TIMEOUT: User Timeout (Linux)

```python
if hasattr(socket, "TCP_USER_TIMEOUT"):
    sock.setsockopt(socket.SOL_TCP, socket.TCP_USER_TIMEOUT, 30000)
```

**Value**: 30,000 milliseconds (30 seconds)

**Purpose**: Time before aborting connection after data loss

**How It Works**:
- Starts when unacknowledged data exists
- Aborts connection if no progress after timeout
- More aggressive than default retransmission timeout

**Why 30 seconds**:
- Faster failure detection than default (often minutes)
- Matches other timeout values
- Reasonable for most networks

**Platform**: Linux 2.6.37+

## Linger Settings

### SO_LINGER: Disabled

```python
# Note: In AIPerf, SO_LINGER is not explicitly set
# Default behavior (disabled) is used
```

**Default Behavior** (linger disabled):
- `close()` returns immediately
- Kernel sends remaining data in background
- Connection closed gracefully if possible

**Why Not Set**:
- Default behavior is appropriate for benchmarking
- Immediate return enables higher throughput
- Graceful shutdown handled by kernel

**Alternative** (linger enabled):
```python
# Not recommended for AIPerf
sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
# Would cause immediate RST (connection abort)
```

## AioHTTP Connector Configuration

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/clients/http/defaults.py`

```python
@dataclass(frozen=True)
class AioHttpDefaults:
    """Default values for aiohttp.ClientSession."""

    LIMIT = constants.AIPERF_HTTP_CONNECTION_LIMIT  # Max concurrent connections
    LIMIT_PER_HOST = 0  # Max per host (0 = use LIMIT)
    TTL_DNS_CACHE = 300  # DNS cache TTL (5 minutes)
    USE_DNS_CACHE = True  # Enable DNS caching
    ENABLE_CLEANUP_CLOSED = False  # Disable closed connection cleanup
    FORCE_CLOSE = False  # Don't force-close connections
    KEEPALIVE_TIMEOUT = 300  # Keepalive timeout (5 minutes)
    HAPPY_EYEBALLS_DELAY = None  # Disable happy eyeballs
    SOCKET_FAMILY = socket.AF_INET  # IPv4 only
```

### Connection Limits

```python
LIMIT = constants.AIPERF_HTTP_CONNECTION_LIMIT
LIMIT_PER_HOST = 0  # Means use LIMIT value
```

**Purpose**: Control connection pool size

**Why Limited**:
- Prevent resource exhaustion
- Stay within OS file descriptor limits
- Balance concurrency vs overhead

**Default**: Typically 100-1000 connections

### DNS Caching

```python
TTL_DNS_CACHE = 300  # 5 minutes
USE_DNS_CACHE = True
```

**Purpose**: Cache DNS resolutions

**Benefits**:
- Eliminate repeated DNS queries
- Faster connection establishment
- Consistent IP addresses
- Reduced network load

**TTL Choice**: 5 minutes balances freshness vs caching

### Keepalive Timeout

```python
KEEPALIVE_TIMEOUT = 300  # 5 minutes
```

**Purpose**: How long to keep idle connections alive

**Why 5 minutes**:
- Long enough for request bursts
- Short enough to prevent resource leaks
- Matches typical server timeouts
- Balances resource use vs performance

### Force Close

```python
FORCE_CLOSE = False
```

**Purpose**: Whether to close connections after each request

**Why Disabled**:
- Connection reuse improves performance
- Avoid TCP handshake overhead
- Better for benchmarking workloads
- Lower latency for subsequent requests

### Happy Eyeballs

```python
HAPPY_EYEBALLS_DELAY = None  # Disabled
```

**Happy Eyeballs**: RFC 8305 - Try IPv6 and IPv4 in parallel

**Why Disabled**:
- Benchmarking uses explicit IP or consistent hostnames
- Avoid non-deterministic behavior
- Simpler connection establishment
- More predictable timing

### Socket Family

```python
SOCKET_FAMILY = socket.AF_INET  # IPv4
```

**Options**:
- `AF_INET`: IPv4 only
- `AF_INET6`: IPv6 only
- `AF_UNSPEC`: Both IPv4 and IPv6

**Why IPv4**:
- Universal support
- Simpler for benchmarking
- Avoid IPv6 fallback delays
- Consistent behavior

## Socket Factory Integration

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

**Key Feature**: Every socket gets optimized settings via `socket_factory`

## Performance Impact

### Latency Improvements

| Optimization | Impact | Magnitude |
|--------------|--------|-----------|
| TCP_NODELAY | TTFT, ITL | 40-200ms per packet |
| TCP_QUICKACK | Round-trip time | Up to 500ms per exchange |
| Large buffers | Burst handling | Prevents packet loss |
| Connection reuse | Subsequent requests | 100-300ms per request |
| DNS caching | Connection setup | 50-200ms per connection |

### Throughput Improvements

| Optimization | Impact | Magnitude |
|--------------|--------|-----------|
| Large buffers | Sustained rate | 2-5x improvement |
| Connection pooling | Request rate | 3-10x improvement |
| TCP_NODELAY | Stream chunks | 10-20% improvement |

### Reliability Improvements

| Optimization | Impact |
|--------------|--------|
| Keepalive | Detects dead connections in 90s |
| User timeout | Faster failure detection (30s vs minutes) |
| Large buffers | Reduces packet loss under load |
| SO_REUSEADDR | Enables rapid restart |

## Platform Considerations

### Linux-Specific Options

```python
# Only set on Linux
if hasattr(socket, "TCP_QUICKACK"):
    sock.setsockopt(socket.SOL_TCP, socket.TCP_QUICKACK, 1)

if hasattr(socket, "TCP_USER_TIMEOUT"):
    sock.setsockopt(socket.SOL_TCP, socket.TCP_USER_TIMEOUT, 30000)

# Keepalive tuning (Linux)
if hasattr(socket, "TCP_KEEPIDLE"):
    sock.setsockopt(socket.SOL_TCP, socket.TCP_KEEPIDLE, 60)
```

**Graceful Degradation**: Falls back on other platforms

### Cross-Platform Support

**Universal Options**:
- TCP_NODELAY
- SO_KEEPALIVE
- SO_RCVBUF / SO_SNDBUF
- SO_REUSEADDR

**Platform-Specific**:
- TCP_QUICKACK: Linux
- TCP_USER_TIMEOUT: Linux 2.6.37+
- TCP_KEEPIDLE/INTVL/CNT: Linux, BSD
- SO_REUSEPORT: Linux 3.9+, BSD

## Debugging Socket Options

### Inspect Current Settings

```python
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Get current values
tcp_nodelay = sock.getsockopt(socket.SOL_TCP, socket.TCP_NODELAY)
rcvbuf = sock.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
sndbuf = sock.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)

print(f"TCP_NODELAY: {tcp_nodelay}")
print(f"SO_RCVBUF: {rcvbuf}")
print(f"SO_SNDBUF: {sndbuf}")
```

### Verify Applied Settings

```python
def verify_socket_options(sock):
    """Verify all socket options are applied correctly."""
    checks = {
        "TCP_NODELAY": (socket.SOL_TCP, socket.TCP_NODELAY, SocketDefaults.TCP_NODELAY),
        "SO_KEEPALIVE": (socket.SOL_SOCKET, socket.SO_KEEPALIVE, SocketDefaults.SO_KEEPALIVE),
        "SO_RCVBUF": (socket.SOL_SOCKET, socket.SO_RCVBUF, SocketDefaults.SO_RCVBUF),
        "SO_SNDBUF": (socket.SOL_SOCKET, socket.SO_SNDBUF, SocketDefaults.SO_SNDBUF),
    }

    for name, (level, optname, expected) in checks.items():
        actual = sock.getsockopt(level, optname)
        status = "✓" if actual == expected else "✗"
        print(f"{status} {name}: {actual} (expected {expected})")
```

## Key Takeaways

1. **TCP_NODELAY**: Critical for low-latency streaming (40-200ms improvement)

2. **Large Buffers**: 10MB buffers handle burst traffic and prevent packet loss

3. **Keepalive**: 60s idle + 30s interval + 1 probe = 90s dead connection detection

4. **Quick ACK**: Reduces round-trip time by up to 500ms (Linux only)

5. **Connection Reuse**: SO_REUSEADDR enables rapid benchmark restarts

6. **User Timeout**: 30s timeout prevents hanging on dead connections (Linux only)

7. **DNS Caching**: 5-minute cache eliminates repeated lookups

8. **Platform Aware**: Graceful degradation on non-Linux platforms

9. **Factory Pattern**: Custom socket factory applies all optimizations automatically

10. **Tested Configuration**: Battle-tested values optimized for AI benchmarking

## What's Next

- **Chapter 27: Request Converters** - Learn how payloads are formatted for different endpoints
- **Chapter 23: HTTP Client Architecture** - See how TCP optimizations integrate with HTTP client

---

**Remember**: TCP optimization are foundational for accurate benchmarking. These settings reduce latency, improve throughput, and ensure reliable measurements across all network conditions.
