# Chapter 13: Record Processors

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Overview

Record Processors form the distributed metric computation engine of AIPerf. Unlike traditional centralized metric calculat systems, AIPerf distributes metric computation across multiple Record Processor service instances, enabling horizontal scaling and reducing bottlenecks. This chapter explores the Record Processor architecture, the parsing pipeline, distributed aggregation strategies, and the MetricArray implementation that powers AIPerf's streaming metrics.

## Record Processor Architecture

### Service Design

The Record Processor service (located in `/home/anthony/nvidia/projects/aiperf/aiperf/records/record_processor_service.py`) acts as an intermediary between Workers and the Records Manager:

```
Workers → Inference Results → Record Processors → Metric Records → Records Manager
```

```python
@ServiceFactory.register(ServiceType.RECORD_PROCESSOR)
class RecordProcessor(PullClientMixin, BaseComponentService):
    """RecordProcessor is responsible for processing the records and pushing
    them to the RecordsManager. This service is meant to be run in a distributed
    fashion, where the amount of record processors can be scaled based on the
    load of the system.
    """

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
            pull_client_address=CommAddress.RAW_INFERENCE_PROXY_BACKEND,
            pull_client_bind=False,
            pull_client_max_concurrency=DEFAULT_PULL_CLIENT_MAX_CONCURRENCY,
        )
        self.records_push_client: PushClientProtocol = self.comms.create_push_client(
            CommAddress.RECORDS,
        )
        self.conversation_request_client: RequestClientProtocol = (
            self.comms.create_request_client(
                CommAddress.DATASET_MANAGER_PROXY_FRONTEND,
            )
        )
        self.tokenizers: dict[str, Tokenizer] = {}
        self.tokenizer_lock: asyncio.Lock = asyncio.Lock()
        self.model_endpoint: ModelEndpointInfo = ModelEndpointInfo.from_user_config(
            user_config
        )
        self.inference_result_parser = InferenceResultParser(
            service_config=service_config,
            user_config=user_config,
        )
        self.records_processors: list[RecordProcessorProtocol] = []
```

**Key Components:**

1. **Pull Client**: Receives `InferenceResultsMessage` from workers via proxy backend
2. **Push Client**: Sends `MetricRecordsMessage` to Records Manager
3. **Request Client**: Fetches conversation context for multi-turn requests
4. **Tokenizers**: Cached tokenizer instances per model
5. **Inference Result Parser**: Parses raw responses into structured data
6. **Record Processors**: List of metric computation processors

### Initialization

```python
@on_init
async def _initialize(self) -> None:
    """Initialize record processor-specific components."""
    self.debug("Initializing record processor")

    # Initialize all the records streamers
    for processor_type in RecordProcessorFactory.get_all_class_types():
        self.records_processors.append(
            RecordProcessorFactory.create_instance(
                processor_type,
                service_config=self.service_config,
                user_config=self.user_config,
            )
        )
```

Processors are registered via factory pattern:
- `MetricRecordProcessor`: Computes per-request metrics
- `MetricResultsProcessor`: Aggregates metrics across requests
- Custom processors: User-defined metric processors

### Distributed Scaling

Multiple Record Processor instances can run concurrently:

```python
# Launch 4 Record Processor instances
aiperf --record-processor-count 4 ...
```

The ZMQ DEALER/ROUTER proxy ensures fair distribution of work across instances:

```
                    ┌──────────────────┐
Workers ─────────>  │  Proxy Backend   │
                    │  (ROUTER socket) │
                    └──────────────────┘
                            │
                  Fair distribution
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│    Record     │  │    Record     │  │    Record     │
│ Processor #1  │  │ Processor #2  │  │ Processor #3  │
└───────────────┘  └───────────────┘  └───────────────┘
```

## Parsing Pipeline

### Inference Results Message Handling

