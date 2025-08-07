<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# ZMQ Dealer-Router Deadlock Analysis and Solutions

## Problem Summary

The ZMQ dealer-router implementation experiences deadlocks under high concurrency due to several architectural issues in the communication layer.

## Root Cause Analysis

### 1. Queue Saturation Deadlock (Primary Issue)

**Location**: `aiperf/common/comms/zmq/dealer_request_client.py`

**Problem**:
- DEALER clients use bounded queues (100K items each) for send/receive operations
- Under high load, these queues fill up and block indefinitely
- The code used `await queue.put()` without timeouts, causing permanent blocking

**Deadlock Scenario**:
```
High concurrent requests → Receive queue fills →
Socket receiver blocks → No responses processed →
Send queue fills → Request sending blocks →
Complete system deadlock
```

### 2. Router Response Buffer Overflow

**Location**: `aiperf/common/comms/zmq/router_reply_client.py`

**Problem**:
- Router sends responses via `socket.send_multipart()` without timeout
- If DEALER clients can't consume responses fast enough, Router blocks
- Creates backpressure that propagates through the entire system

### 3. ZMQ Socket Buffer Limits Missing

**Location**: `aiperf/common/comms/zmq/zmq_base_client.py`

**Problem**:
- No High Water Mark (HWM) configured on ZMQ sockets
- ZMQ internal buffers can grow unbounded and cause blocking
- `IMMEDIATE = 1` prevents queuing but doesn't limit buffer sizes

### 4. Request Future Memory Leaks

**Location**: `aiperf/common/comms/zmq/dealer_request_client.py`

**Problem**:
- Request futures accumulate in memory without cleanup
- Under high load with failures, stale futures consume memory
- Can lead to gradual system degradation

## Solutions Implemented

### 1. Queue Timeout Protection

**Changes**: Added 5-second timeouts to all queue operations

```python
# Before (blocking forever)
await self._receive_queue.put(message)

# After (with timeout and graceful degradation)
try:
    await asyncio.wait_for(self._receive_queue.put(message), timeout=5.0)
except asyncio.TimeoutError:
    self.error("Queue blocked, dropping message to prevent deadlock")
    continue  # Graceful degradation instead of deadlock
```

### 2. Response Sending Timeout

**Changes**: Added timeout to Router response sending

```python
# Before (blocking send)
await self.socket.send_multipart([*routing_envelope, response.model_dump_json().encode()])

# After (with timeout)
await asyncio.wait_for(
    self.socket.send_multipart([*routing_envelope, response.model_dump_json().encode()]),
    timeout=5.0
)
```

### 3. ZMQ Socket Buffer Limits

**Changes**: Added HWM configuration to all ZMQ sockets

```python
# Prevent unbounded buffer growth
self.socket.setsockopt(zmq.SNDHWM, 10000)  # Send buffer limit
self.socket.setsockopt(zmq.RCVHWM, 10000)  # Receive buffer limit
```

### 4. Automatic Future Cleanup

**Changes**: Added background task to clean up stale request futures

```python
@background_task(immediate=False, interval=30.0)
async def _cleanup_stale_futures(self) -> None:
    """Clean up futures older than 5 minutes or already done"""
```

## Performance Impact

### Positive Effects:
- **Eliminates deadlocks** under high concurrency
- **Prevents memory leaks** from accumulated futures
- **Enables graceful degradation** instead of system freeze
- **Maintains system responsiveness** during overload

### Trade-offs:
- **Message loss possible** during extreme overload (better than deadlock)
- **Additional CPU overhead** from timeout monitoring and cleanup tasks
- **Slightly higher memory usage** from timestamp tracking

## Configuration Recommendations

### For High-Concurrency Environments:

1. **Monitor queue utilization**:
   ```python
   # Add monitoring for queue sizes
   if queue.qsize() > 0.8 * queue.maxsize:
       self.warning("Queue approaching capacity")
   ```

2. **Tune timeout values** based on latency requirements:
   - Lower timeouts (1-2s) for real-time systems
   - Higher timeouts (10-15s) for batch processing

3. **Adjust HWM values** based on memory constraints:
   ```python
   # For memory-constrained environments
   self.socket.setsockopt(zmq.SNDHWM, 1000)
   self.socket.setsockopt(zmq.RCVHWM, 1000)
   ```

## Testing Strategy

### Load Testing:
1. **Gradually increase concurrency** from 1 to 1000+ concurrent requests
2. **Monitor for timeouts** in logs (indicates system under stress)
3. **Verify graceful degradation** - system should slow down, not freeze
4. **Check memory growth** - should remain bounded over time

### Stress Testing:
1. **Overwhelm the system** intentionally to verify timeout behavior
2. **Network partition simulation** to test cleanup mechanisms
3. **Resource exhaustion scenarios** to validate graceful failure modes

## Monitoring and Alerting

### Key Metrics to Track:
- Queue timeout frequency (should be rare in normal operation)
- Response send timeout frequency
- Request future cleanup count
- Queue size high-water marks
- Memory usage patterns

### Alert Thresholds:
- **Warning**: >1% of operations timing out
- **Critical**: >5% of operations timing out
- **Emergency**: >10% of operations timing out (indicates system overload)

## Future Improvements

1. **Adaptive queue sizing** based on system load
2. **Circuit breaker pattern** for automatic load shedding
3. **Request prioritization** for critical vs. non-critical requests
4. **Metrics collection** for real-time system health monitoring
5. **Backpressure propagation** to upstream request sources
