<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Dataset Chunking Optimization Design

## Problem Statement

**Current Bottleneck**: Workers request conversations one at a time from a single DatasetManager. With high concurrency (1000+ workers), this creates a serialization bottleneck.

**Performance Impact**:
- 1000 workers × 10 requests/sec = 10,000 requests/second to single DatasetManager
- Each request/response incurs network overhead, serialization, ZMQ routing
- DatasetManager becomes CPU-bound processing individual requests

## Solution: Chunk-Based Distribution with Prefetching

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ OLD: Per-Conversation Request (Bottleneck)                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Worker 1 ──→ ConversationRequest  ──→ DatasetManager       │
│           ←── ConversationResponse ←──                       │
│  Worker 2 ──→ ConversationRequest  ──→                      │
│           ←── ConversationResponse ←──                       │
│  ...                                                         │
│  Worker N ──→ ConversationRequest  ──→                      │
│           ←── ConversationResponse ←──                       │
│                                                              │
│  Throughput: ~1,000-2,000 req/sec (bottleneck!)             │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ NEW: Chunk-Based Distribution (Optimized)                    │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Worker 1 ──→ ChunkRequest(size=100) ──→ DatasetManager     │
│           ←── ChunkResponse(100 convos) ←──                  │
│           [Local Queue: 100 conversations]                   │
│           [Process locally...]                               │
│           [Queue size < 20? Request new chunk]               │
│                                                              │
│  Worker N ──→ ChunkRequest(size=100) ──→                    │
│           ←── ChunkResponse(100 convos) ←──                  │
│                                                              │
│  Throughput: ~100-500 req/sec (100x fewer requests!)        │
└─────────────────────────────────────────────────────────────┘
```

### Key Benefits

1. **100x Reduction in Network Requests**: 100 conversations per request vs 1
2. **Amortized Serialization Overhead**: Serialize once per chunk
3. **Worker-Side Buffering**: Workers process locally without blocking
4. **Load Balancing**: Workers request chunks as needed dynamically
5. **Memory Efficient**: Workers only buffer what they need
6. **Backwards Compatible**: Falls back to single-conversation mode if needed

### Design Decisions

#### 1. Chunk Size Strategy

**Default**: 100 conversations per chunk

**Rationale**:
- Small enough: ~10KB-100KB per chunk (manageable memory)
- Large enough: 100x reduction in network overhead
- Configurable: Users can tune based on dataset size

**Formula**:
```python
optimal_chunk_size = min(
    user_config.dataset_chunk_size,
    max(10, total_conversations // (num_workers * 2))
)
```

#### 2. Prefetch Threshold

**Default**: Request new chunk when local queue < 20% of chunk size

**Rationale**:
- Prevents worker starvation
- Overlaps network I/O with computation
- Maintains steady flow

**Example**:
```python
if len(local_queue) < (chunk_size * 0.2):
    asyncio.create_task(request_new_chunk())  # Background prefetch
```

#### 3. Distribution Strategy

**Round-Robin**: DatasetManager tracks cursor position

**Rationale**:
- Deterministic: Each worker gets unique conversations
- Fair: Even distribution across workers
- No overlap: Each conversation used once (unless dataset repeats)

**Implementation**:
```python
class DatasetManager:
    def __init__(self):
        self._chunk_cursor = 0  # Current position in dataset
        self._session_ids_list = []  # Ordered list of session IDs

    def get_chunk(self, size: int) -> list[Conversation]:
        start = self._chunk_cursor
        end = min(start + size, len(self._session_ids_list))

        chunk_ids = self._session_ids_list[start:end]
        conversations = [self.dataset[sid] for sid in chunk_ids]

        self._chunk_cursor = end

        # Wrap around if needed
        if self._chunk_cursor >= len(self._session_ids_list):
            self._chunk_cursor = 0

        return conversations
```

## Implementation Plan

### Phase 1: Message Types (New)

```python
# aiperf/common/messages/dataset_messages.py

@dataclass
class ConversationChunkRequestMessage(Message):
    """Request a chunk of conversations from DatasetManager."""

    message_type: MessageType = MessageType.CONVERSATION_CHUNK_REQUEST
    request_id: str | None = None
    chunk_size: int = 100  # Number of conversations requested
    worker_id: str | None = None  # For tracking/debugging


@dataclass
class ConversationChunkResponseMessage(Message):
    """Response containing a chunk of conversations."""

    message_type: MessageType = MessageType.CONVERSATION_CHUNK_RESPONSE
    service_id: str
    request_id: str | None
    conversations: list[Conversation]  # Chunk of conversations
    chunk_index: int  # Which chunk this is (for debugging)
    has_more: bool  # Whether more conversations available
```

### Phase 2: DatasetManager Enhancement

```python
# aiperf/dataset/dataset_manager.py

class DatasetManager:
    def __init__(self, ...):
        # ... existing init

        # NEW: Chunking state
        self._chunk_cursor = 0
        self._chunk_counter = 0  # Total chunks served
        self._chunking_enabled = True

    @on_request(MessageType.CONVERSATION_CHUNK_REQUEST)
    async def _handle_chunk_request(
        self, message: ConversationChunkRequestMessage
    ) -> ConversationChunkResponseMessage:
        """Handle a chunk request."""

        await self._wait_for_dataset_configuration()

        chunk_size = min(message.chunk_size, len(self.dataset))
        conversations = self._get_conversation_chunk(chunk_size)

        self._chunk_counter += 1

        return ConversationChunkResponseMessage(
            service_id=self.service_id,
            request_id=message.request_id,
            conversations=conversations,
            chunk_index=self._chunk_counter,
            has_more=True,  # Always true for now (repeating dataset)
        )

    def _get_conversation_chunk(self, size: int) -> list[Conversation]:
        """Get a chunk of conversations starting from current cursor."""

        if not self._session_ids_cache:
            return []

        # Get chunk with wraparound
        start = self._chunk_cursor
        conversations = []

        for _ in range(size):
            session_id = self._session_ids_cache[self._chunk_cursor]
            conversations.append(self.dataset[session_id])

            self._chunk_cursor = (self._chunk_cursor + 1) % len(self._session_ids_cache)

        return conversations
```

### Phase 3: Worker Enhancement

```python
# aiperf/workers/worker.py

class Worker:
    def __init__(self, ...):
        # ... existing init

        # NEW: Local conversation queue
        self._conversation_queue: asyncio.Queue[Conversation] = asyncio.Queue()
        self._chunk_size = self.user_config.dataset.chunk_size
        self._prefetch_threshold = int(self._chunk_size * 0.2)
        self._prefetch_task: asyncio.Task | None = None
        self._use_chunking = self.user_config.dataset.enable_chunking

    async def _initialize_conversation_queue(self):
        """Initialize the conversation queue by requesting first chunk."""

        if self._use_chunking:
            await self._request_chunk()

    async def _request_chunk(self):
        """Request a new chunk of conversations from DatasetManager."""

        request = ConversationChunkRequestMessage(
            request_id=str(uuid.uuid4()),
            chunk_size=self._chunk_size,
            worker_id=self.service_id,
        )

        response: ConversationChunkResponseMessage = await self.request_client.send(
            request,
            address=CommAddress.DATASET_MANAGER_PROXY_FRONTEND,
        )

        # Add conversations to local queue
        for conversation in response.conversations:
            await self._conversation_queue.put(conversation)

        self.debug(
            f"Received chunk with {len(response.conversations)} conversations. "
            f"Queue size now: {self._conversation_queue.qsize()}"
        )

    async def _get_conversation(self) -> Conversation:
        """Get next conversation from local queue or request new one."""

        if self._use_chunking:
            # Check if we need to prefetch
            if (self._conversation_queue.qsize() < self._prefetch_threshold and
                (self._prefetch_task is None or self._prefetch_task.done())):
                # Start background prefetch
                self._prefetch_task = asyncio.create_task(self._request_chunk())

            # Get from local queue (blocks if empty)
            return await self._conversation_queue.get()
        else:
            # OLD: Request single conversation
            return await self._request_single_conversation()

    async def _request_single_conversation(self) -> Conversation:
        """Request a single conversation (legacy mode)."""

        request = ConversationRequestMessage(
            request_id=str(uuid.uuid4()),
            conversation_id=None,
        )

        response: ConversationResponseMessage = await self.request_client.send(
            request,
            address=CommAddress.DATASET_MANAGER_PROXY_FRONTEND,
        )

        return response.conversation
```

### Phase 4: Configuration

```python
# aiperf/common/config/input_config.py

class InputConfig(BaseConfig):
    # ... existing fields

    enable_chunking: Annotated[
        bool,
        Field(description="Enable chunk-based dataset distribution for better performance"),
        CLIParameter(name=("--enable-chunking",)),
    ] = True

    dataset_chunk_size: Annotated[
        int,
        Field(
            description="Number of conversations per chunk (higher = fewer requests, more memory)",
            ge=1,
            le=1000,
        ),
        CLIParameter(name=("--chunk-size",)),
    ] = 100

    prefetch_threshold: Annotated[
        float,
        Field(
            description="Prefetch new chunk when queue below this fraction (0.0-1.0)",
            ge=0.0,
            le=1.0,
        ),
        CLIParameter(name=("--prefetch-threshold",)),
    ] = 0.2
```

## Performance Analysis

### Baseline (No Chunking)

```
Workers: 1000
Request Rate per Worker: 10 req/sec
Total Requests to DatasetManager: 10,000 req/sec

Network Overhead per Request: ~500 μs
Total Network Time: 5,000 sec/sec (500% CPU!)
Result: BOTTLENECK - DatasetManager can't keep up
```

### With Chunking (chunk_size=100)

```
Workers: 1000
Chunk Size: 100 conversations
Chunk Duration: 10 seconds (100 conversations @ 10 req/sec)
Total Requests to DatasetManager: 100 req/sec

Network Overhead per Request: ~500 μs
Total Network Time: 50 sec/sec (5% CPU)
Result: NO BOTTLENECK - 100x improvement!
```

### Memory Impact

```
Per Worker Memory:
- Without chunking: ~10 KB (single conversation)
- With chunking (100): ~1 MB (100 conversations buffered)

Total Memory for 1000 Workers:
- Without: 10 MB
- With: 1 GB (acceptable for high-concurrency deployments)
```

### Latency Impact

```
Worker Request Latency:
- Without chunking:
  - Network round-trip: ~1-5 ms
  - DatasetManager processing: 0.1 ms
  - Total per conversation: ~1-5 ms

- With chunking:
  - First conversation in chunk: ~1-5 ms (initial request)
  - Subsequent 99 conversations: <0.001 ms (local queue)
  - Amortized per conversation: ~0.05 ms

Result: 100x lower amortized latency!
```

## Testing Strategy

### Unit Tests

```python
# tests/dataset/test_chunk_distribution.py

class TestChunkDistribution:
    def test_chunk_request_response():
        """Test chunk request/response message serialization."""

    def test_dataset_manager_chunking():
        """Test DatasetManager returns correct chunk size."""

    def test_chunk_cursor_wraparound():
        """Test cursor wraps around at end of dataset."""

    def test_worker_local_queue():
        """Test worker maintains local queue correctly."""

    def test_prefetch_threshold():
        """Test prefetching triggers at correct threshold."""
```

### Integration Tests

```python
# tests/integration/test_chunk_performance.py

@pytest.mark.benchmark
async def test_throughput_comparison():
    """Compare throughput with/without chunking."""

    # Test without chunking
    throughput_no_chunk = await measure_throughput(
        num_workers=100,
        enable_chunking=False,
        duration=30,
    )

    # Test with chunking
    throughput_with_chunk = await measure_throughput(
        num_workers=100,
        enable_chunking=True,
        chunk_size=100,
        duration=30,
    )

    assert throughput_with_chunk > throughput_no_chunk * 10  # At least 10x improvement
```

### Performance Benchmarks

```python
# benchmarks/dataset_chunking_benchmark.py

async def benchmark_dataset_manager():
    """Benchmark DatasetManager throughput."""

    configs = [
        {"chunk_size": 1, "workers": 100},    # Baseline
        {"chunk_size": 50, "workers": 100},   # Small chunks
        {"chunk_size": 100, "workers": 100},  # Default
        {"chunk_size": 500, "workers": 100},  # Large chunks
    ]

    for config in configs:
        throughput = await measure_requests_per_second(**config)
        print(f"Config {config}: {throughput} req/sec")
```

## Backwards Compatibility

### Automatic Fallback

```python
# DatasetManager automatically supports both modes

@on_request(MessageType.CONVERSATION_REQUEST)
async def _handle_conversation_request(self, message):
    """OLD API - still supported."""
    return self._return_any_conversation(message.request_id)

@on_request(MessageType.CONVERSATION_CHUNK_REQUEST)
async def _handle_chunk_request(self, message):
    """NEW API - chunk-based."""
    return self._get_conversation_chunk(message.chunk_size)
```

### Configuration Flag

```bash
# Disable chunking if needed
aiperf profile --enable-chunking=false ...

# Default: chunking enabled
aiperf profile ...
```

## Migration Path

### Phase 1: Add support (v1.1)
- Implement chunk messages
- Update DatasetManager
- Keep old API working

### Phase 2: Update workers (v1.1)
- Add local queueing
- Add prefetching
- Default to chunking

### Phase 3: Deprecation (v1.2)
- Log warning for old API usage
- Document migration

### Phase 4: Remove old API (v2.0)
- Remove single-conversation API
- Chunking only

## Monitoring & Observability

### New Metrics

```python
# DatasetManager metrics
dataset_chunk_requests_total: Counter
dataset_chunk_size_bytes: Histogram
dataset_chunk_latency_seconds: Histogram

# Worker metrics
worker_queue_size: Gauge
worker_prefetch_requests_total: Counter
worker_queue_wait_time_seconds: Histogram
```

### Logging

```python
# DatasetManager
logger.info(f"Served chunk {chunk_index} with {len(conversations)} conversations")

# Worker
logger.debug(f"Queue size: {queue.qsize()}, prefetch triggered: {prefetch_active}")
```

## Future Enhancements

1. **Smart Chunk Sizing**: Dynamically adjust chunk size based on worker consumption rate
2. **Worker-Specific Sharding**: Assign specific shards to workers for better locality
3. **Compressed Chunks**: Compress conversation data for faster network transfer
4. **Multi-DatasetManager**: Multiple managers for even higher throughput
5. **Dataset Streaming**: Stream from disk/S3 instead of loading all in memory

## Summary

**Impact**:
- **100x fewer requests** to DatasetManager
- **100x lower amortized latency** per conversation
- **No bottleneck** even with 10,000+ concurrent workers
- **Backwards compatible** with existing code
- **Configurable** for different workload characteristics

**Trade-offs**:
- **Memory**: +1 MB per worker (negligible)
- **Complexity**: Local queue management (minimal)
- **Code changes**: ~200 lines total (focused, clean)

**Status**: Ready for implementation and testing.
