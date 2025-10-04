<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 12: Records Manager

## Overview

The Records Manager is AIPerf's central repository for collecting, aggregating, and processing benchmark results. As workers complete inference requests, they send metric records to the Records Manager, which accumulates the data, detects phase completion, tracks errors, and coordinates the final results processing. This service acts as the critical convergence point where distributed execution results are unified into comprehensive benchmark metrics.

This chapter explores the Records Manager's architecture, result aggregation strategies, phase completion detection mechanisms, error tracking, duration filtering, and the intricate coordination required to produce accurate benchmark results.

## Records Manager Architecture

### Service Overview

The Records Manager is implemented in `/home/anthony/nvidia/projects/aiperf/aiperf/records/records_manager.py` as a component service:

```python
@implements_protocol(ServiceProtocol)
@ServiceFactory.register(ServiceType.RECORDS_MANAGER)
class RecordsManager(PullClientMixin, BaseComponentService):
    """
    The RecordsManager service is primarily responsible for holding the
    results returned from the workers.
    """
```

**Key Responsibilities:**

1. **Record Collection**: Receive `MetricRecordsMessage` from Record Processors
2. **Aggregation**: Accumulate results across all workers
3. **Phase Tracking**: Monitor credit phases and detect completion
4. **Error Tracking**: Collect and summarize error details
5. **Duration Filtering**: Filter out requests that completed after benchmark duration
6. **Results Processing**: Coordinate final metric computation and export

### Architectural Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      Records Manager                             │
│                                                                   │
│  ┌───────────────────────────────────────────────────────┐      │
│  │  Pull Client (RECORDS address)                        │      │
│  │  - Receives MetricRecordsMessage                      │      │
│  │  - High concurrency processing                        │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌───────────────────────────────────────────────────────┐      │
│  │  Processing Statistics                                │      │
│  │  - processed: valid record count                      │      │
│  │  - errors: error record count                         │      │
│  │  - total_expected_requests: expected count            │      │
│  │  - worker_stats: per-worker breakdown                 │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌───────────────────────────────────────────────────────┐      │
│  │  Phase Completion Checker                             │      │
│  │  - AllRequestsProcessedCondition                      │      │
│  │  - DurationTimeoutCondition                           │      │
│  │  - Strategy Pattern for extensibility                 │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌───────────────────────────────────────────────────────┐      │
│  │  Results Processors (list)                            │      │
│  │  - MetricRecordProcessor                              │      │
│  │  - MetricResultsProcessor                             │      │
│  │  - Distributed aggregation                            │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                   │
│  ┌───────────────────────────────────────────────────────┐      │
│  │  Error Summary                                        │      │
│  │  - dict[ErrorDetails, count]                          │      │
│  │  - Grouped by error type and message                  │      │
│  └───────────────────────────────────────────────────────┘      │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Initialization

The Records Manager initializes with multiple results processors:

```python
def __init__(
    self,
    service_config: ServiceConfig,
    user_config: UserConfig,
    service_id: str | None = None,
) -> None:
    super().__init__(
        service_config=service_config,
        user_config=user_config,
        service_id=service_id,
        pull_client_address=CommAddress.RECORDS,
        pull_client_bind=True,
        pull_client_max_concurrency=DEFAULT_PULL_CLIENT_MAX_CONCURRENCY,
    )

    # Protected by processing_status_lock
    self.processing_status_lock: asyncio.Lock = asyncio.Lock()
    self.start_time_ns: int | None = None
    self.processing_stats: ProcessingStats = ProcessingStats()
    self.final_request_count: int | None = None
    self.end_time_ns: int | None = None
    self.sent_all_records_received: bool = False
    self.profile_cancelled: bool = False
    self.timeout_triggered: bool = False
    self.expected_duration_sec: float | None = None

    self._completion_checker = PhaseCompletionChecker()

    self.error_summary: dict[ErrorDetails, int] = {}
    self.error_summary_lock: asyncio.Lock = asyncio.Lock()

    # Track per-worker statistics
    self.worker_stats: dict[str, ProcessingStats] = {}
    self.worker_stats_lock: asyncio.Lock = asyncio.Lock()

    self._previous_realtime_records: int | None = None

    # Initialize all results processors
    self._results_processors: list[ResultsProcessorProtocol] = []
    for results_processor_type in ResultsProcessorFactory.get_all_class_types():
        results_processor = ResultsProcessorFactory.create_instance(
            class_type=results_processor_type,
            service_id=self.service_id,
            service_config=self.service_config,
            user_config=self.user_config,
        )
        self.debug(
            f"Created results processor: {results_processor_type}: "
            f"{results_processor.__class__.__name__}"
        )
        self._results_processors.append(results_processor)
```

