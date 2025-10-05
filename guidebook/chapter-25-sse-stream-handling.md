# Chapter 25: SSE Stream Handling

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Navigation
- Previous: [Chapter 24: OpenAI Client](chapter-24-openai-client.md)
- Next: [Chapter 26: TCP Optimizations](chapter-26-tcp-optimizations.md)
- [Table of Contents](README.md)

## Overview

Server-Sent Events (SSE) is the protocol used for streaming AI responses. AIPerf's SSE implementation provides high-performance parsing with nanosecond-precision timing for each message chunk, enabling accurate measurement of Time to First Token (TTFT), Inter-Token Latency (ITL), and stream processing performance.

This chapter explores the SSE parsing implementation, timing capture, protocol compliance, and performance optimizations.

## SSE Protocol

### Specification

SSE is defined in the HTML Living Standard: https://html.spec.whatwg.org/multipage/server-sent-events.html

**Key Characteristics**:
- Text-based protocol over HTTP
- Unidirectional server-to-client streaming
- Content-Type: `text/event-stream`
- Messages separated by blank lines (`\n\n`)
- Field-value pairs separated by colons

**Example Stream**:
```
data: {"id":"1","delta":{"content":"Hello"}}

data: {"id":"1","delta":{"content":" world"}}

data: [DONE]

```

### Field Types

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/enums/sse_enums.py`

```python
class SSEFieldType(CaseInsensitiveStrEnum):
    """Field types in an SSE message."""

    DATA = "data"      # Message payload
    EVENT = "event"    # Event type
    ID = "id"          # Event ID
    RETRY = "retry"    # Reconnection time
    COMMENT = "comment" # Comment (field name is empty)
```

**Field Formats**:
```
data: message content
event: event_type
id: message_id
retry: 3000
: this is a comment
```

## Architecture

### AioHttpSSEStreamReader Class

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/clients/http/aiohttp_client.py`

```python
class AioHttpSSEStreamReader:
    """A helper class for reading an SSE stream from an aiohttp.ClientResponse object.

    This class is optimized for maximum performance and accurate timing measurements,
    making it ideal for benchmarking scenarios.
    """

    def __init__(self, response: aiohttp.ClientResponse):
        self.response = response

    async def read_complete_stream(self) -> list[SSEMessage]:
        """Read the complete SSE stream in a performant manner and return a list of
        SSE messages that contain the most accurate timestamp data possible.

        Returns:
            A list of SSE messages.
        """
        messages: list[SSEMessage] = []

        async for raw_message, first_byte_ns in self.__aiter__():
            # Parse the raw SSE message into a SSEMessage object
            message = parse_sse_message(raw_message, first_byte_ns)
            messages.append(message)

        return messages

    async def __aiter__(self) -> typing.AsyncIterator[tuple[str, int]]:
        """Iterate over the SSE stream in a performant manner and return a tuple of the
        raw SSE message, the perf_counter_ns of the first byte, and the perf_counter_ns of the last byte.
        This provides the most accurate timing information possible without any delays due to the nature of
        the aiohttp library. The first byte is read immediately to capture the timestamp of the first byte,
        and the last byte is read after the rest of the chunk is read to capture the timestamp of the last byte.

        Returns:
            An async iterator of tuples of the raw SSE message, and the perf_counter_ns of the first byte
        """

        while not self.response.content.at_eof():
            # Read the first byte of the SSE stream
            first_byte = await self.response.content.read(1)
            chunk_ns_first_byte = time.perf_counter_ns()
            if not first_byte:
                break

            chunk = await self.response.content.readuntil(b"\n\n")

            if not chunk:
                break
            chunk = first_byte + chunk

            try:
                # Use the fastest available decoder
                yield (
                    chunk.decode("utf-8").strip(),
                    chunk_ns_first_byte,
                )
            except UnicodeDecodeError:
                # Handle potential encoding issues gracefully
                yield (
                    chunk.decode("utf-8", errors="replace").strip(),
                    chunk_ns_first_byte,
                )
```

### Key Design Features

#### 1. First-Byte Timing

The critical optimization is capturing the timestamp of the first byte:

```python
# Read first byte
first_byte = await self.response.content.read(1)

# Capture timestamp IMMEDIATELY after
chunk_ns_first_byte = time.perf_counter_ns()

# Then read rest of message
chunk = await self.response.content.readuntil(b"\n\n")
```

