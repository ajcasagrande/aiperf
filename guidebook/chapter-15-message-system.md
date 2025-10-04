<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 15: Message System

## Overview

The Message System is AIPerf's type-safe communication layer, built on Pydantic models and ZMQ transport. Every interaction between services - from credit drops to inference results to command execution - flows through strongly-typed message objects. This chapter explores the message architecture, message types, command pattern implementation, serialization strategies, and routing mechanisms that enable reliable distributed communication.

## Message Architecture

### Base Message Class

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/common/messages/base_messages.py`:

```python
@exclude_if_none("request_ns", "request_id")
class Message(AIPerfBaseModel):
    """Base message class for optimized message handling.

    Provides a base for all messages, including common fields like message_type,
    request_ns, and request_id. Supports optional field exclusion based on the
    @exclude_if_none decorator.
    """

    _message_type_lookup: ClassVar[dict[MessageTypeT, type["Message"]]] = {}
    """Lookup table for message types to their corresponding message classes."""

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "message_type") and cls.message_type is not None:
            # Store concrete message classes in the lookup table
            cls._message_type_lookup[cls.message_type] = cls

    message_type: MessageTypeT = Field(
        ...,
        description="The type of the message. Must be set in the subclass.",
    )

    request_ns: int | None = Field(
        default=None,
        description="Timestamp of the request",
    )

    request_id: str | None = Field(
        default=None,
        description="ID of the request",
    )
```

**Key Features:**

1. **Auto-registration**: Subclasses automatically register in lookup table
2. **Type safety**: Pydantic validation ensures data integrity
3. **Optional fields**: `@exclude_if_none` decorator omits null fields from serialization
4. **Polymorphic deserialization**: Automatically deserialize to correct subclass

### Message Type Enum

```python
class MessageType(CaseInsensitiveStrEnum):
    """Enum for message types."""

    # Credit messages
    CREDIT_DROP = "credit_drop"
    CREDIT_RETURN = "credit_return"
    CREDIT_PHASE_START = "credit_phase_start"
    CREDIT_PHASE_PROGRESS = "credit_phase_progress"
    CREDIT_PHASE_SENDING_COMPLETE = "credit_phase_sending_complete"
    CREDIT_PHASE_COMPLETE = "credit_phase_complete"
    CREDITS_COMPLETE = "credits_complete"

    # Inference messages
    INFERENCE_RESULTS = "inference_results"
    METRIC_RECORDS = "metric_records"

    # Progress messages
    RECORDS_PROCESSING_STATS = "records_processing_stats"
    ALL_RECORDS_RECEIVED = "all_records_received"
    PROCESS_RECORDS_RESULT = "process_records_result"
    REALTIME_METRICS = "realtime_metrics"

    # Command messages
    COMMAND = "command"
    ERROR = "error"

    # Service messages
    SERVICE_STATUS = "service_status"
    SERVICE_READY = "service_ready"
```

### Deserialization

**Auto-detect message type:**

```python
@classmethod
def from_json(cls, json_str: str | bytes | bytearray) -> "Message":
    """Deserialize a message from a JSON string, attempting to auto-detect
    the message type."""
    data = json.loads(json_str)
    message_type = data.get("message_type")
    if not message_type:
        raise ValueError(f"Missing message_type: {json_str}")

    # Use cached message type lookup
    message_class = cls._message_type_lookup[message_type]
    if not message_class:
        raise ValueError(f"Unknown message type: {message_type}")

    return message_class.model_validate(data)
```

**Known message type (faster):**

```python
@classmethod
def from_json_with_type(
    cls, message_type: MessageTypeT, json_str: str | bytes | bytearray
) -> "Message":
    """Deserialize a message from a JSON string with a specific message type.
    More performant than from_json() because it does not need to parse JSON first."""
    message_class = cls._message_type_lookup[message_type]
    if not message_class:
        raise ValueError(f"Unknown message type: {message_type}")
    return message_class.model_validate_json(json_str)