**Concurrency Design:**

- `DEFAULT_PULL_CLIENT_MAX_CONCURRENCY`: Typically 1000, allows parallel record processing
- Multiple locks protect shared state (`processing_status_lock`, `worker_stats_lock`, `error_summary_lock`)
- Asynchronous processing enables high throughput

## Results Aggregation

### Processing Statistics Model

The `ProcessingStats` model tracks overall progress:

```python
class ProcessingStats(AIPerfBaseModel):
    """Model for phase processing stats. How many requests were processed and
    how many errors were encountered."""

    processed: int = Field(
        default=0, description="The number of records processed successfully"
    )
    errors: int = Field(
        default=0, description="The number of record errors encountered"
    )
    total_expected_requests: int | None = Field(
        default=None,
        description="The total number of expected requests to process.",
    )

    @property
    def total_records(self) -> int:
        """The total number of records processed successfully or in error."""
        return self.processed + self.errors

    @property
    def is_complete(self) -> bool:
        return self.total_records == self.total_expected_requests
```

### Receiving Metric Records

The Records Manager receives metric records via a pull client:

```python
@on_pull_message(MessageType.METRIC_RECORDS)
async def _on_metric_records(self, message: MetricRecordsMessage) -> None:
    """Handle a metric records message."""
    if self.is_trace_enabled:
        self.trace(f"Received metric records: {message}")

    if message.credit_phase != CreditPhase.PROFILING:
        self.debug(lambda: f"Skipping non-profiling record: {message.credit_phase}")
        return

    should_include_request = self._should_include_request_by_duration(
        message.results
    )

    if should_include_request:
        await self._send_results_to_results_processors(message.results)

    worker_id = message.worker_id

    if message.valid and should_include_request:
        # Valid record
        async with self.worker_stats_lock:
            worker_stats = self.worker_stats.setdefault(
                worker_id, ProcessingStats()
            )
            worker_stats.processed += 1
        async with self.processing_status_lock:
            self.processing_stats.processed += 1
    elif message.valid and not should_include_request:
        # Timed out record
        self.debug(
            f"Filtered out record from worker {worker_id} - "
            f"response received after duration"
        )
    else:
        # Invalid record
        async with self.worker_stats_lock:
            worker_stats = self.worker_stats.setdefault(
                worker_id, ProcessingStats()
            )
            worker_stats.errors += 1
        async with self.processing_status_lock:
            self.processing_stats.errors += 1
        if message.error:
            async with self.error_summary_lock:
                self.error_summary[message.error] = (
                    self.error_summary.get(message.error, 0) + 1
                )

    await self._check_if_all_records_received()
```

**Processing Flow:**

1. Filter by phase (only profiling phase records are aggregated)
2. Check duration filtering (exclude late arrivals)
3. Send valid records to results processors for metric computation
4. Update statistics (per-worker and global)
5. Track errors in error summary
6. Check for phase completion

### Sending to Results Processors

Valid records are forwarded to all results processors:

```python
async def _send_results_to_results_processors(
    self, results: list[dict[MetricTagT, MetricValueTypeT]]
) -> None:
    """Send the results to each of the results processors."""
    await asyncio.gather(
        *[
            results_processor.process_result(result)
            for results_processor in self._results_processors
            for result in results
        ]
    )
```