**Why This Matters**:
- **TTFT Accuracy**: First token timestamp is precise
- **ITL Precision**: Inter-token intervals are accurate
- **Minimal Overhead**: Timestamp captured before parsing
- **Network Timing**: Measures actual arrival time

#### 2. Chunk Boundary Detection

Messages are delimited by double newlines (`\n\n`):

```python
chunk = await self.response.content.readuntil(b"\n\n")
```

**Protocol Compliance**:
- Reads until message boundary
- Handles incomplete messages gracefully
- Preserves message integrity
- Works with variable-length messages

#### 3. Error Handling

Graceful handling of encoding errors:

```python
try:
    yield chunk.decode("utf-8").strip(), chunk_ns_first_byte
except UnicodeDecodeError:
    yield chunk.decode("utf-8", errors="replace").strip(), chunk_ns_first_byte
```

**Benefits**:
- Continues processing on encoding errors
- Replaces invalid characters with replacement character
- Logs error without failing
- Maintains timing accuracy

## Message Parsing

### parse_sse_message Function

```python
def parse_sse_message(raw_message: str, perf_ns: int) -> SSEMessage:
    """Parse a raw SSE message into an SSEMessage object.

    Parsing logic based on official HTML SSE Living Standard:
    https://html.spec.whatwg.org/multipage/server-sent-events.html#parsing-an-event-stream
    """

    message = SSEMessage(perf_ns=perf_ns)
    for line in raw_message.split("\n"):
        if not (line := line.strip()):
            continue

        parts = line.split(":", 1)
        if len(parts) < 2:
            # Fields without a colon have no value, so the whole line is the field name
            message.packets.append(SSEField(name=parts[0].strip(), value=None))
            continue

        field_name, value = parts

        if field_name == "":
            # Field name is empty, so this is a comment
            field_name = SSEFieldType.COMMENT

        message.packets.append(SSEField(name=field_name.strip(), value=value.strip()))

    return message
```

### SSE Message Structure

```python
@dataclass
class SSEMessage:
    perf_ns: int                 # Timestamp of first byte
    packets: list[SSEField]      # Parsed field-value pairs

@dataclass
class SSEField:
    name: str                    # Field name (data, event, id, etc.)
    value: str | None           # Field value
```

### Parsing Examples

**Example 1: Simple Data Message**:
```
Input: "data: Hello world"

Output: SSEMessage(
    perf_ns=1234567890123456789,
    packets=[
        SSEField(name="data", value="Hello world")
    ]
)
```

**Example 2: Multi-Line Message**:
```
Input: """
event: message
data: {"text":"Hello"}
id: 123
"""

Output: SSEMessage(
    perf_ns=1234567890123456789,
    packets=[
        SSEField(name="event", value="message"),
        SSEField(name="data", value='{"text":"Hello"}'),
        SSEField(name="id", value="123"),
    ]
)
```

**Example 3: Comment**:
```
Input: ": this is a comment"

Output: SSEMessage(
    perf_ns=1234567890123456789,
    packets=[
        SSEField(name="comment", value="this is a comment")
    ]
)
```

**Example 4: Field Without Value**:
```
Input: "data"

Output: SSEMessage(
    perf_ns=1234567890123456789,
    packets=[
        SSEField(name="data", value=None)
    ]
)
```

## Data Extraction

### extract_data_content Method

```python
class SSEMessage:
    def extract_data_content(self) -> str:
        """Extract the concatenated content of all 'data' fields."""
        data_fields = [
            packet.value
            for packet in self.packets
            if packet.name == SSEFieldType.DATA and packet.value is not None
        ]
        return "\n".join(data_fields)
```

**Usage**:
```python
message = SSEMessage(
    perf_ns=1234567890123456789,
    packets=[
        SSEField(name="data", value='{"delta":{"content":"Hello"}}'),
        SSEField(name="data", value='{"delta":{"content":" world"}}'),
    ]
)

content = message.extract_data_content()
# Returns: '{"delta":{"content":"Hello"}}\n{"delta":{"content":" world"}}'
```

## Streaming Flow

### Complete Process