```

## Message Types

### Service Messages

**BaseServiceMessage:**

```python
class BaseServiceMessage(RequiresRequestNSMixin):
    """Base class for service-related messages."""

    service_id: str = Field(..., description="The ID of the service")
```

All service messages include:
- `service_id`: Identifies the sending service
- `request_ns`: Timestamp of message creation

### Credit Messages

Covered extensively in Chapter 11. Key messages:

- `CreditDropMessage`: Authorization for worker to send request
- `CreditReturnMessage`: Worker completed work, returning credit
- `CreditPhaseStartMessage`: Phase started
- `CreditPhaseProgressMessage`: Progress update
- `CreditPhaseSendingCompleteMessage`: All credits dropped
- `CreditPhaseCompleteMessage`: All work completed
- `CreditsCompleteMessage`: Benchmark finished

### Inference Messages

**InferenceResultsMessage:**

```python
class InferenceResultsMessage(BaseServiceMessage):
    """Message containing inference results from a worker."""

    message_type: MessageTypeT = MessageType.INFERENCE_RESULTS

    record: RequestRecord = Field(
        ...,
        description="The request record with responses",
    )
```

Contains complete `RequestRecord` with:
- Turn data
- Conversation ID
- Timing information (start_perf_ns, end_perf_ns)
- Raw responses (SSEMessage or TextResponse list)
- Error details (if any)
- Credit phase
- Cancellation status

**MetricRecordsMessage:**

```python
class MetricRecordsMessage(BaseServiceMessage):
    """Message containing computed metrics for a request."""

    message_type: MessageTypeT = MessageType.METRIC_RECORDS

    timestamp_ns: int = Field(..., description="Request timestamp")
    x_request_id: str | None = Field(default=None, description="X-Request-ID header")
    x_correlation_id: str | None = Field(default=None, description="X-Correlation-ID header")
    credit_phase: CreditPhase = Field(..., description="Credit phase")
    results: list[dict[MetricTagT, MetricValueTypeT]] = Field(
        ...,
        description="Computed metrics for the request",
    )
    error: ErrorDetails | None = Field(default=None, description="Error details")
    worker_id: str = Field(..., description="Worker that processed this request")

    @property
    def valid(self) -> bool:
        """Check if this is a valid (non-error) record."""
        return self.error is None
```

Contains pre-computed metrics from Record Processor:
- `request_latency`: Total latency in nanoseconds
- `ttft`: Time to first token
- `output_token_count`: Number of output tokens
- etc.

### Progress Messages

**RecordsProcessingStatsMessage:**

```python
class RecordsProcessingStatsMessage(BaseServiceMessage):
    """Message containing records processing statistics."""

    message_type: MessageTypeT = MessageType.RECORDS_PROCESSING_STATS

    processing_stats: ProcessingStats = Field(
        ...,
        description="Global processing statistics",
    )
    worker_stats: dict[str, ProcessingStats] = Field(
        default_factory=dict,
        description="Per-worker processing statistics",
    )
```

Published periodically by Records Manager with:
- Total processed/error counts
- Per-worker breakdown

**AllRecordsReceivedMessage:**

```python
class AllRecordsReceivedMessage(BaseServiceMessage):
    """Message indicating all records have been received."""

    message_type: MessageTypeT = MessageType.ALL_RECORDS_RECEIVED

    final_processing_stats: ProcessingStats = Field(
        ...,
        description="Final processing statistics",
    )
```

**ProcessRecordsResultMessage:**

```python
class ProcessRecordsResultMessage(BaseServiceMessage):
    """Message containing final benchmark results."""

    message_type: MessageTypeT = MessageType.PROCESS_RECORDS_RESULT

    results: ProcessRecordsResult = Field(
        ...,
        description="Final processed results",
    )