This distributes results across multiple processors (e.g., `MetricResultsProcessor` for aggregation, streaming exporters, etc.), enabling parallel processing and diverse output formats.

### Worker Statistics Tracking

Per-worker statistics provide visibility into load distribution:

```python
# Track per-worker statistics
self.worker_stats: dict[str, ProcessingStats] = {}
self.worker_stats_lock: asyncio.Lock = asyncio.Lock()

# Update worker stats
async with self.worker_stats_lock:
    worker_stats = self.worker_stats.setdefault(worker_id, ProcessingStats())
    worker_stats.processed += 1
```

This enables detection of:
- Uneven load distribution (some workers processing many more requests)
- Worker failures (no records from specific workers)
- Performance bottlenecks (workers consistently slower)

## Phase Completion Detection

### Completion Checker Architecture

The `PhaseCompletionChecker` uses the Strategy pattern to detect phase completion. Located in `/home/anthony/nvidia/projects/aiperf/aiperf/records/phase_completion.py`:

```python
class PhaseCompletionChecker:
    """Orchestrates checking multiple completion conditions."""

    def __init__(self):
        self.conditions: list[PhaseCompletionCondition] = [
            AllRequestsProcessedCondition(),
            DurationTimeoutCondition(),
        ]

    def is_complete(
        self,
        processing_stats: ProcessingStats,
        final_request_count: int | None = None,
        timeout_triggered: bool = False,
        expected_duration_sec: float | None = None,
    ) -> tuple[bool, CompletionReason | None]:
        """Check if the phase is complete based on registered conditions."""
        context = PhaseCompletionContext(
            processing_stats=processing_stats,
            final_request_count=final_request_count,
            timeout_triggered=timeout_triggered,
            expected_duration_sec=expected_duration_sec,
        )

        for condition in self.conditions:
            if condition.is_satisfied(context):
                return True, condition.reason

        return False, None
```

### Completion Conditions

**AllRequestsProcessedCondition:**

```python
class AllRequestsProcessedCondition(PhaseCompletionCondition):
    """Completion condition for when all expected requests have been processed."""

    def is_satisfied(self, context: PhaseCompletionContext) -> bool:
        return (
            context.final_request_count is not None
            and context.processing_stats.total_records >= context.final_request_count
        )

    @property
    def reason(self) -> CompletionReason:
        return CompletionReason.ALL_REQUESTS_PROCESSED
```

This condition is satisfied when the Records Manager has received exactly (or more) records than were sent by the Timing Manager.

**DurationTimeoutCondition:**

```python
class DurationTimeoutCondition(PhaseCompletionCondition):
    """Completion condition for when the benchmark duration has elapsed."""

    def is_satisfied(self, context: PhaseCompletionContext) -> bool:
        return context.timeout_triggered and context.final_request_count is not None

    @property
    def reason(self) -> CompletionReason:
        return CompletionReason.DURATION_TIMEOUT
```

This condition is satisfied when the Timing Manager has triggered a timeout (grace period expired) and the final request count is known.

### Checking for Completion

The Records Manager checks for completion after processing each record:

```python
async def _check_if_all_records_received(self) -> None:
    """Check if all records have been received, and if so, publish a message
    and process the records."""
    all_records_received = False

    async with self.processing_status_lock:
        # Use the Strategy pattern for completion checking
        is_complete, completion_reason = self._completion_checker.is_complete(
            processing_stats=self.processing_stats,
            final_request_count=self.final_request_count,
            timeout_triggered=self.timeout_triggered,
            expected_duration_sec=self.expected_duration_sec,
        )
        all_records_received = is_complete

        if all_records_received:
            if (
                self.final_request_count is not None
                and self.processing_stats.total_records > self.final_request_count
            ):
                self.warning(
                    f"Processed {self.processing_stats.total_records:,} records, "
                    f"but only expected {self.final_request_count:,} records"
                )

            if self.sent_all_records_received:
                return
            self.sent_all_records_received = True

    if all_records_received:
        self.info(
            lambda: f"Processed {self.processing_stats.processed} valid requests "
            f"and {self.processing_stats.errors} errors "
            f"({self.processing_stats.total_records} total)."
        )
        # Make sure everyone knows the final stats
        await self._publish_processing_stats()

        async with self.processing_status_lock:
            cancelled = self.profile_cancelled
            proc_stats = copy.deepcopy(self.processing_stats)

        # Send a message to the event bus to signal that we received all records
        await self.publish(
            AllRecordsReceivedMessage(
                service_id=self.service_id,
                request_ns=time.time_ns(),
                final_processing_stats=proc_stats,
            )
        )

        self.debug("Received all records, processing now...")
        await self._process_results(cancelled=cancelled)
```

**Completion Flow:**

1. Check completion conditions with current state
2. If complete and not already sent, publish final stats
3. Publish `AllRecordsReceivedMessage` to event bus
4. Trigger final results processing

### Phase Message Handling

The Records Manager listens to phase lifecycle messages from the Timing Manager:

**Phase Start:**

```python
@on_message(MessageType.CREDIT_PHASE_START)
async def _on_credit_phase_start(
    self, phase_start_msg: CreditPhaseStartMessage
) -> None:
    """Handle a credit phase start message in order to track the total number
    of expected requests."""
    if phase_start_msg.phase != CreditPhase.PROFILING:
        return
    async with self.processing_status_lock:
        self.start_time_ns = phase_start_msg.start_ns
        self.expected_duration_sec = phase_start_msg.expected_duration_sec
        self.processing_stats.total_expected_requests = (
            phase_start_msg.total_expected_requests
        )
```

**Sending Complete:**

```python
@on_message(MessageType.CREDIT_PHASE_SENDING_COMPLETE)
async def _on_credit_phase_sending_complete(
    self, message: CreditPhaseSendingCompleteMessage
) -> None:
    """Handle a credit phase sending complete message in order to track the
    final request count."""
    if message.phase != CreditPhase.PROFILING:
        return
    # This will equate to how many records we expect to receive,
    # and once we receive that many records, we know to stop.
    async with self.processing_status_lock:
        self.final_request_count = message.sent
        self.info(
            f"Sent {self.final_request_count:,} requests. Waiting for completion..."
        )
```

**Phase Complete:**

```python
@on_message(MessageType.CREDIT_PHASE_COMPLETE)
async def _on_credit_phase_complete(
    self, message: CreditPhaseCompleteMessage
) -> None:
    """Handle a credit phase complete message in order to track the end time,
    and check if all records have been received."""
    if message.phase != CreditPhase.PROFILING:
        return
    async with self.processing_status_lock:
        if self.final_request_count is None:
            self.warning(
                f"Final request count was not set for profiling phase, "
                f"using {message.completed:,} as the final request count"
            )
            self.final_request_count = message.completed
        self.end_time_ns = message.end_ns
        self.timeout_triggered = message.timeout_triggered

        self.notice(
            f"All requests have completed, please wait for the results to be "
            f"processed (currently {self.processing_stats.total_records:,} of "
            f"{self.final_request_count:,} records processed)..."
        )
    # This check prevents a race condition
    await self._check_if_all_records_received()
```

## Duration Filtering

### Why Duration Filtering?

For time-based benchmarks, not all completed requests should be included in metrics:

```
Benchmark Duration: 60 seconds
Grace Period: 10 seconds

Timeline:
0s ────────────────────────────────── 60s ────────── 70s
    [  Benchmark Duration  ]  [ Grace Period ]
                           │
                         Last credit dropped
                                      │
                              Some requests still in-flight
                                      │
                          These complete during grace period
```