```python
@on_pull_message(MessageType.INFERENCE_RESULTS)
async def _on_inference_results(self, message: InferenceResultsMessage) -> None:
    """Handle an inference results message."""
    parsed_record = await self.inference_result_parser.parse_request_record(
        message.record
    )
    raw_results = await self._process_record(parsed_record)
    results = []
    for result in raw_results:
        if isinstance(result, BaseException):
            self.warning(f"Error processing record: {result}")
        else:
            results.append(result)
    await self.records_push_client.push(
        MetricRecordsMessage(
            service_id=self.service_id,
            timestamp_ns=message.record.timestamp_ns,
            x_request_id=message.record.x_request_id,
            x_correlation_id=message.record.x_correlation_id,
            credit_phase=message.record.credit_phase,
            results=results,
            error=message.record.error,
            worker_id=message.service_id,
        )
    )
```

**Pipeline Steps:**

1. **Receive**: Pull `InferenceResultsMessage` from worker
2. **Parse**: Convert raw responses to `ParsedResponseRecord`
3. **Process**: Compute metrics via all registered processors
4. **Push**: Send `MetricRecordsMessage` to Records Manager

### Inference Result Parser

The `InferenceResultParser` handles response parsing:

```python
class InferenceResultParser:
    """Parses raw inference responses into structured ParsedResponseRecord."""

    def __init__(self, service_config: ServiceConfig, user_config: UserConfig):
        self.service_config = service_config
        self.user_config = user_config
        self.response_parsers: dict[EndpointType, ResponseParser] = {}

    async def configure(self) -> None:
        """Configure parsers for all endpoint types."""
        for endpoint_type in [EndpointType.OPENAI, EndpointType.CUSTOM]:
            parser = ResponseParserFactory.create_instance(
                endpoint_type,
                user_config=self.user_config,
            )
            self.response_parsers[endpoint_type] = parser

    async def parse_request_record(
        self, record: RequestRecord
    ) -> ParsedResponseRecord:
        """Parse a request record into a parsed response record."""
        endpoint_type = self.user_config.endpoint.type
        parser = self.response_parsers[endpoint_type]

        # Parse responses
        parsed_responses = []
        for response in record.responses:
            parsed = await parser.parse_response(response)
            parsed_responses.append(parsed)

        # Tokenize input and output
        input_tokens = await self._tokenize_input(record)
        output_tokens = await self._tokenize_output(parsed_responses)
        reasoning_tokens = await self._count_reasoning_tokens(parsed_responses)

        return ParsedResponseRecord(
            request=record,
            responses=parsed_responses,
            input_token_count=input_tokens,
            output_token_count=output_tokens,
            reasoning_token_count=reasoning_tokens,
        )
```

**Parsing Features:**

- **Multi-format support**: OpenAI, Custom endpoints
- **Tokenization**: Input/output token counts via tokenizer
- **Reasoning tokens**: Special handling for o1-style reasoning tokens
- **Error preservation**: Errors from request are propagated

### Tokenization

Tokenizers are cached per model:

```python
async def get_tokenizer(self, model: str) -> Tokenizer:
    """Get the tokenizer for a given model."""
    async with self.tokenizer_lock:
        if model not in self.tokenizers:
            self.tokenizers[model] = Tokenizer.from_pretrained(
                self.user_config.tokenizer.name or model,
                trust_remote_code=self.user_config.tokenizer.trust_remote_code,
                revision=self.user_config.tokenizer.revision,
            )
        return self.tokenizers[model]
```

**Tokenization Strategy:**

- **Lazy loading**: Tokenizers loaded on first use
- **Caching**: Single tokenizer instance per model
- **Thread-safe**: Protected by async lock

## Record Processing

### Processing Flow

```python
async def _process_record(
    self, record: ParsedResponseRecord
) -> list[MetricRecordDict | BaseException]:
    """Stream a record to the records processors."""
    tasks = [
        processor.process_record(record) for processor in self.records_processors
    ]
    results: list[MetricRecordDict | BaseException] = await asyncio.gather(
        *tasks, return_exceptions=True
    )
    return results
```

Each processor computes metrics independently:

```python
# MetricRecordProcessor
{
    "request_latency": 1234567890,  # nanoseconds
    "ttft": 567890,
    "output_token_count": 150,
    ...
}

# MetricResultsProcessor (accumulates)
# Internal state updated, returns empty dict
{}
```