```
┌─────────────────────┐
│ HTTP Response       │
│ Content-Type:       │
│ text/event-stream   │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Read First Byte     │
│ first_byte = read(1)│
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Capture Timestamp   │
│ ns = perf_counter() │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Read Until \n\n     │
│ chunk = readuntil() │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Decode UTF-8        │
│ text = decode()     │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Parse SSE Message   │
│ parse_sse_message() │
└──────────┬──────────┘
           │
           v
┌─────────────────────┐
│ Store Message       │
│ messages.append()   │
└──────────┬──────────┘
           │
           v
      Loop Until EOF
```

### Timing Precision

**Captured Timestamps**:

1. **Request Start**: Before sending request
2. **First Response Byte**: After receiving first SSE message byte
3. **Each Chunk**: First byte of each subsequent message
4. **Request End**: After processing all messages

**Metric Calculations**:

```python
# Time to First Token (TTFT)
ttft = messages[0].perf_ns - record.start_perf_ns

# Inter-Token Latency (ITL)
itl_values = []
for i in range(1, len(messages)):
    itl = messages[i].perf_ns - messages[i-1].perf_ns
    itl_values.append(itl)

# Average ITL
avg_itl = sum(itl_values) / len(itl_values)

# Request Latency
request_latency = record.end_perf_ns - record.start_perf_ns
```

## OpenAI Streaming Format

### Chat Completion Chunks

**Stream Format**:
```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1694268190,"model":"gpt-4","choices":[{"index":0,"delta":{"content":"Hello"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1694268190,"model":"gpt-4","choices":[{"index":0,"delta":{"content":" world"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1694268190,"model":"gpt-4","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]

```

### Completion Stream

```
data: {"id":"cmpl-123","object":"text_completion","created":1694268190,"choices":[{"text":"Hello","index":0,"finish_reason":null}]}

data: {"id":"cmpl-123","object":"text_completion","created":1694268190,"choices":[{"text":" world","index":0,"finish_reason":"length"}]}

data: [DONE]

```

### Stream Termination

The `[DONE]` message signals stream completion:

```python
if raw_text in ("", None, "[DONE]"):
    return None  # Skip this message
```

## Performance Optimizations

### 1. First-Byte Reading

```python
# Optimal: Read 1 byte, timestamp immediately
first_byte = await self.response.content.read(1)
timestamp = time.perf_counter_ns()

# Suboptimal: Read whole chunk, then timestamp
chunk = await self.response.content.readuntil(b"\n\n")
timestamp = time.perf_counter_ns()  # Delayed timestamp
```

**Impact**: 100-1000 microseconds difference per chunk

### 2. Efficient Decoding

```python
# Fast: UTF-8 direct decode
text = chunk.decode("utf-8")

# Slower: Encoding detection
import chardet
encoding = chardet.detect(chunk)['encoding']
text = chunk.decode(encoding)
```

### 3. Minimal Allocations

```python
# Efficient: Single list append
messages.append(parse_sse_message(raw_message, first_byte_ns))

# Inefficient: Multiple intermediate structures
temp_message = parse_sse_message(raw_message, first_byte_ns)
validated_message = validate_message(temp_message)
messages.append(validated_message)
```

### 4. Streaming Iterator

```python
# Memory efficient: Process as stream
async for raw_message, first_byte_ns in self.__aiter__():
    message = parse_sse_message(raw_message, first_byte_ns)
    messages.append(message)

# Memory inefficient: Buffer entire stream
all_chunks = []
while not eof:
    chunk = await read_chunk()
    all_chunks.append(chunk)
# Then process all chunks
```

## Error Handling

### Connection Errors

```python
try:
    messages = await AioHttpSSEStreamReader(response).read_complete_stream()
except aiohttp.ClientError as e:
    self.error(f"Connection error during SSE stream: {e}")
    record.error = ErrorDetails(
        type=e.__class__.__name__,
        message=str(e)
    )
```

### Incomplete Messages

```python
# EOF before message boundary
while not self.response.content.at_eof():
    first_byte = await self.response.content.read(1)
    if not first_byte:
        break  # Handle gracefully

    try:
        chunk = await self.response.content.readuntil(b"\n\n")
    except asyncio.LimitOverrunError:
        # Message too large for buffer
        self.error("SSE message exceeded buffer size")
        break
```

### Encoding Errors

```python
try:
    text = chunk.decode("utf-8").strip()
except UnicodeDecodeError as e:
    # Replace invalid characters
    text = chunk.decode("utf-8", errors="replace").strip()
    self.warning(f"Invalid UTF-8 in SSE message: {e}")
```

