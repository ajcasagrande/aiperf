# Chapter 7: Workers Architecture

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Table of Contents
- [Worker Process Design](#worker-process-design)
- [Credit Processing Pipeline](#credit-processing-pipeline)
- [HTTP Client Integration](#http-client-integration)
- [Timing Precision](#timing-precision)
- [Error Handling](#error-handling)
- [Performance Considerations](#performance-considerations)
- [Key Takeaways](#key-takeaways)

## Worker Process Design

Workers (`/home/anthony/nvidia/projects/aiperf/aiperf/workers/worker.py`) are the workhorses of AIPerf. Each worker runs in its own process and is responsible for executing HTTP requests against the target inference endpoint.

### Worker Initialization

```python
@ServiceFactory.register(ServiceType.WORKER)
class Worker(PullClientMixin, BaseComponentService, ProcessHealthMixin):
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
        **kwargs,
    ):
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            pull_client_address=CommAddress.CREDIT_DROP,
            pull_client_bind=False,
            # Limit concurrency to HTTP connection limit
            pull_client_max_concurrency=AIPERF_HTTP_CONNECTION_LIMIT,
            **kwargs,
        )

        # Task statistics tracking
        self.task_stats: WorkerTaskStats = WorkerTaskStats()

        # Create ZMQ clients
        self.credit_return_push_client = self.comms.create_push_client(
            CommAddress.CREDIT_RETURN,
        )
        self.inference_results_push_client = self.comms.create_push_client(
            CommAddress.RAW_INFERENCE_PROXY_FRONTEND,
        )
        self.conversation_request_client = self.comms.create_request_client(
            CommAddress.DATASET_MANAGER_PROXY_FRONTEND,
        )

        # Create endpoint-specific clients
        self.model_endpoint = ModelEndpointInfo.from_user_config(self.user_config)
        self.request_converter = RequestConverterFactory.create_instance(
            self.model_endpoint.endpoint.type,
        )
        self.inference_client = InferenceClientFactory.create_instance(
            self.model_endpoint.endpoint.type,
            model_endpoint=self.model_endpoint,
        )
        self.extractor = ResponseExtractorFactory.create_instance(
            self.model_endpoint.endpoint.type,
            model_endpoint=self.model_endpoint,
        )
```

### Worker Components

1. **Pull Client**: Pulls credit drops with concurrency limiting
2. **Push Clients**: Return credits and send results
3. **Request Client**: Request conversation data
4. **Inference Client**: HTTP client for endpoint
5. **Request Converter**: Format payloads for endpoint type
6. **Response Extractor**: Parse responses

## Credit Processing Pipeline

The core worker loop follows this pipeline:

```
1. Pull Credit Drop (blocks until available and semaphore allows)
   │
   ├→ CreditDropMessage received
   │
2. Request Conversation Data
   │
   ├→ ConversationRequestMessage → Dataset Manager
   │
   ├→ ConversationResponseMessage received
   │
3. Process Each Turn in Conversation
   │
   ├→ For each turn:
   │     │
   │     ├→ Format payload
   │     │
   │     ├→ Wait for credit drop time (if specified)
   │     │
   │     ├→ Send HTTP request
   │     │
   │     ├→ Measure timing
   │     │
   │     ├→ Create RequestRecord
   │     │
   │     ├→ Send to Record Processor
   │     │
   │     └→ Extract response for next turn (multi-turn)
   │
4. Return Credit
   │
   └→ CreditReturnMessage → Timing Manager
```

### Credit Drop Handler

```python
@on_pull_message(MessageType.CREDIT_DROP)
async def _credit_drop_callback(self, message: CreditDropMessage) -> None:
    """Handle an incoming credit drop message."""
    try:
        # Process the credit (this must complete)
        await self._process_credit_drop_internal(message)
    except Exception as e:
        self.error(f"Error processing credit drop: {e!r}")
        # Always return credit even on error
        await self.credit_return_push_client.push(
            CreditReturnMessage(
                service_id=self.service_id,
                phase=message.phase,
                credit_drop_id=message.request_id,
            )
        )
```

### Credit Processing

```python
async def _process_credit_drop_internal(
    self, message: CreditDropMessage
) -> None:
    """Process a credit drop message."""
    try:
        # Execute the credit task
        await self._execute_single_credit_internal(message)
    finally:
        # MUST return credit in finally block
        return_message = CreditReturnMessage(
            service_id=self.service_id,
            phase=message.phase,
            credit_drop_id=message.request_id,
            delayed_ns=None,
        )
        await self.credit_return_push_client.push(return_message)
```

### Single Credit Execution

```python
async def _execute_single_credit_internal(
    self, message: CreditDropMessage
) -> None:
    """Run a credit task for a single credit."""
    drop_perf_ns = time.perf_counter_ns()

    # 1. Retrieve conversation from Dataset Manager
    conversation = await self._retrieve_conversation_response(
        service_id=self.service_id,
        conversation_id=message.conversation_id,
        phase=message.phase,
    )

    # 2. Process each turn in the conversation
    turn_list = []
    for turn_index in range(len(conversation.turns)):
        self.task_stats.total += 1
        turn = conversation.turns[turn_index]
        turn_list.append(turn)

        # Execute turn and build record
        record = await self._build_response_record(
            conversation.session_id,
            message,
            turn,
            turn_index,
            drop_perf_ns,
        )

        # Send result
        await self._send_inference_result_message(record)

        # Extract response for next turn (multi-turn)
        resp_turn = await self._process_response(record)
        if resp_turn:
            turn_list.append(resp_turn)
```

### Conversation Retrieval

```python
async def _retrieve_conversation_response(
    self,
    service_id: str,
    conversation_id: str | None,
    phase: CreditPhase,
) -> Conversation:
    """Retrieve conversation from Dataset Manager."""
    conversation_response = await self.conversation_request_client.request(
        ConversationRequestMessage(
            service_id=service_id,
            conversation_id=conversation_id,
            credit_phase=phase,
        )
    )

    # Handle errors
    if isinstance(conversation_response, ErrorMessage):
        await self._send_inference_result_message(
            RequestRecord(
                model_name=self.model_endpoint.primary_model_name,
                conversation_id=conversation_id,
                turn_index=0,
                turn=None,
                timestamp_ns=time.time_ns(),
                start_perf_ns=time.perf_counter_ns(),
                end_perf_ns=time.perf_counter_ns(),
                error=conversation_response.error,
            )
        )
        raise ValueError("Failed to retrieve conversation response")

    return conversation_response.conversation
```

## HTTP Client Integration

### Inference API Call

```python
async def _call_inference_api_internal(
    self,
    message: CreditDropMessage,
    turn: Turn,
    x_request_id: str,
) -> RequestRecord:
    """Make a single call to the inference API."""
    formatted_payload = None
    pre_send_perf_ns = None
    timestamp_ns = None

    try:
        # 1. Format payload for endpoint type
        formatted_payload = await self.request_converter.format_payload(
            model_endpoint=self.model_endpoint,
            turn=turn,
        )

        # 2. Wait for credit drop time if specified
        drop_ns = message.credit_drop_ns
        now_ns = time.time_ns()
        if drop_ns and drop_ns > now_ns:
            await asyncio.sleep((drop_ns - now_ns) / NANOS_PER_SECOND)

        # 3. Capture pre-send timing
        pre_send_perf_ns = time.perf_counter_ns()
        timestamp_ns = time.time_ns()

        # 4. Send request (with optional cancellation)
        send_coroutine = self.inference_client.send_request(
            model_endpoint=self.model_endpoint,
            payload=formatted_payload,
            x_request_id=x_request_id,
            x_correlation_id=message.request_id,
        )

        maybe_result = await self._send_with_optional_cancel(
            send_coroutine=send_coroutine,
            should_cancel=message.should_cancel,
            cancel_after_ns=message.cancel_after_ns,
        )

        if maybe_result is not None:
            result = maybe_result
            result.turn = turn
            return result
        else:
            # Request was cancelled
            return RequestRecord(
                turn=turn,
                timestamp_ns=timestamp_ns,
                start_perf_ns=pre_send_perf_ns,
                end_perf_ns=time.perf_counter_ns(),
                was_cancelled=True,
                cancellation_perf_ns=time.perf_counter_ns(),
                error=ErrorDetails(
                    type="RequestCancellationError",
                    message=f"Request was cancelled after {message.cancel_after_ns / NANOS_PER_SECOND:.3f} seconds",
                    code=499,
                ),
            )

    except Exception as e:
        # Handle errors
        self.error(f"Error calling inference server API: {e!r}")
        return RequestRecord(
            turn=turn,
            timestamp_ns=timestamp_ns or time.time_ns(),
            start_perf_ns=pre_send_perf_ns or time.perf_counter_ns(),
            end_perf_ns=time.perf_counter_ns(),
            error=ErrorDetails.from_exception(e),
        )
```

### Request Cancellation

```python
async def _send_with_optional_cancel(
    self,
    *,
    send_coroutine: Awaitable[RequestRecord],
    should_cancel: bool,
    cancel_after_ns: int,
) -> RequestRecord | None:
    """Send a coroutine with optional cancellation."""
    if not should_cancel:
        return await send_coroutine

    timeout_s = cancel_after_ns / NANOS_PER_SECOND
    try:
        return await asyncio.wait_for(send_coroutine, timeout=timeout_s)
    except asyncio.TimeoutError:
        return None  # Indicates cancellation
```

## Timing Precision

Workers use nanosecond-precision timing throughout:

### Timing Points

```python
class RequestRecord:
    # Wall clock time (for absolute timestamps)
    timestamp_ns: int  # time.time_ns()

    # Monotonic time (for intervals)
    start_perf_ns: int  # time.perf_counter_ns()
    end_perf_ns: int    # time.perf_counter_ns()

    # Streaming timing
    first_token_ns: int | None
    second_token_ns: int | None
    token_timestamps: list[int]

    # Scheduling overhead
    credit_drop_latency: int  # start_perf_ns - drop_perf_ns
```

### Why Two Time Sources?

1. **time.time_ns()**: Wall clock time
   - Absolute timestamps
   - Can go backwards (NTP adjustments)
   - Use for: Timestamps, logging

2. **time.perf_counter_ns()**: Monotonic time
   - Never goes backwards
   - High resolution
   - Use for: Intervals, latency measurements

### Credit Drop Latency

```python
# When credit is received
drop_perf_ns = time.perf_counter_ns()

# Later, when request starts
record.start_perf_ns = time.perf_counter_ns()

# Calculate scheduling overhead
if turn_index == 0:
    record.credit_drop_latency = record.start_perf_ns - drop_perf_ns
```

This measures the overhead between receiving permission and actually starting the request.

## Error Handling

### Graceful Error Handling

Workers handle errors without crashing:

```python
try:
    # Execute request
    record = await self._call_inference_api_internal(...)
except Exception as e:
    # Create error record
    record = RequestRecord(
        turn=turn,
        timestamp_ns=time.time_ns(),
        start_perf_ns=time.perf_counter_ns(),
        end_perf_ns=time.perf_counter_ns(),
        error=ErrorDetails.from_exception(e),
    )
finally:
    # Always send result
    await self._send_inference_result_message(record)
    # Always return credit
    await self.credit_return_push_client.push(return_message)
```

### Error Record Creation

```python
class ErrorDetails:
    type: str  # Exception type
    message: str  # Error message
    code: int | None  # HTTP status code if applicable

    @classmethod
    def from_exception(cls, e: Exception) -> "ErrorDetails":
        return cls(
            type=type(e).__name__,
            message=str(e),
            code=getattr(e, "status_code", None),
        )
```

### Task Statistics

```python
class WorkerTaskStats:
    total: int = 0          # Total tasks started
    in_progress: int = 0    # Currently executing
    completed: int = 0      # Successfully completed
    failed: int = 0         # Failed with errors

    def task_finished(self, valid: bool):
        if valid:
            self.completed += 1
        else:
            self.failed += 1
```

## Performance Considerations

### Connection Pooling

Workers use aiohttp with connection pooling:

```python
# In InferenceClient
self.connector = TCPConnector(
    limit=AIPERF_HTTP_CONNECTION_LIMIT,  # Per worker
    limit_per_host=AIPERF_HTTP_CONNECTION_LIMIT,
    ttl_dns_cache=300,
)

self.session = ClientSession(
    connector=self.connector,
    timeout=ClientTimeout(total=request_timeout_seconds),
)
```

### Concurrency Limiting

Pull client uses a semaphore to limit concurrency:

```python
# In PullClientMixin
self.pull_client_semaphore = asyncio.Semaphore(
    pull_client_max_concurrency  # Typically AIPERF_HTTP_CONNECTION_LIMIT
)

async def _pull_messages_loop(self):
    while not self.stop_requested:
        # Acquire semaphore (blocks if at limit)
        async with self.pull_client_semaphore:
            # Pull message
            message = await self.pull_client.pull()
            # Process message
            await self._handle_pull_message(message)
            # Semaphore released automatically
```

This ensures workers never exceed their HTTP connection limit.

### Health Reporting

Workers periodically report health:

```python
@background_task(
    immediate=False,
    interval=lambda self: self.health_check_interval,
)
async def _health_check_task(self) -> None:
    """Task to report the health of the worker."""
    await self.publish(self.create_health_message())

def create_health_message(self) -> WorkerHealthMessage:
    return WorkerHealthMessage(
        service_id=self.service_id,
        health=self.get_process_health(),  # CPU, memory, I/O
        task_stats=self.task_stats,        # Task counts
    )
```

### Shutdown Handling

```python
@on_stop
async def _shutdown_worker(self) -> None:
    self.debug("Shutting down worker")
    if self.inference_client:
        await self.inference_client.close()
```

## Key Takeaways

1. **Credit-Driven Execution**: Workers pull credits and execute one request per credit, ensuring controlled load generation.

2. **Conversation-Based**: Workers request full conversations from Dataset Manager, supporting multi-turn interactions.

3. **Nanosecond Precision**: Uses both wall clock and monotonic time for accurate measurements.

4. **Endpoint Agnostic**: Factory pattern enables support for different endpoint types (chat, completions, embeddings, etc.).

5. **Graceful Error Handling**: Errors create error records rather than crashing, ensuring system stability.

6. **Concurrency Limiting**: Semaphore limits in-flight requests to prevent resource exhaustion.

7. **Connection Pooling**: Reuses HTTP connections for efficiency.

8. **Health Monitoring**: Reports CPU, memory, and task statistics for observability.

9. **Request Cancellation**: Supports timeout-based request cancellation for SLA testing.

10. **Always Return Credits**: Credits are always returned in finally blocks to prevent deadlocks.

Workers are the execution engine of AIPerf, translating timing credits into actual HTTP requests with precise measurement and robust error handling.

---

Next: [Chapter 8: Worker Manager](chapter-08-worker-manager.md)