**Problem:** Requests that started before 60s but completed after 70s should be excluded from metrics to maintain accuracy.

**Solution:** Duration filtering based on final response timestamps.

### Filtering Implementation

```python
def _should_include_request_by_duration(
    self, results: list[dict[MetricTagT, MetricValueTypeT]]
) -> bool:
    """Determine if the request should be included based on benchmark duration.

    Args:
        results: List of metric results for a single request

    Returns:
        True if the request should be included, else False
    """
    if not self.expected_duration_sec:
        return True

    grace_period_sec = self.user_config.loadgen.benchmark_grace_period
    duration_end_ns = self.start_time_ns + int(
        (self.expected_duration_sec + grace_period_sec) * NANOS_PER_SECOND
    )

    # Check if any response in this request was received after the duration
    # If so, filter out the entire request (all-or-nothing approach)
    for result_dict in results:
        request_timestamp = result_dict.get(MinRequestTimestampMetric.tag)
        request_latency = result_dict.get(RequestLatencyMetric.tag)

        if request_timestamp is not None and request_latency is not None:
            final_response_timestamp = request_timestamp + request_latency

            if final_response_timestamp > duration_end_ns:
                self.debug(
                    f"Filtering out timed-out request - response received "
                    f"{final_response_timestamp - duration_end_ns} ns after timeout"
                )
                return False

    return True
```

**All-or-Nothing Approach:**

If ANY response in a multi-turn conversation arrives after the cutoff, the ENTIRE request is excluded. This prevents partial data from skewing metrics.

**Metrics Used:**

- `MinRequestTimestampMetric`: When the request started (wall clock time)
- `RequestLatencyMetric`: Total latency of the request

These are computed by the Record Processor and included in the `MetricRecordsMessage`.

## Error Tracking

### Error Summary Structure

The Records Manager maintains an error summary:

```python
self.error_summary: dict[ErrorDetails, int] = {}
self.error_summary_lock: asyncio.Lock = asyncio.Lock()
```

**ErrorDetails Structure:**

```python
class ErrorDetails(AIPerfBaseModel):
    """Details about an error that occurred."""

    error_type: str = Field(..., description="The type of error")
    error_message: str = Field(..., description="The error message")
    traceback: str | None = Field(default=None, description="The error traceback")
```

Errors are grouped by type and message, allowing identification of common failure patterns.

### Recording Errors

When a `MetricRecordsMessage` contains an error:

```python
if message.error:
    async with self.error_summary_lock:
        self.error_summary[message.error] = (
            self.error_summary.get(message.error, 0) + 1
        )
```

### Generating Error Summary

At the end of the benchmark:

```python
async def get_error_summary(self) -> list[ErrorDetailsCount]:
    """Generate a summary of the error records."""
    async with self.error_summary_lock:
        return [
            ErrorDetailsCount(error_details=error_details, count=count)
            for error_details, count in self.error_summary.items()
        ]
```

**ErrorDetailsCount:**

```python
class ErrorDetailsCount(AIPerfBaseModel):
    """Error details with count."""

    error_details: ErrorDetails
    count: int
```

This provides a ranked list of errors by frequency, making it easy to identify the most common issues.

## Results Processing

### Processing Trigger

Results processing is triggered when all records are received:

```python
async def _process_results(self, cancelled: bool) -> ProcessRecordsResult:
    """Process the results."""
    self.debug(lambda: f"Processing records (cancelled: {cancelled})")

    self.info("Processing records results...")
    # Process the records through the results processors.
    results = await asyncio.gather(
        *[
            results_processor.summarize()
            for results_processor in self._results_processors
        ],
        return_exceptions=True,
    )

    records_results, error_results = [], []
    for result in results:
        if isinstance(result, list):
            records_results.extend(result)
        elif isinstance(result, ErrorDetails):
            error_results.append(result)
        elif isinstance(result, BaseException):
            error_results.append(ErrorDetails.from_exception(result))

    result = ProcessRecordsResult(
        results=ProfileResults(
            records=records_results,
            completed=len(records_results),
            start_ns=self.start_time_ns or time.time_ns(),
            end_ns=self.end_time_ns or time.time_ns(),
            error_summary=await self.get_error_summary(),
            was_cancelled=cancelled,
        ),
        errors=error_results,
    )
    self.debug(lambda: f"Process records result: {result}")
    await self.publish(
        ProcessRecordsResultMessage(
            service_id=self.service_id,
            results=result,
        )
    )
    return result
```

