<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# StreamingTokenChunks - SSE Data Payload Concept

## Overview
Successfully modified the streaming HTTP client to use **StreamingTokenChunks** instead of **StreamingChunks**, representing SSE (Server-Sent Events) data payloads with timing handled through RequestTimers indices.

## Key Changes Made

### 1. StreamingTokenChunk Structure
- **Removed**: `timestamp_ns` field (no more embedded timestamps)
- **Removed**: `chunk_index` field
- **Kept**: `data` (SSE payload content)
- **Kept**: `size_bytes` (payload size)
- **Kept**: `token_index` (relates to RequestTimers)

### 2. RequestTimers Integration
- StreamingTokenChunks relate to RequestTimers through **token_index**
- Timing captured via `capture_token_start()` and `capture_token_end()`
- Perfect 1:1 relationship between tokens and timer measurements
- Access timing via `get_token_timing(token_index)`

### 3. Code Changes

#### Rust Files Modified:
- `src/request.rs`: StreamingChunk → StreamingToken
- `src/client.rs`: Updated streaming processing logic
- `src/lib.rs`: Export StreamingTokenChunk instead of StreamingChunk
- `src/timers.rs`: No changes (already supported token timing)

#### Python Files Modified:
- `python/aiperf_streaming/__init__.py`: Updated imports
- `python/aiperf_streaming/models.py`: StreamingChunkModel → StreamingTokenChunkModel

### 4. Functional Improvements

#### StreamingTokenChunk Features:
```rust
pub struct StreamingTokenChunk {
    pub data: String,           // SSE payload content
    pub size_bytes: usize,      // Payload size
    pub token_index: usize,     // Index for RequestTimers
}
```

#### Timing Access:
```python
# Get timing for specific token
token_timing = request.get_token_timing(token_index)

# Get all token durations from RequestTimers
token_durations = timers.get_token_durations_ns()

# Perfect relationship verification
assert request.token_count == timers.token_starts_count()
assert request.token_count == timers.token_ends_count()
```

### 5. Test Results

The test demonstrates:
- ✅ **Perfect 1:1 relationship** between tokens and timers
- ✅ **Nanosecond precision** timing (e.g., 0.005 ms, 0.002 ms)
- ✅ **SSE data payload** representation
- ✅ **No embedded timestamps** in tokens
- ✅ **RequestTimers integration** for all timing operations

#### Example Output:
```
🔗 Token-Timer Relationship:
  Tokens in request: 2
  Token starts in timer: 2
  Token ends in timer: 2
  ✅ Perfect 1:1 relationship between tokens and timers!

🔤 Token Statistics:
     Token count: 2
     Average duration: 0.003 ms
     Min duration: 0.002 ms
     Max duration: 0.005 ms
```

## Benefits Achieved

1. **Clean Separation**: Tokens store data, RequestTimers handle timing
2. **SSE Focused**: Tokens represent actual SSE data payloads
3. **Precise Timing**: Nanosecond accuracy through RequestTimers
4. **Type Safety**: No more raw timestamp handling in tokens
5. **Efficient Storage**: HashMap + vectors in RequestTimers for O(1) lookups

## Usage Pattern

```python
# Create request
request = StreamingRequest(url="https://api.example.com/stream")

# Execute with timing
timers = client.stream_request(request)

# Or get both request and timers
request, timers = client.stream_request_with_details(request)

# Access tokens (SSE payloads)
for i in range(request.token_count):
    token = request.get_token(i)
    timing = request.get_token_timing(i)
    print(f"Token {i}: {token.size_bytes} bytes, {timing/1_000_000:.3f} ms")

# Analyze timing patterns
token_durations = timers.get_token_durations_ns()
```

## Architecture

```
StreamingTokenChunk (SSE Data)     RequestTimers (Timing)
├── data: String             ├── timestamps: HashMap<Kind, Instant>
├── size_bytes: usize        ├── token_starts: Vec<Instant>
├── token_index: usize ──────├── token_ends: Vec<Instant>
                             └── base_time: Instant

Perfect 1:1 relationship via token_index
```

This design provides extreme accuracy for AI performance analysis while maintaining clean, type-safe interfaces focused on the SSE data payload concept.