## Usage Examples

### Basic Streaming

```python
# Make streaming request
record = await client.post_request(
    url="https://api.openai.com/v1/chat/completions",
    payload=json.dumps({
        "model": "gpt-4",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True,
    }),
    headers={
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    },
)

# Process SSE messages
for message in record.responses:
    if isinstance(message, SSEMessage):
        print(f"Timestamp: {message.perf_ns}")
        print(f"Content: {message.extract_data_content()}")
```

### TTFT Calculation

```python
# Get TTFT from first message
if record.responses:
    first_message = record.responses[0]
    ttft_ns = first_message.perf_ns - record.start_perf_ns
    ttft_ms = ttft_ns / 1_000_000
    print(f"TTFT: {ttft_ms:.2f} ms")
```

### ITL Calculation

```python
# Calculate inter-token latencies
itl_values = []
for i in range(1, len(record.responses)):
    prev_ts = record.responses[i-1].perf_ns
    curr_ts = record.responses[i].perf_ns
    itl_ns = curr_ts - prev_ts
    itl_values.append(itl_ns)

# Statistics
avg_itl_ms = sum(itl_values) / len(itl_values) / 1_000_000
min_itl_ms = min(itl_values) / 1_000_000
max_itl_ms = max(itl_values) / 1_000_000

print(f"Average ITL: {avg_itl_ms:.2f} ms")
print(f"Min ITL: {min_itl_ms:.2f} ms")
print(f"Max ITL: {max_itl_ms:.2f} ms")
```

## Testing

### Mock SSE Stream

```python
import asyncio
from unittest.mock import AsyncMock

async def test_sse_parsing():
    # Create mock response
    mock_response = AsyncMock()
    mock_response.content.at_eof.side_effect = [False, False, True]
    mock_response.content.read.side_effect = [
        b"d",  # First byte of first message
        b"d",  # First byte of second message
    ]
    mock_response.content.readuntil.side_effect = [
        b"ata: Hello\n\n",
        b"ata: World\n\n",
    ]

    # Parse stream
    reader = AioHttpSSEStreamReader(mock_response)
    messages = await reader.read_complete_stream()

    # Verify
    assert len(messages) == 2
    assert messages[0].extract_data_content() == "Hello"
    assert messages[1].extract_data_content() == "World"
```

## Debugging

### Message Inspection

```python
for i, message in enumerate(record.responses):
    print(f"Message {i}:")
    print(f"  Timestamp: {message.perf_ns}")
    print(f"  Packets: {len(message.packets)}")
    for packet in message.packets:
        print(f"    {packet.name}: {packet.value}")
```

### Timing Analysis

```python
# Analyze timing between chunks
timestamps = [msg.perf_ns for msg in record.responses]
intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]

print(f"Total messages: {len(record.responses)}")
print(f"Total time: {(timestamps[-1] - timestamps[0]) / 1_000_000:.2f} ms")
print(f"Average interval: {sum(intervals) / len(intervals) / 1_000_000:.2f} ms")
print(f"Min interval: {min(intervals) / 1_000_000:.2f} ms")
print(f"Max interval: {max(intervals) / 1_000_000:.2f} ms")
```

## Key Takeaways

1. **First-Byte Timing**: Critical optimization for accurate TTFT and ITL measurements

2. **Protocol Compliance**: Follows HTML SSE Living Standard specification

3. **Nanosecond Precision**: Timestamps captured immediately upon byte arrival

4. **Error Resilience**: Graceful handling of encoding and connection errors

5. **Memory Efficiency**: Streaming iterator processes messages as they arrive

6. **Minimal Overhead**: Optimized for benchmarking with minimal processing delay

7. **OpenAI Compatible**: Handles OpenAI streaming format correctly

8. **Type Safety**: Structured SSEMessage and SSEField types

9. **Data Extraction**: Convenient methods for accessing message content

10. **Performance Focus**: Every optimization targets accurate timing measurement

## What's Next

- **Chapter 26: TCP Optimizations** - Explore socket-level optimizations for streaming
- **Chapter 28: Response Parsers** - Learn how SSE messages are parsed into structured data

---

**Remember**: SSE streaming performance is critical for AI benchmarking. The first-byte timing optimization ensures accurate TTFT measurements, while efficient parsing maintains low overhead for ITL calculations.