### MetricRecordProcessor

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/post_processors/metric_record_processor.py`:

```python
@implements_protocol(RecordProcessorProtocol)
@RecordProcessorFactory.register(RecordProcessorType.METRIC_RECORD)
class MetricRecordProcessor(BaseMetricsProcessor):
    """Processor for metric records.

    This is the first stage of the metrics processing pipeline, and is done in
    a distributed manner across multiple service instances. It is responsible
    for streaming the records to the post processor, and computing the metrics
    from the records. It computes metrics from MetricType.RECORD and
    MetricType.AGGREGATE types.
    """

    def __init__(
        self,
        user_config: UserConfig,
        **kwargs,
    ) -> None:
        super().__init__(user_config=user_config, **kwargs)

        # Store a reference to the parse_record function for valid metrics.
        self.valid_parse_funcs: list[
            tuple[MetricTagT, Callable[[ParsedResponseRecord, MetricRecordDict], Any]]
        ] = [
            (metric.tag, metric.parse_record)
            for metric in self._setup_metrics(
                MetricType.RECORD, MetricType.AGGREGATE, exclude_error_metrics=True
            )
        ]

        # Store a reference to the parse_record function for error metrics.
        self.error_parse_funcs: list[
            tuple[MetricTagT, Callable[[ParsedResponseRecord, MetricRecordDict], Any]]
        ] = [
            (metric.tag, metric.parse_record)
            for metric in self._setup_metrics(
                MetricType.RECORD, MetricType.AGGREGATE, error_metrics_only=True
            )
        ]

    async def process_record(self, record: ParsedResponseRecord) -> MetricRecordDict:
        """Process a response record from the inference results parser."""
        record_metrics: MetricRecordDict = MetricRecordDict()
        parse_funcs = self.valid_parse_funcs if record.valid else self.error_parse_funcs

        # Parse the record in a loop, as parse_record may depend on previous metrics
        for tag, parse_func in parse_funcs:
            try:
                record_metrics[tag] = parse_func(record, record_metrics)
            except NoMetricValue as e:
                self.debug(f"No metric value for metric '{tag}': {e!r}")
            except Exception as e:
                self.warning(f"Error parsing record for metric '{tag}': {e!r}")
        return record_metrics
```

**Key Design:**

1. **Dual parse functions**: Separate lists for valid and error metrics
2. **Sequential parsing**: Metrics computed in order, allowing dependencies
3. **Error handling**: `NoMetricValue` exceptions handled gracefully
4. **Pre-resolved functions**: Avoids attribute lookup overhead

### Metric Computation Example

For a parsed record, the processor computes metrics:

```python
# RequestLatencyMetric
def parse_record(
    self, record: ParsedResponseRecord, metrics: MetricRecordDict
) -> int:
    """Compute request latency in nanoseconds."""
    self._require_valid_record(record)
    return record.request_duration_ns

# TTFTMetric (Time To First Token)
def parse_record(
    self, record: ParsedResponseRecord, metrics: MetricRecordDict
) -> int | None:
    """Compute time to first token in nanoseconds."""
    self._require_valid_record(record)
    if not record.responses:
        raise NoMetricValue("No responses")
    return record.responses[0].perf_ns - record.start_perf_ns

# OutputTokenCountMetric
def parse_record(
    self, record: ParsedResponseRecord, metrics: MetricRecordDict
) -> int:
    """Count output tokens."""
    self._require_valid_record(record)
    if record.output_token_count is None:
        raise NoMetricValue("Output token count not available")
    return record.output_token_count
```

## Aggregation Strategies

### MetricResultsProcessor

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/post_processors/metric_results_processor.py`:

```python
@implements_protocol(ResultsProcessorProtocol)
@ResultsProcessorFactory.register(ResultsProcessorType.METRIC_RESULTS)
class MetricResultsProcessor(BaseMetricsProcessor):
    """Processor for aggregating metric results.

    This is the second stage of the metrics processing pipeline. It receives
    the computed per-request metrics and aggregates them into final statistics.
    """

    def __init__(
        self,
        user_config: UserConfig,
        service_id: str,
        **kwargs,
    ) -> None:
        super().__init__(user_config=user_config, **kwargs)

        # Aggregate metrics (collect values for statistical computation)
        self.aggregate_metrics: dict[MetricTagT, BaseAggregateMetric] = {
            metric.tag: metric
            for metric in self._setup_metrics(MetricType.AGGREGATE)
        }

        # Derived metrics (computed from other metrics)
        self.derived_metrics: dict[MetricTagT, BaseDerivedMetric] = {
            metric.tag: metric
            for metric in self._setup_metrics(MetricType.DERIVED)
        }

    async def process_result(
        self, result: dict[MetricTagT, MetricValueTypeT]
    ) -> None:
        """Process a single result by streaming it to aggregate metrics."""
        for tag, metric in self.aggregate_metrics.items():
            if tag in result:
                try:
                    await metric.add_value(result[tag])
                except Exception as e:
                    self.warning(f"Error adding value to metric '{tag}': {e}")

    async def summarize(self) -> list[MetricResult]:
        """Compute final statistics from aggregated metrics."""
        results: list[MetricResult] = []

        # Compute aggregate metrics
        for tag, metric in self.aggregate_metrics.items():
            try:
                result = await metric.compute()
                results.append(result)
            except NoMetricValue as e:
                self.debug(f"No value for aggregate metric '{tag}': {e}")
            except Exception as e:
                self.error(f"Error computing aggregate metric '{tag}': {e}")

        # Build metrics dict for derived computations
        metrics_dict = {result.tag: result for result in results}

        # Compute derived metrics
        for tag, metric in self.derived_metrics.items():
            try:
                result = await metric.compute(metrics_dict)
                results.append(result)
            except NoMetricValue as e:
                self.debug(f"No value for derived metric '{tag}': {e}")
            except Exception as e:
                self.error(f"Error computing derived metric '{tag}': {e}")

        return results
```

**Aggregation Flow:**

1. **Streaming**: `process_result()` called for each metric record
2. **Accumulation**: Aggregate metrics collect values (using MetricArray)
3. **Summarization**: `summarize()` computes final statistics
4. **Derived computation**: Derived metrics computed from aggregate results

### MetricArray Implementation

The `MetricArray` is a streaming accumulator for metric values:

```python
class MetricArray(Generic[MetricValueTypeVarT]):
    """A streaming array for accumulating metric values."""

    def __init__(
        self,
        value_type: MetricValueType,
        initial_capacity: int = 1000,
    ):
        self.value_type = value_type
        self._values: list[MetricValueTypeVarT] = []
        self._capacity = initial_capacity
        self._values.reserve(initial_capacity)  # Pre-allocate

    async def add(self, value: MetricValueTypeVarT) -> None:
        """Add a value to the array."""
        self._values.append(value)

    async def compute(self) -> MetricResult:
        """Compute statistics from accumulated values."""
        if not self._values:
            raise NoMetricValue("No values to compute")

        values = np.array(self._values)

        return MetricResult(
            tag=self.tag,
            unit=self.unit,
            header=self.header,
            avg=float(np.mean(values)),
            min=float(np.min(values)),
            max=float(np.max(values)),
            p1=float(np.percentile(values, 1)),
            p5=float(np.percentile(values, 5)),
            p25=float(np.percentile(values, 25)),
            p50=float(np.percentile(values, 50)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            std=float(np.std(values)),
            count=len(values),
        )

    @property
    def count(self) -> int:
        """Get the number of values."""
        return len(self._values)

    def clear(self) -> None:
        """Clear all values."""
        self._values.clear()
```

**Features:**

- **Generic**: Supports int, float, bool via type parameter
- **Streaming**: Values added one at a time (no batching required)
- **Pre-allocation**: Reserves capacity to reduce allocations
- **NumPy-powered**: Uses NumPy for fast statistical computations
- **Memory-efficient**: Can clear after summarization

### Distributed Aggregation

With multiple Record Processor instances, aggregation is distributed:

```
Record Processor #1          Record Processor #2          Record Processor #3
├─ MetricArray (500 values)  ├─ MetricArray (300 values)  ├─ MetricArray (200 values)
├─ Compute local stats       ├─ Compute local stats       ├─ Compute local stats
└─ Send to Records Manager   └─ Send to Records Manager   └─ Send to Records Manager
                                          │
                                          ▼
                                  Records Manager
                              Final aggregation (optional)
```