**Processing Flow:**

1. Call `summarize()` on all results processors
2. Collect `MetricResult` objects and errors
3. Build `ProcessRecordsResult` with:
   - Computed metrics (`records_results`)
   - Error summary
   - Timing information (start_ns, end_ns)
   - Cancellation status
4. Publish `ProcessRecordsResultMessage` to event bus
5. Return result to caller (if triggered via command)

### Command-Based Processing

Results processing can also be triggered via command:

```python
@on_command(CommandType.PROCESS_RECORDS)
async def _on_process_records_command(
    self, message: ProcessRecordsCommand
) -> ProcessRecordsResult:
    """Handle the process records command by forwarding it to all of the
    results processors, and returning the results."""
    self.debug(lambda: f"Received process records command: {message}")
    return await self._process_results(cancelled=message.cancelled)
```

This allows the System Controller to explicitly request results processing (e.g., for testing or debugging).

### Profile Cancellation

The benchmark can be cancelled mid-execution:

```python
@on_command(CommandType.PROFILE_CANCEL)
async def _on_profile_cancel_command(
    self, message: ProfileCancelCommand
) -> ProcessRecordsResult:
    """Handle the profile cancel command by cancelling the streaming post
    processors."""
    self.debug(lambda: f"Received profile cancel command: {message}")
    async with self.processing_status_lock:
        self.profile_cancelled = True
    return await self._process_results(cancelled=True)
```

When cancelled, the `was_cancelled` flag is set in the results, allowing exporters to indicate the benchmark was aborted.

## Progress Reporting

### Periodic Progress Updates

A background task publishes progress at regular intervals:

```python
@background_task(interval=DEFAULT_RECORDS_PROGRESS_REPORT_INTERVAL, immediate=False)
async def _report_records_task(self) -> None:
    """Report the records processing stats."""
    if self.processing_stats.processed > 0 or self.processing_stats.errors > 0:
        # Only publish stats if there are records to report
        await self._publish_processing_stats()

async def _publish_processing_stats(self) -> None:
    """Publish the profile processing stats."""

    async with self.processing_status_lock, self.worker_stats_lock:
        proc_stats = copy.deepcopy(self.processing_stats)
        worker_stats = copy.deepcopy(self.worker_stats)

    message = RecordsProcessingStatsMessage(
        service_id=self.service_id,
        request_ns=time.time_ns(),
        processing_stats=proc_stats,
        worker_stats=worker_stats,
    )
    await self.publish(message)
```

**Default Interval:** `DEFAULT_RECORDS_PROGRESS_REPORT_INTERVAL` (typically 1 second)

**Message Contents:**

- Global processing stats (processed, errors, total)
- Per-worker breakdown

This enables the UI to display live progress during benchmark execution.

## Realtime Metrics

### Realtime Metrics Generation

For the dashboard UI, the Records Manager can generate real-time metrics:

```python
@background_task(interval=None, immediate=True)
async def _report_realtime_metrics_task(self) -> None:
    """Report the real-time metrics at a regular interval (only if the UI type
    is dashboard)."""
    if self.service_config.ui_type != AIPerfUIType.DASHBOARD:
        return
    while not self.stop_requested:
        await asyncio.sleep(DEFAULT_REALTIME_METRICS_INTERVAL)
        async with self.processing_status_lock:
            if (
                self.processing_stats.total_records
                == self._previous_realtime_records
            ):
                continue  # No new records, skip update
            self._previous_realtime_records = self.processing_stats.processed
        await self._report_realtime_metrics()

@on_command(CommandType.REALTIME_METRICS)
async def _on_realtime_metrics_command(
    self, message: RealtimeMetricsCommand
) -> None:
    """Handle a real-time metrics command."""
    await self._report_realtime_metrics()

async def _report_realtime_metrics(self) -> None:
    """Report the real-time metrics."""
    metrics = await self._generate_realtime_metrics()
    if not metrics:
        return
    await self.publish(
        RealtimeMetricsMessage(
            service_id=self.service_id,
            metrics=metrics,
        )
    )

async def _generate_realtime_metrics(self) -> list[MetricResult]:
    """Generate the real-time metrics for the profile run."""
    results = await asyncio.gather(
        *[
            results_processor.summarize()
            for results_processor in self._results_processors
        ],
        return_exceptions=True,
    )
    return [
        res
        for result in results
        if isinstance(result, list)
        for res in result
        if isinstance(res, MetricResult)
    ]
```

**Realtime Metrics Flow:**

1. Background task checks for new records every `DEFAULT_REALTIME_METRICS_INTERVAL` (typically 0.5s)
2. If new records processed, generate metrics via `summarize()`
3. Publish `RealtimeMetricsMessage` to event bus
4. Dashboard consumes and displays live metrics

**Performance Optimization:**

- Only generate metrics if new records have been processed
- Skip generation if no dashboard UI is active

## Concurrency and Locking

### Lock Strategy

The Records Manager uses three locks:

**processing_status_lock:**
- Protects: `processing_stats`, `final_request_count`, `start_time_ns`, `end_time_ns`, etc.
- Used by: Record processing, phase message handling, completion checking

**worker_stats_lock:**
- Protects: `worker_stats` dictionary
- Used by: Record processing, progress reporting

**error_summary_lock:**
- Protects: `error_summary` dictionary
- Used by: Error recording, error summary generation

### Lock Ordering

To prevent deadlocks, locks are always acquired in the same order:

```python
async with self.processing_status_lock, self.worker_stats_lock:
    proc_stats = copy.deepcopy(self.processing_stats)
    worker_stats = copy.deepcopy(self.worker_stats)
```

**Never** acquire in reverse order or nest differently across methods.

### High Concurrency Processing

The pull client supports high concurrency:

```python
pull_client_max_concurrency=DEFAULT_PULL_CLIENT_MAX_CONCURRENCY,  # 1000
```

This means up to 1000 `_on_metric_records()` calls can execute concurrently, requiring careful lock management to prevent contention.

**Best Practices:**

- Keep critical sections small
- Use `copy.deepcopy()` to snapshot state before releasing lock
- Prefer immutable data structures where possible

## Performance Implications

### Memory Usage

Each metric record consumes memory until final processing:

**Per Record:**
- MetricRecordsMessage: ~500 bytes
- Forwarded to results processors: additional ~300 bytes per processor

**For 10,000 requests:**
- Direct memory: 5 MB
- Results processor memory: 3 MB per processor (typically 2 processors = 6 MB)
- Total: ~11 MB

### Processing Latency

**Record Processing Pipeline:**

```
Worker → ZMQ → Record Processor → ZMQ → Records Manager → Results Processors
  ~100μs    ~50μs      ~200μs      ~50μs     ~100μs            ~500μs
```

**Total per-record latency:** ~1ms

For 10,000 RPS, this means the Records Manager can easily keep up.

### Lock Contention

With high concurrency (1000 concurrent handlers), lock contention can become a bottleneck:

**Mitigation Strategies:**

1. **Sharding:** Split statistics across multiple dictionaries with separate locks
2. **Lock-Free Structures:** Use atomic operations for simple counters
3. **Batching:** Accumulate multiple records before acquiring lock

**Current Design:**