```

Contains `ProfileResults` with:
- Computed `MetricResult` list
- Error summary
- Timing info (start_ns, end_ns)
- Cancellation status

**RealtimeMetricsMessage:**

```python
class RealtimeMetricsMessage(BaseServiceMessage):
    """Message containing real-time metrics for dashboard."""

    message_type: MessageTypeT = MessageType.REALTIME_METRICS

    metrics: list[MetricResult] = Field(
        ...,
        description="Current metric values",
    )
```

### Command Messages

Commands use request/reply pattern for synchronous operations.

**CommandMessage Base:**

```python
@exclude_if_none("request_ns", "request_id")
class CommandMessage(Message):
    """Base class for command messages."""

    message_type: MessageTypeT = MessageType.COMMAND

    command_type: CommandType = Field(..., description="The type of command")
```

**CommandResponse Base:**

```python
class CommandResponse(AIPerfBaseModel):
    """Base class for command responses."""

    success: bool = Field(default=True, description="Whether command succeeded")
    error: ErrorDetails | None = Field(default=None, description="Error if failed")
```

### Example Commands

**ProcessRecordsCommand:**

```python
class ProcessRecordsCommand(CommandMessage):
    """Command to process accumulated records."""

    command_type: CommandType = CommandType.PROCESS_RECORDS

    cancelled: bool = Field(
        default=False,
        description="Whether the profile was cancelled",
    )
```

Response: `ProcessRecordsResult`

**GetDatasetItemCommand:**

```python
class GetDatasetItemCommand(CommandMessage):
    """Command to retrieve a dataset item."""

    command_type: CommandType = CommandType.GET_DATASET_ITEM

    conversation_id: str = Field(..., description="Conversation ID to retrieve")
```

Response: `DatasetItem`

**ProfileConfigureCommand:**

```python
class ProfileConfigureCommand(CommandMessage):
    """Command to configure services before profiling."""

    command_type: CommandType = CommandType.PROFILE_CONFIGURE
```

Response: None (success/error only)

## Command Pattern

### Command Registration

Services register command handlers using decorators:

```python
@on_command(CommandType.PROCESS_RECORDS)
async def _on_process_records_command(
    self, message: ProcessRecordsCommand
) -> ProcessRecordsResult:
    """Handle the process records command."""
    return await self._process_results(cancelled=message.cancelled)
```

The `@on_command` decorator:
1. Registers handler for specific command type
2. Automatically deserializes command message
3. Invokes handler with typed command object
4. Serializes and sends response

### Command Execution Flow

```
System Controller                    Records Manager
       │                                    │
       │  1. Send command                   │
       ├──────ProcessRecordsCommand────────>│
       │                                    │
       │                                    │  2. Execute handler
       │                                    ├─> _on_process_records_command()
       │                                    │
       │  3. Return response                │
       │<──────ProcessRecordsResult─────────┤
       │                                    │
```

### Request/Reply Implementation

**Sender (System Controller):**

```python
request_client = self.comms.create_request_client(CommAddress.RECORDS_MANAGER)
result = await request_client.request(ProcessRecordsCommand(cancelled=False))
```

**Receiver (Records Manager):**

```python
request_server = self.comms.create_request_server(
    CommAddress.RECORDS_MANAGER,
    bind=True,
)

@on_command(CommandType.PROCESS_RECORDS)
async def handle_command(self, cmd: ProcessRecordsCommand) -> ProcessRecordsResult:
    # Process command
    return result
```

The framework handles:
- Message serialization/deserialization
- Command routing to correct handler
- Response serialization/deserialization
- Error handling and propagation

## Serialization

### JSON Serialization

AIPerf uses Pydantic's JSON serialization:

```python
# Sending
message_json = message.model_dump_json()
await socket.send_string(message_json)

# Receiving
message_json = await socket.recv_string()
message = Message.from_json(message_json)
```

**Advantages:**

- Human-readable (debugging)
- Language-agnostic
- Schema evolution friendly

**Disadvantages:**

- Slower than binary formats
- Larger message size

### Field Exclusion

The `@exclude_if_none` decorator optimizes serialization:

```python
@exclude_if_none("request_ns", "request_id")
class Message(AIPerfBaseModel):
    request_ns: int | None = None
    request_id: str | None = None