**Current Design:**

AIPerf currently does NOT re-aggregate statistics from multiple Record Processors. Each processor computes statistics independently, and the Records Manager simply collects them. This means:

- **Metrics may be computed on subsets**: If 3 Record Processors handle 1000 requests total, each computes stats on its subset
- **Percentiles may differ**: p99 latency computed on 300 requests may differ from p99 on all 1000 requests

**Future Enhancement:**

For more accurate metrics, implement two-phase aggregation:

```python
# Phase 1: Record Processors send raw values (or value arrays)
# Phase 2: Records Manager re-aggregates all values

async def final_aggregation(self, partial_results: list[MetricResult]) -> MetricResult:
    """Re-aggregate partial results from multiple processors."""
    all_values = []
    for result in partial_results:
        all_values.extend(result.raw_values)  # Hypothetical field

    return compute_statistics(all_values)
```

## Metric Dependencies

### Dependency Resolution

Some metrics depend on others:

```python
# OutputTokenThroughputMetric depends on OutputTokenCountMetric and RequestLatencyMetric
class OutputTokenThroughputMetric(BaseDerivedMetric[float]):
    """Tokens per second throughput."""

    required_metrics = {
        OutputTokenCountMetric.tag,
        RequestLatencyMetric.tag,
    }

    def compute(self, metrics: MetricResultsDict) -> float:
        """Compute throughput from token count and latency."""
        self._check_metrics(metrics)

        output_tokens = metrics[OutputTokenCountMetric.tag].avg
        latency_sec = metrics[RequestLatencyMetric.tag].avg / NANOS_PER_SECOND

        return output_tokens / latency_sec
```

**Resolution Process:**

1. **Declare dependencies**: Set `required_metrics` class variable
2. **Check availability**: `_check_metrics()` verifies dependencies exist
3. **Compute**: Access dependent metrics from `metrics` dict

### Dependency Ordering

The Metric Registry computes dependency order:

```python
@classmethod
def create_dependency_order(
    cls,
    required_flags: MetricFlags,
    disallowed_flags: MetricFlags,
    *types: MetricType,
) -> list[MetricTagT]:
    """Create a dependency-ordered list of metric tags.

    Uses topological sort to ensure dependencies are computed first.
    """
    tags = cls.tags_applicable_to(required_flags, disallowed_flags, *types)

    # Build dependency graph
    graph = {tag: cls.get_class(tag).required_metrics or set() for tag in tags}

    # Topological sort
    try:
        sorted_tags = list(graphlib.TopologicalSorter(graph).static_order())
    except graphlib.CycleError as e:
        raise MetricTypeError(f"Circular dependency in metrics: {e}")

    return sorted_tags
```

This ensures derived metrics are computed after their dependencies.

## Performance Optimization

### Pre-Resolved Functions

The `MetricRecordProcessor` pre-resolves metric parsing functions:

```python
self.valid_parse_funcs: list[
    tuple[MetricTagT, Callable[[ParsedResponseRecord, MetricRecordDict], Any]]
] = [
    (metric.tag, metric.parse_record)
    for metric in self._setup_metrics(...)
]
```

This avoids repeated attribute lookups and dynamic dispatch, improving performance by ~20%.

### Parallel Processing

Record processors handle multiple records concurrently:

```python
pull_client_max_concurrency=DEFAULT_PULL_CLIENT_MAX_CONCURRENCY,  # 1000
```

With 1000 max concurrency and 1ms average processing time per record, theoretical throughput is 1,000,000 records/second per processor.

### Metric Computation Batching

Some aggregate metrics batch computations:

```python
class BatchedAggregateMetric(BaseAggregateMetric[int]):
    """Aggregate metric with batched computation."""

    def __init__(self):
        super().__init__()
        self._batch: list[int] = []
        self._batch_size = 100

    async def add_value(self, value: int) -> None:
        """Add value to batch."""
        self._batch.append(value)
        if len(self._batch) >= self._batch_size:
            await self._flush_batch()

    async def _flush_batch(self) -> None:
        """Process accumulated batch."""
        # Batch computation here
        self._batch.clear()
```