AIPerf's current design is optimized for typical workloads (1000-10000 RPS). For extreme loads (>100,000 RPS), sharding or lock-free structures may be needed.

## Best Practices

### Error Handling

Always check for errors in received records:

```python
if message.error:
    # Track error
    async with self.error_summary_lock:
        self.error_summary[message.error] = (
            self.error_summary.get(message.error, 0) + 1
        )
    # Update error stats
    async with self.processing_status_lock:
        self.processing_stats.errors += 1
```

### Progress Monitoring

Monitor key metrics:

```python
# Processing rate
records_per_sec = processing_stats.total_records / elapsed_time_sec

# Error rate
error_rate = processing_stats.errors / processing_stats.total_records

# Worker utilization
for worker_id, stats in worker_stats.items():
    worker_utilization = stats.total_records / processing_stats.total_records
```

### Duration Filtering Configuration

**Too Aggressive (short grace period):**
- May exclude valid late arrivals
- Reduces measured throughput

**Too Lenient (long grace period):**
- May include requests that started after duration
- Inflates measured throughput

**Recommendation:**
- Set grace period to 2-3x p99 latency
- For typical inference: 5-10 seconds

### Completion Detection

Always check both conditions:

```python
# Condition 1: All requests processed (count-based or exhausted time-based)
if (
    final_request_count is not None
    and processing_stats.total_records >= final_request_count
):
    # Complete!

# Condition 2: Timeout triggered (time-based with grace period expired)
if timeout_triggered and final_request_count is not None:
    # Complete (possibly with in-flight requests)
```

## Troubleshooting

### Records Manager Never Completes

**Symptoms:**
- Processing stats show fewer records than expected
- Phase hangs in COMPLETE state

**Causes:**
1. Record Processors crashed without sending messages
2. Network partition
3. ZMQ socket issues

**Solutions:**
- Enable detailed logging
- Check Record Processor health
- Implement timeout-based completion fallback

### Memory Growth

**Symptoms:**
- Memory usage grows unbounded
- OOM errors

**Causes:**
1. Results processors accumulating data without bounds
2. Error summary growing excessively large
3. Worker stats accumulating for terminated workers

**Solutions:**
- Implement results processor streaming/summarization
- Cap error summary size (e.g., top 100 unique errors)
- Clean up worker stats for inactive workers

### Incorrect Metrics

**Symptoms:**
- Metrics don't match expected values
- Throughput too high or too low

**Causes:**
1. Duration filtering misconfigured
2. Including warmup phase records
3. Duplicate records

**Solutions:**
- Verify duration filtering logic
- Ensure only profiling phase records are aggregated
- Add request deduplication (via request_id)

## Key Takeaways

1. **Central Aggregation**: The Records Manager is the convergence point for all benchmark results, aggregating data from distributed workers.

2. **Phase Completion Detection**: Uses Strategy pattern with multiple conditions (all requests processed, duration timeout) to detect phase completion.

3. **Duration Filtering**: For time-based benchmarks, filters out requests that completed after the benchmark duration + grace period to maintain accuracy.

4. **Error Tracking**: Maintains an error summary grouped by error type and message, enabling identification of common failure patterns.

5. **Results Processing**: Coordinates final metric computation by calling `summarize()` on all results processors and aggregating their outputs.

6. **Progress Reporting**: Publishes periodic progress updates (processing stats, worker stats) for live monitoring and UI display.

7. **Realtime Metrics**: For dashboard UI, generates and publishes real-time metrics at regular intervals during benchmark execution.

8. **Concurrency Management**: Uses multiple locks (processing_status_lock, worker_stats_lock, error_summary_lock) to protect shared state while supporting high concurrency (1000 concurrent handlers).

9. **High Throughput**: Pull client with high max concurrency enables processing of thousands of records per second with low latency.

10. **Extensible Processing**: Results processors are registered via factory pattern, enabling easy addition of custom aggregation or export logic.

Next: [Chapter 13: Record Processors](chapter-13-record-processors.md)