```

Fields with `None` values are excluded from JSON:

```json
// Without decorator
{"message_type": "credit_drop", "request_ns": null, "request_id": null}

// With decorator
{"message_type": "credit_drop"}
```

Reduces message size by 20-30% for messages with many optional fields.

### Performance Optimization

**Pre-computed serialization:**

```python
class CachedMessage(Message):
    """Message with cached serialization."""

    _json_cache: str | None = None

    def model_dump_json(self) -> str:
        if self._json_cache is None:
            self._json_cache = super().model_dump_json()
        return self._json_cache
```

For frequently-sent identical messages (e.g., progress updates with same values).

**Lazy deserialization:**

```python
# Only deserialize specific message type
message = Message.from_json_with_type(MessageType.CREDIT_DROP, json_str)
```

Avoids parsing JSON to detect message type.

## Routing

### Publish/Subscribe Routing

**Topic-based filtering:**

```python
# Publisher (no filtering)
await pub_client.publish(CreditPhaseStartMessage(...))

# Subscriber (filter by message type)
sub_client = self.comms.create_sub_client(CommAddress.SUB)

@on_message(MessageType.CREDIT_PHASE_START)
async def handle_phase_start(self, msg: CreditPhaseStartMessage):
    # Only receives CREDIT_PHASE_START messages
    pass
```

The `@on_message` decorator registers handlers for specific message types.

### Message Bus Routing

The Message Bus Mixin enables simple pub/sub:

```python
class MessageBusClientMixin:
    """Mixin for services to publish/subscribe to messages."""

    async def publish(self, message: Message) -> None:
        """Publish a message to the event bus."""
        await self.pub_client.publish(message)

    def subscribe(self, message_type: MessageType, handler: Callable) -> None:
        """Subscribe to a message type."""
        # Register handler
        self._message_handlers[message_type].append(handler)
```

Services can publish without knowing subscribers:

```python
# Timing Manager publishes phase start
await self.publish(CreditPhaseStartMessage(...))

# Records Manager subscribes
@on_message(MessageType.CREDIT_PHASE_START)
async def _on_phase_start(self, msg: CreditPhaseStartMessage):
    # Handle message
    pass
```

### Command Routing

Commands use direct addressing:

```python
# System Controller sends to specific service
request_client = self.comms.create_request_client(CommAddress.RECORDS_MANAGER)
result = await request_client.request(ProcessRecordsCommand())
```

The `CommAddress` enum specifies the target service.

## Error Handling

### ErrorMessage

```python
class ErrorMessage(Message):
    """Message containing error data."""

    message_type: MessageTypeT = MessageType.ERROR

    error: ErrorDetails = Field(..., description="Error information")
```

**ErrorDetails:**

```python
class ErrorDetails(AIPerfBaseModel):
    """Details about an error that occurred."""

    error_type: str = Field(..., description="The type of error")
    error_message: str = Field(..., description="The error message")
    traceback: str | None = Field(default=None, description="The error traceback")

    @classmethod
    def from_exception(cls, exc: BaseException) -> "ErrorDetails":
        """Create ErrorDetails from an exception."""
        return cls(
            error_type=exc.__class__.__name__,
            error_message=str(exc),
            traceback=traceback.format_exc() if hasattr(exc, "__traceback__") else None,
        )
```

### Command Error Handling

Commands can return error responses:

```python
@on_command(CommandType.PROCESS_RECORDS)
async def handle_command(self, cmd: ProcessRecordsCommand) -> ProcessRecordsResult:
    try:
        return await self._process_results()
    except Exception as e:
        # Return error response
        return ProcessRecordsResult(
            success=False,
            error=ErrorDetails.from_exception(e),
        )
```

The requester receives the error:

```python
result = await request_client.request(ProcessRecordsCommand())
if not result.success:
    self.error(f"Command failed: {result.error}")
