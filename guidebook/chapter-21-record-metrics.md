# Chapter 21: Record Metrics

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Navigation
- Previous: [Chapter 20: Metrics Foundation](chapter-20-metrics-foundation.md)
- Next: [Chapter 22: Aggregate and Derived Metrics](chapter-22-aggregate-derived-metrics.md)
- [Table of Contents](INDEX.md)

## Overview

Record metrics form the foundation of AIPerf's metrics system. These metrics compute individual values for each request-response pair, enabling per-request analysis and forming the basis for aggregate and derived metrics. This chapter provides a comprehensive examination of the record metrics architecture, implementation patterns, and the built-in metrics that AIPerf provides.

Record metrics operate independently on each request record, extracting timing information, token counts, and other per-request characteristics. They are the first stage in AIPerf's three-tiered metrics architecture (Record → Aggregate → Derived).

## Key Concepts

### What is a Record Metric?

A record metric computes a value for each individual request-response record. These metrics:

- **Operate Independently**: Each record is processed without knowledge of other records
- **Support Dependencies**: Can depend on other record metrics computed earlier
- **Enable Statistical Analysis**: Produce lists of values suitable for percentile and distribution calculations
- **Form Building Blocks**: Serve as inputs to aggregate and derived metrics

### Metric Value Types

Record metrics can produce different value types:

```python
# Integer metrics (e.g., token counts, timestamps)
class InputSequenceLengthMetric(BaseRecordMetric[int]):
    pass

# Float metrics (e.g., computed ratios, normalized values)
class InterTokenLatencyMetric(BaseRecordMetric[float]):
    pass

# List metrics (e.g., per-token latencies)
class TokenLatenciesMetric(BaseRecordMetric[list[int]]):
    pass
```

## Architecture

### BaseRecordMetric Class