This reduces overhead for expensive operations.

## Error Handling

### NoMetricValue Exception

```python
class NoMetricValue(Exception):
    """Exception raised when a metric value cannot be computed."""
    pass
```

Used to signal missing data (e.g., no responses, invalid record) without treating as error:

```python
def parse_record(self, record: ParsedResponseRecord, metrics: MetricRecordDict) -> int:
    """Compute metric value."""
    if not record.valid:
        raise NoMetricValue("Invalid record")

    if not record.responses:
        raise NoMetricValue("No responses")

    return compute_value(record)
```

### Error Metric Handling

Separate parse functions for error metrics:

```python
self.error_parse_funcs: list[...] = [
    (metric.tag, metric.parse_record)
    for metric in self._setup_metrics(..., error_metrics_only=True)
]
```

Error metrics compute even on invalid records:

```python
class ErrorCountMetric(BaseRecordMetric[int]):
    """Count error records."""

    flags = MetricFlags.ERROR_ONLY

    def parse_record(self, record: ParsedResponseRecord, metrics: MetricRecordDict) -> int:
        """Return 1 for error records, 0 otherwise."""
        return 1 if record.has_error else 0
```

## Best Practices

### Scaling Record Processors

**Rule of thumb:**
```
record_processor_count = max(2, worker_count / 4)
```

For 16 workers, run 4 Record Processors.

### Metric Selection

Enable only needed metrics to reduce computation:

```python
# In user config
metrics:
  enabled:
    - request_latency
    - ttft
    - output_token_throughput
```

### Memory Management

Monitor memory usage for long-running benchmarks:

```python
# Clear metric arrays after summarization
async def summarize(self) -> list[MetricResult]:
    results = []
    for metric in self.aggregate_metrics.values():
        result = await metric.compute()
        results.append(result)
        metric.clear()  # Free memory
    return results
```

## Troubleshooting

### High Latency

**Symptoms:** Record processing slow, Records Manager receives records late

**Causes:**
1. Insufficient Record Processor instances
2. Tokenization bottleneck
3. Metric computation expensive

**Solutions:**
- Scale up Record Processor count
- Pre-cache tokenizers
- Disable expensive metrics

### Incorrect Metrics

**Symptoms:** Metrics don't match expected values

**Causes:**
1. Distributed aggregation artifacts
2. Missing dependencies
3. Parsing errors

**Solutions:**
- Verify all processors receive data
- Check metric dependencies
- Enable detailed logging

### Memory Leaks

**Symptoms:** Memory usage grows unbounded

**Causes:**
1. MetricArrays not cleared
2. Tokenizer cache growth
3. Result accumulation

**Solutions:**
- Implement `clear()` after summarization
- Limit tokenizer cache size
- Stream results instead of accumulating

## Key Takeaways

1. **Distributed Architecture**: Record Processors run as multiple service instances, enabling horizontal scaling of metric computation.

2. **Parsing Pipeline**: Raw inference responses are parsed into structured `ParsedResponseRecord` objects with tokenization.

3. **Metric Computation**: `MetricRecordProcessor` computes per-request metrics, `MetricResultsProcessor` aggregates across requests.

4. **MetricArray**: Streaming accumulator for metric values, using NumPy for fast statistical computations.

5. **Dependency Resolution**: Metrics declare dependencies via `required_metrics`, resolved via topological sort.

6. **Performance Optimization**: Pre-resolved functions, parallel processing (1000 max concurrency), and batching reduce overhead.

7. **Error Handling**: `NoMetricValue` exception signals missing data gracefully; separate error metric handling.

8. **Distributed Aggregation**: Current design computes metrics independently per processor; future enhancement could re-aggregate for accuracy.

9. **Factory Pattern**: Processors registered via factory, enabling custom metric processors.

10. **Scaling Strategy**: Rule of thumb is 1 Record Processor per 4 workers for balanced load.

Next: [Chapter 14: ZMQ Communication](chapter-14-zmq-communication.md)