```

## Best Practices

### Message Design

**Keep messages immutable:**

```python
class ImmutableMessage(Message):
    """Message with immutable fields."""

    field: int = Field(..., frozen=True)  # Cannot be modified after creation
```

**Use specific message types:**

```python
# Bad - generic message
class GenericMessage(Message):
    data: dict[str, Any]

# Good - specific message
class CreditDropMessage(Message):
    phase: CreditPhase
    conversation_id: str | None
    credit_drop_ns: int | None
```

### Command Design

**Commands should be idempotent when possible:**

```python
@on_command(CommandType.CONFIGURE)
async def handle_configure(self, cmd: ConfigureCommand) -> None:
    """Configure service (idempotent - can be called multiple times)."""
    self.config = cmd.config  # Safe to repeat
```

**Use timeouts for commands:**

```python
try:
    result = await asyncio.wait_for(
        request_client.request(ProcessRecordsCommand()),
        timeout=60.0,  # 60 second timeout
    )
except asyncio.TimeoutError:
    self.error("Command timed out")
```

### Serialization Optimization

**Exclude large fields when not needed:**

```python
@exclude_if_none("raw_responses", "traceback")
class OptimizedMessage(Message):
    raw_responses: list | None = None  # Potentially large
    traceback: str | None = None       # Potentially large
```

**Use compression for large messages:**

```python
import zlib

async def send_large_message(self, message: Message) -> None:
    """Send a large message with compression."""
    data = message.model_dump_json().encode()
    if len(data) > 10240:  # > 10 KB
        data = zlib.compress(data)
        await self.socket.send(b"compressed:" + data)
    else:
        await self.socket.send(data)
```

## Troubleshooting

### Deserialization Errors

**Symptoms:** `ValidationError: field required`

**Causes:**
1. Message schema changed without migration
2. Sender/receiver version mismatch
3. Corrupted message

**Solutions:**

```python
try:
    message = Message.from_json(json_str)
except ValidationError as e:
    self.error(f"Deserialization failed: {e}")
    # Log raw message for debugging
    self.debug(f"Raw message: {json_str}")
```

### Message Loss

**Symptoms:** Messages not received by subscribers

**Causes:**
1. Late joiner (SUB) missed early PUB messages
2. HWM reached, messages dropped
3. Network partition

**Solutions:**

```python
# Use synchronization for critical messages
# Wait for all subscribers before publishing
await self._wait_for_subscribers()
await self.publish(CriticalMessage(...))
```

### High Serialization Overhead

**Symptoms:** High CPU usage in serialization

**Causes:**
1. Large messages
2. Frequent serialization of same message
3. Complex nested structures

**Solutions:**

```python
# Cache serialized messages
self._message_cache[message.request_id] = message.model_dump_json()

# Use binary formats for large messages
# Switch to MessagePack or Pickle

# Simplify message structure
# Extract large fields to separate messages
```

## Key Takeaways

1. **Type-Safe Messages**: All messages are strongly-typed Pydantic models with automatic validation.

2. **Auto-Registration**: Message subclasses automatically register in lookup table via `__init_subclass__`.

3. **Polymorphic Deserialization**: `from_json()` automatically deserializes to correct subclass based on `message_type`.

4. **Field Exclusion**: `@exclude_if_none` decorator reduces message size by excluding null fields.

5. **Command Pattern**: Commands use request/reply pattern with typed responses and error handling.

6. **Message Types**: Three main categories - service messages (credit, inference, progress), command messages, and error messages.

7. **Routing**: Pub/sub for broadcasts, direct addressing for commands, topic-based filtering for subscribers.

8. **JSON Serialization**: Human-readable but slower than binary; optimization via field exclusion and caching.

9. **Error Handling**: `ErrorDetails` captures exception information; commands can return error responses.

10. **Best Practices**: Keep messages immutable, use specific types, implement idempotent commands, optimize serialization for large messages.

Next: [Chapter 16: Dataset Types](chapter-16-dataset-types.md)