The foundation of all record metrics is the `BaseRecordMetric` class:

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/base_record_metric.py`

```python
class BaseRecordMetric(
    Generic[MetricValueTypeVarT], BaseMetric[MetricValueTypeVarT], ABC
):
    """A base class for record-based metrics. These metrics are computed for each record,
    and are independent of other records. The final results will be a list of values, one for each record.

    NOTE: Set the generic type to be the type of the individual values, and NOT a list, unless the metric produces
    a list *for every record*. In that case, the result will be a list of lists.
    """

    type = MetricType.RECORD

    def parse_record(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> MetricValueTypeVarT:
        """Parse a single record and return the metric value."""
        self._require_valid_record(record)
        self._check_metrics(record_metrics)
        return self._parse_record(record, record_metrics)

    @abstractmethod
    def _parse_record(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> MetricValueTypeVarT:
        """Parse a single record and return the metric value. This method is implemented by subclasses.
        This method is called after the required metrics are checked, so it can assume that the required metrics are available.
        This method is called after the record is checked, so it can assume that the record is valid.

        Raises:
            ValueError: If the metric cannot be computed for the given inputs.
        """
        raise NotImplementedError("Subclasses must implement this method")
```

### Key Design Features

#### 1. Generic Type System

Record metrics use Python's generic type system to enforce type safety:

```python
# The generic parameter specifies the value type for EACH RECORD
BaseRecordMetric[int]      # Each record produces an integer
BaseRecordMetric[float]    # Each record produces a float
BaseRecordMetric[list[int]] # Each record produces a list of integers
```

The final result across all records is always a list:
- `BaseRecordMetric[int]` → `list[int]` (one value per record)
- `BaseRecordMetric[float]` → `list[float]` (one value per record)
- `BaseRecordMetric[list[int]]` → `list[list[int]]` (one list per record)

#### 2. Validation Pipeline

The `parse_record` method implements a validation pipeline:

1. **Record Validation**: Ensures the record is valid and complete
2. **Dependency Check**: Verifies required metrics are available
3. **Computation**: Delegates to subclass `_parse_record` implementation

```python
def parse_record(
    self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
) -> MetricValueTypeVarT:
    # Step 1: Validate the record
    self._require_valid_record(record)

    # Step 2: Check dependencies
    self._check_metrics(record_metrics)

    # Step 3: Compute the metric
    return self._parse_record(record, record_metrics)
```

#### 3. Error Handling

Record metrics use exceptions to signal when values cannot be computed:

```python
from aiperf.common.exceptions import NoMetricValue

def _parse_record(self, record: ParsedResponseRecord, record_metrics: MetricRecordDict) -> int:
    if len(record.responses) < 1:
        raise NoMetricValue("Record must have at least one response to calculate TTFT.")

    # Normal computation continues...
```

The `NoMetricValue` exception indicates that this specific record cannot produce a metric value, which is different from an error. The metrics processor handles this gracefully by excluding the record from results.

## Metric Declaration

### Class Attributes

Record metrics declare their characteristics through class attributes:

```python
class TTFTMetric(BaseRecordMetric[int]):
    tag = "ttft"                              # Unique identifier
    header = "Time to First Token"            # Display name
    short_header = "TTFT"                     # Abbreviated name
    unit = MetricTimeUnit.NANOSECONDS         # Internal unit
    display_unit = MetricTimeUnit.MILLISECONDS # Display unit
    display_order = 100                       # Display ordering
    flags = MetricFlags.STREAMING_TOKENS_ONLY # Applicability flags
    required_metrics = None                   # Dependency list
```

### Attribute Descriptions

#### tag (Required)

A unique string identifier for the metric. Must be unique across all metrics.

```python
tag = "ttft"
tag = "request_latency"
tag = "input_sequence_length"
```

#### header (Required)

The full display name used in console output and reports:

```python
header = "Time to First Token"
header = "Request Latency"
header = "Input Sequence Length"
```

#### short_header (Optional)

An abbreviated name for dashboard display:

```python
short_header = "TTFT"
short_header = "Req Latency"
short_header = "Input Len"
```

#### unit (Required)

The unit of the internal metric representation:

```python
from aiperf.common.enums import MetricTimeUnit, GenericMetricUnit

unit = MetricTimeUnit.NANOSECONDS           # Time-based metrics
unit = GenericMetricUnit.TOKENS             # Token counts
unit = GenericMetricUnit.BYTES              # Data sizes
```

#### display_unit (Optional)

The unit for displaying values to users. If not set, uses the internal unit:

```python
unit = MetricTimeUnit.NANOSECONDS           # Store in nanoseconds
display_unit = MetricTimeUnit.MILLISECONDS  # Display in milliseconds
```

AIPerf automatically handles unit conversions when displaying values.

#### display_order (Optional)

Controls the ordering in console output. Lower numbers appear first:

```python
display_order = 100  # TTFT appears early
display_order = 300  # Request Latency appears later
display_order = None # Appears after all ordered metrics
```

#### flags (Required)

Controls when and how the metric is computed:

```python
from aiperf.common.enums import MetricFlags

# Basic flags
flags = MetricFlags.NONE                    # Always applicable
flags = MetricFlags.STREAMING_TOKENS_ONLY   # Only for streaming endpoints
flags = MetricFlags.LARGER_IS_BETTER        # Higher values are better

# Combined flags
flags = MetricFlags.STREAMING_TOKENS_ONLY | MetricFlags.LARGER_IS_BETTER
```

Common flag combinations:

| Flags | Meaning |
|-------|---------|
| `NONE` | Always applicable |
| `STREAMING_TOKENS_ONLY` | Only for streaming token-based responses |
| `LARGER_IS_BETTER` | Metric value should be maximized |
| `SMALLER_IS_BETTER` | Metric value should be minimized |
| `GOODPUT` | Used for goodput calculations |
| `ERROR_ONLY` | Only computed for error records |

#### required_metrics (Optional)

Set of metric tags that must be computed before this metric:

```python
# No dependencies
required_metrics = None

# Single dependency
required_metrics = {RequestLatencyMetric.tag}

# Multiple dependencies
required_metrics = {
    RequestLatencyMetric.tag,
    TTFTMetric.tag,
    OutputSequenceLengthMetric.tag,
}
```

AIPerf automatically computes metrics in dependency order using topological sorting.

## Implementation Patterns

### Pattern 1: Simple Extraction

Extract a value directly from the record:

```python
class InputSequenceLengthMetric(BaseRecordMetric[int]):
    """Extract the input token count from the record."""

    tag = "input_sequence_length"
    header = "Input Sequence Length"
    short_header = "Input Len"
    unit = GenericMetricUnit.TOKENS
    display_order = 600
    flags = MetricFlags.NONE
    required_metrics = None

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        return record.input_token_count
```

**Pattern Characteristics**:
- No dependencies (`required_metrics = None`)
- Direct field access
- Simple return statement
- No validation needed (record is pre-validated)

### Pattern 2: Timestamp Computation

Compute timing differences from timestamps:

```python
class TTFTMetric(BaseRecordMetric[int]):
    """Calculate Time to First Token from timestamps."""

    tag = "ttft"
    header = "Time to First Token"
    short_header = "TTFT"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    display_order = 100
    flags = MetricFlags.STREAMING_TOKENS_ONLY
    required_metrics = None

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        if len(record.responses) < 1:
            raise NoMetricValue(
                "Record must have at least one response to calculate TTFT."
            )

        request_ts: int = record.request.start_perf_ns
        first_response_ts: int = record.responses[0].perf_ns

        if first_response_ts < request_ts:
            raise ValueError(
                "First response timestamp is before request start timestamp, cannot compute TTFT."
            )

        return first_response_ts - request_ts
```

**Pattern Characteristics**:
- Validates response availability
- Extracts timestamps from specific positions
- Validates timestamp ordering
- Returns difference in nanoseconds

### Pattern 3: Dependent Computation

Compute from other record metrics:

```python
class InterTokenLatencyMetric(BaseRecordMetric[float]):
    """Calculate Inter Token Latency from other metrics."""

    tag = "inter_token_latency"
    header = "Inter Token Latency"
    short_header = "ITL"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    display_order = 400
    flags = MetricFlags.STREAMING_TOKENS_ONLY
    required_metrics = {
        RequestLatencyMetric.tag,
        TTFTMetric.tag,
        OutputSequenceLengthMetric.tag,
    }

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> float:
        # Access dependent metric values
        osl = record_metrics.get_or_raise(OutputSequenceLengthMetric)

        if osl < 2:
            raise NoMetricValue(
                f"Output sequence length must be at least 2, got {osl}"
            )

        ttft = record_metrics.get_or_raise(TTFTMetric)
        request_latency = record_metrics.get_or_raise(RequestLatencyMetric)

        # Formula: (Request Latency - TTFT) / (Output Length - 1)
        return (request_latency - ttft) / (osl - 1)
```

**Pattern Characteristics**:
- Declares dependencies via `required_metrics`
- Uses `record_metrics.get_or_raise()` for type-safe access
- Validates dependent values
- Computes derived value from dependencies

### Pattern 4: Complex Analysis

Analyze response streams for detailed metrics:

```python
class TokenLatenciesMetric(BaseRecordMetric[list[int]]):
    """Calculate per-token latencies from response stream."""

    tag = "token_latencies"
    header = "Token Latencies"
    short_header = "Token Lat"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    display_order = 500
    flags = MetricFlags.STREAMING_TOKENS_ONLY
    required_metrics = None

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> list[int]:
        if len(record.responses) < 2:
            raise NoMetricValue(
                "Need at least 2 responses for per-token latencies"
            )

        latencies = []
        for i in range(1, len(record.responses)):
            prev_ts = record.responses[i - 1].perf_ns
            curr_ts = record.responses[i].perf_ns
            latencies.append(curr_ts - prev_ts)

        return latencies
```

**Pattern Characteristics**:
- Returns a list of values per record
- Iterates through response stream
- Computes inter-arrival times
- Result type is `list[int]` → final result is `list[list[int]]`

## Built-in Record Metrics

### Timing Metrics

#### Time to First Token (TTFT)

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/types/ttft_metric.py`

Measures the time from request start to the first response byte.

**Formula**: `TTFT = First Response Timestamp - Request Start Timestamp`

**Applicability**: Streaming endpoints only

```python
class TTFTMetric(BaseRecordMetric[int]):
    tag = "ttft"
    header = "Time to First Token"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.STREAMING_TOKENS_ONLY
```

**Use Cases**:
- Measuring perceived responsiveness
- Detecting prefill performance issues
- Comparing model initialization times

#### Request Latency

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/types/request_latency_metric.py`

Measures the total time from request start to final response.

**Formula**: `Request Latency = Final Response Timestamp - Request Start Timestamp`

**Applicability**: All endpoints

```python
class RequestLatencyMetric(BaseRecordMetric[int]):
    tag = "request_latency"
    header = "Request Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.NONE
```

**Use Cases**:
- End-to-end latency measurement
- SLA compliance checking
- Performance baseline establishment

#### Inter-Token Latency (ITL)

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/types/inter_token_latency_metric.py`

Measures the average time between tokens during generation.

**Formula**: `ITL = (Request Latency - TTFT) / (Output Length - 1)`

**Dependencies**: RequestLatencyMetric, TTFTMetric, OutputSequenceLengthMetric

**Applicability**: Streaming endpoints only

```python
class InterTokenLatencyMetric(BaseRecordMetric[float]):
    tag = "inter_token_latency"
    header = "Inter Token Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.STREAMING_TOKENS_ONLY
    required_metrics = {
        RequestLatencyMetric.tag,
        TTFTMetric.tag,
        OutputSequenceLengthMetric.tag,
    }
```

**Use Cases**:
- Measuring decode performance
- Identifying generation bottlenecks
- Comparing token generation speeds

#### Time to Second Token (TTST)

Measures the time from request start to the second response token.

**Formula**: `TTST = Second Response Timestamp - Request Start Timestamp`

**Applicability**: Streaming endpoints only

**Use Cases**:
- Measuring initial generation latency
- Detecting first-token caching effects
- Comparing prefill + first decode time

#### Inter-Chunk Latency

Measures the average time between response chunks (not individual tokens).

**Formula**: Average time between consecutive SSE messages

**Applicability**: Streaming endpoints only

**Use Cases**:
- Measuring chunk-based streaming performance
- Network latency analysis
- Batch generation analysis

### Length Metrics

#### Input Sequence Length

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/types/input_sequence_length_metric.py`

Counts the number of input tokens in the request.

```python
class InputSequenceLengthMetric(BaseRecordMetric[int]):
    tag = "input_sequence_length"
    header = "Input Sequence Length"
    unit = GenericMetricUnit.TOKENS
    flags = MetricFlags.NONE

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        return record.input_token_count
```

**Use Cases**:
- Analyzing prompt length distributions
- Correlating input size with performance
- Planning capacity based on workload

#### Output Sequence Length

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/types/output_sequence_length_metric.py`

Counts the number of output tokens in the response.

```python
class OutputSequenceLengthMetric(BaseRecordMetric[int]):
    tag = "output_sequence_length"
    header = "Output Sequence Length"
    unit = GenericMetricUnit.TOKENS
    flags = MetricFlags.NONE

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        return record.output_token_count
```

**Use Cases**:
- Measuring generation length
- Analyzing token budgets
- Detecting truncation patterns

### Boundary Metrics

#### Minimum Request Time

Records the earliest timestamp in the benchmark run.

**Use Cases**:
- Calculating benchmark duration
- Timestamp normalization
- Performance window analysis

#### Maximum Response Time

Records the latest timestamp in the benchmark run.

**Use Cases**:
- Calculating benchmark duration
- Determining completion time
- Grace period analysis

## MetricRecordDict: The Dependency Container

Record metrics access their dependencies through `MetricRecordDict`, a type-safe container for computed metric values.

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/metric_dicts.py`

### Type-Safe Access

```python
# Type-safe access with automatic type inference
value = record_metrics.get_or_raise(TTFTMetric)
# Returns: int (inferred from TTFTMetric[int])

value = record_metrics.get_or_raise(InterTokenLatencyMetric)
# Returns: float (inferred from InterTokenLatencyMetric[float])
```

### Access Methods

```python
# Get value or raise NoMetricValue if not found
value = record_metrics.get_or_raise(SomeMetric)

# Get value or return None if not found
value = record_metrics.get(SomeMetric.tag)

# Check existence
if SomeMetric.tag in record_metrics:
    # Metric is available
    pass

# Direct dictionary access (not recommended - loses type safety)
value = record_metrics[SomeMetric.tag]
```

### Usage in Dependent Metrics

```python
def _parse_record(
    self,
    record: ParsedResponseRecord,
    record_metrics: MetricRecordDict,
) -> float:
    # Type-safe access to dependencies
    request_latency = record_metrics.get_or_raise(RequestLatencyMetric)
    ttft = record_metrics.get_or_raise(TTFTMetric)
    osl = record_metrics.get_or_raise(OutputSequenceLengthMetric)

    # Compute derived value
    return (request_latency - ttft) / (osl - 1)
```

## ParsedResponseRecord: The Data Source

Record metrics extract information from `ParsedResponseRecord` objects.

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/common/models.py`

### Key Fields

```python
@dataclass
class ParsedResponseRecord:
    # Timing information
    start_perf_ns: int                    # Request start time
    end_perf_ns: int                      # Request end time
    recv_start_perf_ns: int              # First byte received time

    # Request data
    request: RequestRecord                # Original request details

    # Response data
    responses: list[ParsedResponse]       # Parsed responses

    # Token counts
    input_token_count: int                # Number of input tokens
    output_token_count: int               # Number of output tokens

    # Status
    valid: bool                           # Whether record is valid
    error: ErrorDetails | None            # Error information if any
```

### Accessing Response Data

```python
def _parse_record(
    self,
    record: ParsedResponseRecord,
    record_metrics: MetricRecordDict,
) -> int:
    # Check response availability
    if len(record.responses) < 1:
        raise NoMetricValue("No responses available")

    # Access first response
    first_response = record.responses[0]
    first_ts = first_response.perf_ns

    # Access last response
    last_response = record.responses[-1]
    last_ts = last_response.perf_ns

    # Iterate through all responses
    for response in record.responses:
        # Process each response
        pass

    return last_ts - first_ts
```

### Accessing Request Data

```python
def _parse_record(
    self,
    record: ParsedResponseRecord,
    record_metrics: MetricRecordDict,
) -> int:
    # Request timing
    request_start = record.request.start_perf_ns

    # HTTP status
    status_code = record.status

    # Error information
    if record.error:
        error_code = record.error.code
        error_message = record.error.message

    return some_computed_value
```

## Statistical Analysis

Record metrics produce lists of values that enable rich statistical analysis.

### Automatic Statistics

AIPerf automatically computes standard statistics for all record metrics:

- **Mean**: Average value
- **Median**: 50th percentile
- **Min**: Minimum value
- **Max**: Maximum value
- **Std Dev**: Standard deviation
- **Percentiles**: P25, P50, P75, P90, P95, P99

### Access in Console Output

```
Time to First Token (ms):
  Mean: 125.3
  Median: 120.5
  Min: 95.2
  Max: 450.8
  Std Dev: 35.7
  P25: 110.2
  P75: 135.8
  P90: 160.5
  P95: 180.3
  P99: 250.7
```

### Programmatic Access

```python
from aiperf.metrics.metric_registry import MetricRegistry
from aiperf.post_processors import MetricResultsProcessor

# Get metric results
results = processor.get_results()

# Access raw values (list of per-record values)
ttft_values = results[TTFTMetric.tag]

# Compute custom statistics
import numpy as np
p99_9 = np.percentile(ttft_values, 99.9)
geometric_mean = np.exp(np.mean(np.log(ttft_values)))
```

## Dependency Management

### Topological Sorting

AIPerf automatically orders metric computation using topological sorting to respect dependencies.

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/metric_registry.py`

```python
def create_dependency_order_for(
    cls,
    tags: Iterable[MetricTagT] | None = None,
) -> list[MetricTagT]:
    """
    Create a dependency order for the given metrics using topological sort.

    This ensures that all dependencies are computed before their dependents.
    """
    if tags is None:
        tags = cls._metrics_map.keys()

    # Build the dependency graph
    sorter = graphlib.TopologicalSorter()

    for metric in cls.classes_for(tags):
        sorter.add(metric.tag, *(metric.required_metrics or set()))

    try:
        order = list(sorter.static_order())
        tags_set = set(tags)
        return [tag for tag in order if tag in tags_set]
    except graphlib.CycleError as e:
        raise MetricTypeError(
            f"Circular dependency detected among metrics: {e}"
        ) from e
```

### Dependency Example

Given these metrics:

```python
# No dependencies
class RequestLatencyMetric(BaseRecordMetric[int]):
    required_metrics = None

class TTFTMetric(BaseRecordMetric[int]):
    required_metrics = None

class OutputSequenceLengthMetric(BaseRecordMetric[int]):
    required_metrics = None

# Depends on three metrics
class InterTokenLatencyMetric(BaseRecordMetric[float]):
    required_metrics = {
        RequestLatencyMetric.tag,
        TTFTMetric.tag,
        OutputSequenceLengthMetric.tag,
    }
```

AIPerf computes in this order:

1. `RequestLatencyMetric` (no dependencies)
2. `TTFTMetric` (no dependencies)
3. `OutputSequenceLengthMetric` (no dependencies)
4. `InterTokenLatencyMetric` (all dependencies satisfied)

### Circular Dependency Detection

AIPerf detects and rejects circular dependencies at startup:

```python
# This would cause an error:
class MetricA(BaseRecordMetric[int]):
    required_metrics = {MetricB.tag}

class MetricB(BaseRecordMetric[int]):
    required_metrics = {MetricA.tag}

# Error: Circular dependency detected among metrics
```

## Processing Pipeline

### Record Processing Flow

```
┌──────────────────┐
│ RequestRecord    │
└────────┬─────────┘
         │
         v
┌──────────────────┐
│ Response Parser  │ Extract and parse responses
└────────┬─────────┘
         │
         v
┌──────────────────┐
│ParsedResponseRec │ Contains request + parsed responses
└────────┬─────────┘
         │
         v
┌──────────────────┐
│ Metric Processor │ Process in dependency order
└────────┬─────────┘
         │
         v
┌──────────────────┐
│ For each metric: │
│ 1. Validate rec  │ Ensure record is valid
│ 2. Check deps    │ Verify dependencies available
│ 3. Compute value │ Call _parse_record()
│ 4. Store result  │ Add to MetricRecordDict
└────────┬─────────┘
         │
         v
┌──────────────────┐
│ Metric Results   │ List of values for each metric
└──────────────────┘
```

### Distributed Processing

Record metrics are computed in parallel across worker processes:

```python
# Each worker processes a subset of records
class MetricRecordProcessor:
    def process_record(
        self,
        record: ParsedResponseRecord,
    ) -> MetricRecordDict:
        """Process a single record through all metrics."""
        record_metrics = MetricRecordDict()

        # Compute metrics in dependency order
        for metric_tag in self.dependency_order:
            metric = MetricRegistry.get_instance(metric_tag)
            try:
                value = metric.parse_record(record, record_metrics)
                record_metrics[metric_tag] = value
            except NoMetricValue:
                # Skip this metric for this record
                pass

        return record_metrics
```

Workers return per-record results, which are aggregated by the main process.

## Error Handling

### NoMetricValue Exception

Use `NoMetricValue` when a metric cannot be computed for a specific record:

```python
from aiperf.common.exceptions import NoMetricValue

def _parse_record(
    self,
    record: ParsedResponseRecord,
    record_metrics: MetricRecordDict,
) -> int:
    if len(record.responses) < 1:
        raise NoMetricValue("No responses available")

    # Continue computation
    return computed_value
```

**When to Use**:
- Record doesn't have required data (e.g., no responses)
- Metric is not applicable to this record (e.g., TTFT for non-streaming)
- Computation would produce invalid result (e.g., division by zero)

**Effect**:
- Record is excluded from this metric's results
- Other metrics can still be computed for the record
- No error is logged (this is expected behavior)

### ValueError Exception

Use `ValueError` for actual errors in data:

```python
def _parse_record(
    self,
    record: ParsedResponseRecord,
    record_metrics: MetricRecordDict,
) -> int:
    request_ts = record.request.start_perf_ns
    response_ts = record.responses[0].perf_ns

    if response_ts < request_ts:
        raise ValueError(
            "Response timestamp is before request timestamp"
        )

    return response_ts - request_ts
```

**When to Use**:
- Data is malformed or invalid
- Timestamps are out of order
- Values are outside expected ranges
- Logic errors in computation

**Effect**:
- Processing stops for this record
- Error is logged
- Record is marked as invalid

## Custom Record Metrics

### Creating a Custom Metric

**Example**: `/home/anthony/nvidia/projects/aiperf/examples/custom-metrics/custom_record_metric.py`

```python
from aiperf.common.enums import MetricFlags, MetricTimeUnit
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics import BaseRecordMetric
from aiperf.metrics.metric_dicts import MetricRecordDict

class CustomLatencyMetric(BaseRecordMetric[float]):
    """Custom metric that computes a specialized latency."""

    # Required: Unique identifier
    tag = "custom_latency"

    # Required: Display information
    header = "Custom Latency"
    short_header = "Custom Lat"

    # Required: Units
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS

    # Required: Display ordering
    display_order = 150

    # Required: Applicability flags
    flags = MetricFlags.NONE

    # Optional: Dependencies
    required_metrics = {
        "request_latency",
        "ttft",
    }

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> float:
        """Compute the custom latency value."""
        # Access dependencies
        request_latency = record_metrics.get_or_raise("request_latency")
        ttft = record_metrics.get_or_raise("ttft")

        # Custom computation
        custom_value = (request_latency + ttft) / 2.0

        return custom_value
```

### Registration

Custom metrics are automatically registered when the class is defined:

```python
# Metric is registered when class is created
class CustomLatencyMetric(BaseRecordMetric[float]):
    tag = "custom_latency"
    # ... rest of implementation
```

The `BaseMetric.__init_subclass__` method handles registration:

```python
def __init_subclass__(cls, **kwargs):
    super().__init_subclass__(**kwargs)

    # Only register concrete classes
    if inspect.isabstract(cls):
        return

    # Verify and register
    cls._verify_base_class()
    MetricRegistry.register_metric(cls)
```

### Using Custom Metrics

Custom metrics work exactly like built-in metrics:

```python
from aiperf.metrics.metric_registry import MetricRegistry

# Get the metric class
CustomLatencyMetric = MetricRegistry.get_class("custom_latency")

# Get or create an instance
metric = MetricRegistry.get_instance("custom_latency")

# Use in dependency declarations
class AnotherMetric(BaseRecordMetric[float]):
    required_metrics = {CustomLatencyMetric.tag}
```

## Performance Considerations

### Computational Efficiency

Record metrics are called once per record per worker, making them a hot path:

**Best Practices**:

1. **Minimize Allocations**: Avoid creating unnecessary objects

```python
# Good: Direct calculation
def _parse_record(self, record, record_metrics) -> int:
    return record.responses[-1].perf_ns - record.request.start_perf_ns

# Less efficient: Intermediate variables
def _parse_record(self, record, record_metrics) -> int:
    times = [r.perf_ns for r in record.responses]
    end_time = max(times)
    start_time = record.request.start_perf_ns
    return end_time - start_time
```

2. **Early Returns**: Validate and return quickly

```python
def _parse_record(self, record, record_metrics) -> int:
    # Validate early
    if len(record.responses) < 1:
        raise NoMetricValue("No responses")

    # Fast path computation
    return record.responses[0].perf_ns - record.request.start_perf_ns
```

3. **Avoid Expensive Operations**: No I/O, no heavy computation

```python
# Bad: File I/O in hot path
def _parse_record(self, record, record_metrics) -> int:
    with open("log.txt", "a") as f:  # DON'T DO THIS
        f.write(f"Processing {record.id}\n")
    return compute_value()

# Good: Return value directly
def _parse_record(self, record, record_metrics) -> int:
    return compute_value()
```

### Memory Efficiency

Record metrics produce lists of values, which can be large:

```python
# 100,000 records × 8 bytes = 800 KB per metric
class TTFTMetric(BaseRecordMetric[int]):  # 8 bytes per int
    pass

# 100,000 records × 1,000 values × 8 bytes = 800 MB
class PerTokenLatenciesMetric(BaseRecordMetric[list[int]]):  # Large per record
    pass
```

**Considerations**:
- Record metrics are computed in workers and aggregated in main process
- Large per-record values (like `list[int]`) should be used sparingly
- Consider aggregate metrics for large-scale computations

## Testing Record Metrics

### Unit Testing Pattern

```python
import pytest
from aiperf.common.models import ParsedResponseRecord, ParsedResponse
from aiperf.metrics.metric_dicts import MetricRecordDict

def test_ttft_metric_basic():
    """Test TTFT calculation with valid data."""
    # Create test record
    record = ParsedResponseRecord(
        start_perf_ns=1000000,
        request=RequestRecord(start_perf_ns=1000000),
        responses=[
            ParsedResponse(perf_ns=1100000),
            ParsedResponse(perf_ns=1200000),
        ],
        valid=True,
    )

    # Compute metric
    metric = TTFTMetric()
    result = metric.parse_record(record, MetricRecordDict())

    # Verify result
    assert result == 100000  # 1100000 - 1000000

def test_ttft_metric_no_responses():
    """Test TTFT with no responses."""
    record = ParsedResponseRecord(
        start_perf_ns=1000000,
        request=RequestRecord(start_perf_ns=1000000),
        responses=[],
        valid=True,
    )

    metric = TTFTMetric()

    # Should raise NoMetricValue
    with pytest.raises(NoMetricValue):
        metric.parse_record(record, MetricRecordDict())

def test_inter_token_latency_with_dependencies():
    """Test metric with dependencies."""
    # Create test record
    record = create_test_record()

    # Create dependency metrics
    record_metrics = MetricRecordDict()
    record_metrics["request_latency"] = 500000
    record_metrics["ttft"] = 100000
    record_metrics["output_sequence_length"] = 10

    # Compute dependent metric
    metric = InterTokenLatencyMetric()
    result = metric.parse_record(record, record_metrics)

    # Verify: (500000 - 100000) / (10 - 1) = 44444.44
    assert abs(result - 44444.44) < 0.01
```

### Integration Testing

```python
def test_metric_in_pipeline():
    """Test metric in full processing pipeline."""
    from aiperf.post_processors import MetricRecordProcessor

    # Create processor with metric
    processor = MetricRecordProcessor(metrics=["ttft", "request_latency"])

    # Process test record
    record = create_test_record()
    results = processor.process_record(record)

    # Verify both metrics computed
    assert "ttft" in results
    assert "request_latency" in results

    # Verify values
    assert results["ttft"] > 0
    assert results["request_latency"] > results["ttft"]
```

## Debugging Record Metrics

### Logging

Use the logger mixin for debugging:

```python
class CustomMetric(BaseRecordMetric[int]):
    def _parse_record(self, record, record_metrics) -> int:
        # Debug logging
        self.debug(f"Processing record with {len(record.responses)} responses")

        value = compute_value(record)

        # Info logging
        self.info(f"Computed value: {value}")

        return value
```

### Validation

Add validation helpers:

```python
def _parse_record(self, record, record_metrics) -> int:
    # Validate inputs
    assert record.valid, "Record must be valid"
    assert len(record.responses) > 0, "Must have responses"
    assert record.request.start_perf_ns > 0, "Must have start time"

    # Compute
    value = compute_value(record)

    # Validate output
    assert value > 0, f"Value must be positive, got {value}"

    return value
```

### Inspection

Access metric information programmatically:

```python
from aiperf.metrics.metric_registry import MetricRegistry

# Get metric class
metric_class = MetricRegistry.get_class("ttft")

# Inspect attributes
print(f"Tag: {metric_class.tag}")
print(f"Header: {metric_class.header}")
print(f"Unit: {metric_class.unit}")
print(f"Flags: {metric_class.flags}")
print(f"Dependencies: {metric_class.required_metrics}")
print(f"Value Type: {metric_class.value_type}")

# Check applicability
if metric_class.has_flags(MetricFlags.STREAMING_TOKENS_ONLY):
    print("Only for streaming endpoints")
```

## Key Takeaways

1. **Record Metrics are Per-Request**: Each record is processed independently, producing one value per record

2. **Type Safety Matters**: Use generic type parameters (`BaseRecordMetric[int]`) for type-safe implementations

3. **Dependencies are Automatic**: Declare dependencies via `required_metrics`, AIPerf handles ordering

4. **Validation Pipeline**: Records and dependencies are validated before `_parse_record` is called

5. **NoMetricValue vs ValueError**: Use `NoMetricValue` for inapplicable metrics, `ValueError` for data errors

6. **Statistical Analysis**: Record metrics automatically produce percentiles and distributions

7. **Performance Critical**: Record metrics are hot paths, optimize for efficiency

8. **Custom Metrics are Easy**: Extend `BaseRecordMetric`, implement `_parse_record`, automatic registration

9. **MetricRecordDict is Type-Safe**: Use `get_or_raise` for type-safe dependency access

10. **Testing is Straightforward**: Create test records, compute metrics, verify results

## What's Next

Record metrics form the foundation for more advanced metrics:

- **Chapter 22: Aggregate and Derived Metrics** - Learn how to build metrics that aggregate across records and derive new values from existing metrics
- **Chapter 23: HTTP Client Architecture** - Understand how records are captured with precise timing

---

**Remember**: Record metrics are the building blocks of AIPerf's metrics system. Master these patterns, and you'll be able to extract any insight from your benchmark data.
