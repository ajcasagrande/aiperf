<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 22: Aggregate and Derived Metrics

## Navigation
- Previous: [Chapter 21: Record Metrics](chapter-21-record-metrics.md)
- Next: [Chapter 23: HTTP Client Architecture](chapter-23-http-client-architecture.md)
- [Table of Contents](README.md)

## Overview

While record metrics compute values for individual requests, aggregate and derived metrics operate at the benchmark level. Aggregate metrics accumulate values across all records (like counting total requests), while derived metrics compute new values from existing metrics (like calculating throughput from counts and duration). Together, they provide high-level insights into benchmark performance.

This chapter explores both metric types in detail, showing how they complement record metrics to provide comprehensive benchmark analysis.

## The Three-Tier Metrics Architecture

AIPerf's metrics system consists of three tiers that work together:

```
┌─────────────────────────────────────────────────────────────┐
│ Tier 1: RECORD METRICS                                      │
│ - Computed per-request                                       │
│ - Independent of other requests                              │
│ - Produce lists of values                                    │
│ Examples: TTFT, Request Latency, Token Counts                │
└────────────────┬────────────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────────────┐
│ Tier 2: AGGREGATE METRICS                                   │
│ - Accumulate across requests                                 │
│ - Track running totals, mins, maxes                          │
│ - Produce single values                                      │
│ Examples: Request Count, Benchmark Duration, Min/Max Times   │
└────────────────┬────────────────────────────────────────────┘
                 │
                 v
┌─────────────────────────────────────────────────────────────┐
│ Tier 3: DERIVED METRICS                                     │
│ - Computed from other metrics                                │
│ - No access to raw records                                   │
│ - Produce computed values                                    │
│ Examples: Request Throughput, Goodput                        │
└─────────────────────────────────────────────────────────────┘
```

## Aggregate Metrics

Aggregate metrics accumulate values across multiple records, maintaining running totals, counts, or extrema. They are designed for distributed processing, where workers process subsets of records and the main process aggregates their results.

### BaseAggregateMetric Class

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/base_aggregate_metric.py`

```python
class BaseAggregateMetric(
    Generic[MetricValueTypeVarT], BaseMetric[MetricValueTypeVarT], ABC
):
    """A base class for aggregate metrics. These metrics keep track of a value or list of values over time.

    This metric type is unique in the fact that it is split into 2 distinct phases of processing, in order to support distributed processing.

    For each distributed RecordProcessor, an instance of this class is created. This instance is passed the record and the existing record metrics,
    and is responsible for returning the individual value for that record. It should not use or update the aggregate value here.

    The ResultsProcessor creates a singleton instance of this class, which will be used to aggregate the results from the distributed
    RecordProcessors. It calls the `_aggregate_value` method, which each metric class must implement to define how values from different
    processes are aggregated, such as summing the values, or taking the min/max/average, etc.
    """

    type = MetricType.AGGREGATE

    def __init__(self, default_value: MetricValueTypeVarT | None = None) -> None:
        """Initialize the metric with optionally with a default value."""
        self._value: MetricValueTypeVarT = (
            default_value
            if default_value is not None
            else self.value_type.default_factory()
        )
        self.aggregate_value: Callable[[MetricValueTypeVarT], None] = (
            self._aggregate_value
        )
        super().__init__()

    @property
    def current_value(self) -> MetricValueTypeVarT:
        """Get the current value of the metric."""
        return self._value

    def parse_record(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> MetricValueTypeVarT:
        """Parse the record and return the individual value."""
        self._require_valid_record(record)
        self._check_metrics(record_metrics)
        return self._parse_record(record, record_metrics)

    @abstractmethod
    def _parse_record(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> MetricValueTypeVarT:
        """Parse the record and *return* the individual value base on this record, and this record alone.
        NOTE: Do not use or update the aggregate value here."""
        raise NotImplementedError("Subclasses must implement this method")

    @abstractmethod
    def _aggregate_value(self, value: MetricValueTypeVarT) -> None:
        """Aggregate the metric value. This method is implemented by subclasses.

        This method is called with the result value from the `_parse_record` method, from each distributed record processor.
        It is the responsibility of each metric class to implement how values from different processes are aggregated, such
        as summing the values, or taking the min/max/average, etc.

        NOTE: The order of the values is not guaranteed.
        """
        raise NotImplementedError("Subclasses must implement this method")
```

### Two-Phase Processing

Aggregate metrics operate in two distinct phases to support distributed processing:

#### Phase 1: Record Processing (Workers)

Each worker processes a subset of records:

```python
# Worker Process
class RequestCountMetric(BaseAggregateMetric[int]):
    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        # Return individual contribution for this record
        # DO NOT update self._value here
        return 1  # Each record contributes 1 to the count

# Worker processes records independently
worker1_results = [1, 1, 1]  # 3 records
worker2_results = [1, 1]     # 2 records
worker3_results = [1, 1, 1, 1]  # 4 records
```

**Key Principle**: `_parse_record` returns the contribution from a single record without updating the aggregate value.

#### Phase 2: Aggregation (Main Process)

The main process aggregates results from all workers:

```python
# Main Process
class RequestCountMetric(BaseAggregateMetric[int]):
    def __init__(self):
        super().__init__(default_value=0)

    def _aggregate_value(self, value: int) -> None:
        # Sum contributions from each record
        self._value += value

# Main process aggregates all results
metric = RequestCountMetric()
for value in worker1_results:
    metric.aggregate_value(value)  # _value = 3
for value in worker2_results:
    metric.aggregate_value(value)  # _value = 5
for value in worker3_results:
    metric.aggregate_value(value)  # _value = 9

final_count = metric.current_value  # 9
```

**Key Principle**: `_aggregate_value` updates `self._value` based on each contributed value.

### Design Rationale

This two-phase design enables:

1. **Parallel Processing**: Workers process records independently without coordination
2. **Scalability**: Each worker handles a subset of records
3. **Flexibility**: Different aggregation strategies (sum, min, max, etc.)
4. **Correctness**: No race conditions or shared state during processing

## Built-in Aggregate Metrics

### Counter Metrics

#### Request Count Metric

Counts the total number of valid requests processed.

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/types/request_count_metric.py`

```python
class RequestCountMetric(BaseAggregateCounterMetric[int]):
    """
    This is the total number of valid requests processed by the benchmark.
    It is incremented for each valid request.

    Formula:
        Request Count = Sum(Valid Requests)
    """

    tag = "request_count"
    header = "Request Count"
    short_header = "Requests"
    short_header_hide_unit = True
    unit = GenericMetricUnit.REQUESTS
    display_order = 1000
    flags = MetricFlags.LARGER_IS_BETTER
    required_metrics = None
```

**Usage**:
- Tracking total benchmark load
- Computing rates and throughputs
- Validating expected request counts

#### BaseAggregateCounterMetric

A convenience base class for simple counter metrics:

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/base_aggregate_counter_metric.py`

```python
class BaseAggregateCounterMetric(
    Generic[MetricValueTypeVarT], BaseAggregateMetric[MetricValueTypeVarT], ABC
):
    """
    A base class for aggregate counter metrics. These metrics increment a counter for each record.
    """

    def _parse_record(
        self, record: ParsedResponseRecord, record_metrics: MetricRecordDict
    ) -> MetricValueTypeVarT:
        """Return the value of the counter for this record."""
        return 1  # type: ignore

    def _aggregate_value(self, value: MetricValueTypeVarT) -> None:
        """Aggregate the metric value."""
        self._value += value  # type: ignore
```

**Using BaseAggregateCounterMetric**:

```python
# Simple counter - just declare attributes
class GoodRequestCountMetric(BaseAggregateCounterMetric[int]):
    tag = "good_request_count"
    header = "Good Request Count"
    unit = GenericMetricUnit.REQUESTS
    flags = MetricFlags.GOODPUT
```

All the counting logic is inherited automatically.

### Boundary Metrics

#### Minimum Request Time

Tracks the earliest request start time.

```python
class MinRequestMetric(BaseAggregateMetric[int]):
    """Track the minimum (earliest) request timestamp."""

    tag = "min_request"
    header = "Min Request Time"
    unit = MetricTimeUnit.NANOSECONDS
    flags = MetricFlags.NONE

    def __init__(self):
        # Start with maximum possible value
        super().__init__(default_value=float('inf'))

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        # Return this record's start time
        return record.request.start_perf_ns

    def _aggregate_value(self, value: int) -> None:
        # Keep the minimum (earliest) time
        self._value = min(self._value, value)
```

**Usage**:
- Computing benchmark duration
- Normalizing timestamps
- Analyzing benchmark start time

#### Maximum Response Time

Tracks the latest response completion time.

```python
class MaxResponseMetric(BaseAggregateMetric[int]):
    """Track the maximum (latest) response timestamp."""

    tag = "max_response"
    header = "Max Response Time"
    unit = MetricTimeUnit.NANOSECONDS
    flags = MetricFlags.NONE

    def __init__(self):
        # Start with minimum possible value
        super().__init__(default_value=0)

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        # Return this record's end time
        return record.end_perf_ns

    def _aggregate_value(self, value: int) -> None:
        # Keep the maximum (latest) time
        self._value = max(self._value, value)
```

**Usage**:
- Computing benchmark duration
- Determining completion time
- Grace period analysis

### Duration Metrics

#### Benchmark Duration Metric

Computes the total benchmark duration from min/max timestamps.

```python
class BenchmarkDurationMetric(BaseAggregateMetric[int]):
    """Calculate the total benchmark duration."""

    tag = "benchmark_duration"
    header = "Benchmark Duration"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.SECONDS
    flags = MetricFlags.NONE
    required_metrics = {
        MinRequestMetric.tag,
        MaxResponseMetric.tag,
    }

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        # Aggregate metrics don't need per-record values
        # Return 0 as placeholder
        return 0

    def _aggregate_value(self, value: int) -> None:
        # Duration is computed from min/max, not summed
        # This method is called but doesn't update _value
        pass

    def compute_final_value(
        self,
        min_request: int,
        max_response: int,
    ) -> int:
        """Compute duration from min and max timestamps."""
        return max_response - min_request
```

**Note**: This metric uses dependencies on other aggregate metrics, which is allowed for aggregate metrics.

## Derived Metrics

Derived metrics compute values from existing metrics without accessing raw records. They represent the final tier in the metrics hierarchy.

### BaseDerivedMetric Class

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/base_derived_metric.py`

```python
class BaseDerivedMetric(
    Generic[MetricValueTypeVarT], BaseMetric[MetricValueTypeVarT], ABC
):
    """A base class for derived metrics. These metrics are computed from other metrics,
    and do not require any knowledge of the individual records. The final results will be a single computed value (or list of values).

    NOTE: The generic type can be a list of values, or a single value.
    """

    type = MetricType.DERIVED

    def derive_value(self, metric_results: MetricResultsDict) -> MetricValueTypeVarT:
        """Derive the metric value."""
        self._check_metrics(metric_results)
        return self._derive_value(metric_results)

    @abstractmethod
    def _derive_value(self, metric_results: MetricResultsDict) -> MetricValueTypeVarT:
        """Derive the metric value. This method is implemented by subclasses.
        This method is called after the required metrics are checked, so it can assume that the required metrics are available.

        Raises:
            ValueError: If the metric cannot be computed for the given inputs.
        """
        raise NotImplementedError("Subclasses must implement this method")
```

### Key Characteristics

1. **No Record Access**: Derived metrics only see aggregated results
2. **Single Computation**: Computed once after all records are processed
3. **Dependency-Based**: Always depend on other metrics
4. **Type Flexibility**: Can return any type, not just lists

### Built-in Derived Metrics

#### Request Throughput Metric

Computes requests per second from count and duration.

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/types/request_throughput_metric.py`

```python
class RequestThroughputMetric(BaseDerivedMetric[float]):
    """
    Post Processor for calculating Request throughput metrics from records.

    Formula:
        Request Throughput = Valid Request Count / Benchmark Duration (seconds)
    """

    tag = "request_throughput"
    header = "Request Throughput"
    short_header = "Req/sec"
    short_header_hide_unit = True
    unit = MetricOverTimeUnit.REQUESTS_PER_SECOND
    display_order = 900
    flags = MetricFlags.LARGER_IS_BETTER
    required_metrics = {
        RequestCountMetric.tag,
        BenchmarkDurationMetric.tag,
    }

    def _derive_value(
        self,
        metric_results: MetricResultsDict,
    ) -> float:
        request_count = metric_results.get_or_raise(RequestCountMetric)
        benchmark_duration_converted = metric_results.get_converted_or_raise(
            BenchmarkDurationMetric,
            self.unit.time_unit,  # Convert to seconds
        )
        return request_count / benchmark_duration_converted
```

**Key Features**:
- Automatic unit conversion for duration
- Type-safe metric access
- Simple division computation

**Usage**:
- Measuring overall throughput
- Comparing across benchmarks
- Capacity planning

#### Goodput Metric

Computes throughput of "good" requests that meet SLOs.

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/types/goodput_metric.py`

```python
class GoodputMetric(BaseDerivedMetric[float]):
    """
    Postprocessor for calculating the Goodput metric.

    Formula:
    Goodput = Good request count / Benchmark Duration (seconds)
    """

    tag = "goodput"
    header = "Goodput"
    short_header = "Goodput"
    short_header_hide_unit = True
    unit = MetricOverTimeUnit.REQUESTS_PER_SECOND
    display_order = 1000
    flags = MetricFlags.GOODPUT
    required_metrics = {GoodRequestCountMetric.tag, BenchmarkDurationMetric.tag}

    def _derive_value(self, metric_results: MetricResultsDict) -> float:
        tag = GoodRequestCountMetric.tag
        if tag not in metric_results:
            raise NoMetricValue(f"Metric '{tag}' is not available for the run.")
        good_request_count = metric_results[tag]

        benchmark_duration_converted = metric_results.get_converted_or_raise(
            BenchmarkDurationMetric,
            self.unit.time_unit,
        )
        return good_request_count / benchmark_duration_converted
```

**Usage**:
- Measuring SLO compliance
- Quality-adjusted throughput
- Production performance estimation

**Reference**: [DistServe Paper](https://arxiv.org/pdf/2401.09670)

#### Output Token Throughput Metric

Computes tokens generated per second.

```python
class OutputTokenThroughputMetric(BaseDerivedMetric[float]):
    """
    Calculate output token throughput.

    Formula:
        Output Token Throughput = Sum(Output Tokens) / Benchmark Duration (seconds)
    """

    tag = "output_token_throughput"
    header = "Output Token Throughput"
    short_header = "Out Tok/s"
    unit = MetricOverTimeUnit.TOKENS_PER_SECOND
    flags = MetricFlags.LARGER_IS_BETTER
    required_metrics = {
        OutputSequenceLengthMetric.tag,
        BenchmarkDurationMetric.tag,
    }

    def _derive_value(self, metric_results: MetricResultsDict) -> float:
        # Output sequence length is a record metric (list of values)
        output_lengths = metric_results.get_or_raise(OutputSequenceLengthMetric)
        total_tokens = sum(output_lengths)

        duration_seconds = metric_results.get_converted_or_raise(
            BenchmarkDurationMetric,
            MetricTimeUnit.SECONDS,
        )

        return total_tokens / duration_seconds
```

**Note**: This metric depends on a record metric (`OutputSequenceLengthMetric`), which is a list. It aggregates the list by summing.

## MetricResultsDict: The Results Container

Derived metrics access computed metric values through `MetricResultsDict`.

**File**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/metric_dicts.py`

### Type-Safe Access

```python
# Get value with type inference
count = metric_results.get_or_raise(RequestCountMetric)
# Returns: int (inferred from RequestCountMetric[int])

throughput = metric_results.get_or_raise(RequestThroughputMetric)
# Returns: float (inferred from RequestThroughputMetric[float])
```

### Unit Conversion

```python
# Get value with automatic unit conversion
duration_seconds = metric_results.get_converted_or_raise(
    BenchmarkDurationMetric,      # Source metric
    MetricTimeUnit.SECONDS,        # Target unit
)

# Original unit: nanoseconds
# Returned unit: seconds
# Conversion happens automatically
```

### Access Methods

```python
# Type-safe access with metric class
value = metric_results.get_or_raise(SomeMetric)

# String-based access (less type-safe)
value = metric_results["metric_tag"]

# Safe access with default
value = metric_results.get("metric_tag", default_value)

# Check existence
if "metric_tag" in metric_results:
    value = metric_results["metric_tag"]
```

### Record vs Aggregate Results

```python
# Record metrics return lists
ttft_values = metric_results.get_or_raise(TTFTMetric)
# Type: list[int]
# Example: [100000, 120000, 95000, ...]

# Aggregate metrics return single values
request_count = metric_results.get_or_raise(RequestCountMetric)
# Type: int
# Example: 1000

# Derived metrics return computed values
throughput = metric_results.get_or_raise(RequestThroughputMetric)
# Type: float
# Example: 125.5
```

## Dependency Management

### Cross-Tier Dependencies

Metrics can depend on metrics from any lower tier:

```python
# Record metrics can depend on other record metrics
class InterTokenLatencyMetric(BaseRecordMetric[float]):
    required_metrics = {
        RequestLatencyMetric.tag,  # Record metric
        TTFTMetric.tag,            # Record metric
    }

# Aggregate metrics can depend on record or aggregate metrics
class BenchmarkDurationMetric(BaseAggregateMetric[int]):
    required_metrics = {
        MinRequestMetric.tag,      # Aggregate metric
        MaxResponseMetric.tag,     # Aggregate metric
    }

# Derived metrics can depend on any metric type
class RequestThroughputMetric(BaseDerivedMetric[float]):
    required_metrics = {
        RequestCountMetric.tag,    # Aggregate metric
        BenchmarkDurationMetric.tag, # Aggregate metric
    }

class OutputTokenThroughputMetric(BaseDerivedMetric[float]):
    required_metrics = {
        OutputSequenceLengthMetric.tag,  # Record metric
        BenchmarkDurationMetric.tag,     # Aggregate metric
    }
```

### Allowed Dependencies

| Metric Type | Can Depend On |
|-------------|---------------|
| Record      | Record metrics only |
| Aggregate   | Record or Aggregate metrics |
| Derived     | Any metric type |

This hierarchy ensures:
- No circular dependencies possible
- Clear processing order
- Efficient computation

### Dependency Resolution

AIPerf uses topological sorting to compute metrics in the correct order:

```python
from aiperf.metrics.metric_registry import MetricRegistry

# Get dependency order for all metrics
order = MetricRegistry.create_dependency_order()

# Example order:
# 1. Record metrics with no dependencies
# 2. Record metrics with dependencies
# 3. Aggregate metrics with no dependencies
# 4. Aggregate metrics with dependencies
# 5. Derived metrics
```

## Implementation Patterns

### Pattern 1: Simple Aggregation

Sum values across records:

```python
class TotalTokensMetric(BaseAggregateMetric[int]):
    """Sum all output tokens."""

    tag = "total_tokens"
    header = "Total Tokens"
    unit = GenericMetricUnit.TOKENS
    flags = MetricFlags.LARGER_IS_BETTER

    def __init__(self):
        super().__init__(default_value=0)

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        # Return this record's token count
        return record.output_token_count

    def _aggregate_value(self, value: int) -> None:
        # Sum all token counts
        self._value += value
```

### Pattern 2: Min/Max Tracking

Track extreme values:

```python
class MaxLatencyMetric(BaseAggregateMetric[int]):
    """Track maximum request latency."""

    tag = "max_latency"
    header = "Maximum Latency"
    unit = MetricTimeUnit.NANOSECONDS
    flags = MetricFlags.NONE
    required_metrics = {RequestLatencyMetric.tag}

    def __init__(self):
        super().__init__(default_value=0)

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        # Get latency from record metrics
        return record_metrics.get_or_raise(RequestLatencyMetric)

    def _aggregate_value(self, value: int) -> None:
        # Keep maximum value
        self._value = max(self._value, value)
```

### Pattern 3: Ratio Computation

Compute ratios from aggregated values:

```python
class AverageOutputLengthMetric(BaseDerivedMetric[float]):
    """Compute average output token count."""

    tag = "average_output_length"
    header = "Average Output Length"
    unit = GenericMetricUnit.TOKENS
    flags = MetricFlags.NONE
    required_metrics = {
        TotalTokensMetric.tag,
        RequestCountMetric.tag,
    }

    def _derive_value(self, metric_results: MetricResultsDict) -> float:
        total_tokens = metric_results.get_or_raise(TotalTokensMetric)
        request_count = metric_results.get_or_raise(RequestCountMetric)

        if request_count == 0:
            return 0.0

        return total_tokens / request_count
```

### Pattern 4: Statistical Aggregation

Compute statistics from record metric lists:

```python
class MedianTTFTMetric(BaseDerivedMetric[float]):
    """Compute median TTFT."""

    tag = "median_ttft"
    header = "Median TTFT"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.NONE
    required_metrics = {TTFTMetric.tag}

    def _derive_value(self, metric_results: MetricResultsDict) -> float:
        # Get list of TTFT values
        ttft_values = metric_results.get_or_raise(TTFTMetric)

        if not ttft_values:
            raise NoMetricValue("No TTFT values available")

        # Compute median
        import numpy as np
        return float(np.median(ttft_values))
```

### Pattern 5: Conditional Aggregation

Aggregate only records meeting criteria:

```python
class LongRequestCountMetric(BaseAggregateMetric[int]):
    """Count requests with latency > 1 second."""

    tag = "long_request_count"
    header = "Long Request Count"
    unit = GenericMetricUnit.REQUESTS
    flags = MetricFlags.NONE
    required_metrics = {RequestLatencyMetric.tag}

    THRESHOLD_NS = 1_000_000_000  # 1 second

    def __init__(self):
        super().__init__(default_value=0)

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> int:
        latency = record_metrics.get_or_raise(RequestLatencyMetric)

        # Return 1 if latency exceeds threshold
        return 1 if latency > self.THRESHOLD_NS else 0

    def _aggregate_value(self, value: int) -> None:
        self._value += value
```

## Custom Aggregate Metrics

### Example: Weighted Average

```python
class WeightedAverageLatencyMetric(BaseAggregateMetric[float]):
    """Compute weighted average latency based on token count."""

    tag = "weighted_avg_latency"
    header = "Weighted Average Latency"
    unit = MetricTimeUnit.NANOSECONDS
    display_unit = MetricTimeUnit.MILLISECONDS
    flags = MetricFlags.NONE
    required_metrics = {
        RequestLatencyMetric.tag,
        OutputSequenceLengthMetric.tag,
    }

    def __init__(self):
        super().__init__(default_value={"sum_weighted": 0.0, "sum_weights": 0.0})

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> dict[str, float]:
        latency = record_metrics.get_or_raise(RequestLatencyMetric)
        tokens = record_metrics.get_or_raise(OutputSequenceLengthMetric)

        # Return weighted latency and weight
        return {
            "sum_weighted": latency * tokens,
            "sum_weights": float(tokens),
        }

    def _aggregate_value(self, value: dict[str, float]) -> None:
        self._value["sum_weighted"] += value["sum_weighted"]
        self._value["sum_weights"] += value["sum_weights"]

    @property
    def current_value(self) -> float:
        """Override to compute final average."""
        if self._value["sum_weights"] == 0:
            return 0.0
        return self._value["sum_weighted"] / self._value["sum_weights"]
```

## Custom Derived Metrics

### Example: Efficiency Ratio

```python
class EfficiencyRatioMetric(BaseDerivedMetric[float]):
    """Compute ratio of good requests to total requests."""

    tag = "efficiency_ratio"
    header = "Efficiency Ratio"
    unit = GenericMetricUnit.PERCENTAGE
    flags = MetricFlags.LARGER_IS_BETTER
    required_metrics = {
        GoodRequestCountMetric.tag,
        RequestCountMetric.tag,
    }

    def _derive_value(self, metric_results: MetricResultsDict) -> float:
        good_count = metric_results.get_or_raise(GoodRequestCountMetric)
        total_count = metric_results.get_or_raise(RequestCountMetric)

        if total_count == 0:
            return 0.0

        return (good_count / total_count) * 100.0
```

### Example: Complex Multi-Metric Computation

```python
class PerformanceScoreMetric(BaseDerivedMetric[float]):
    """Compute composite performance score."""

    tag = "performance_score"
    header = "Performance Score"
    unit = GenericMetricUnit.SCORE
    flags = MetricFlags.LARGER_IS_BETTER
    required_metrics = {
        RequestThroughputMetric.tag,
        TTFTMetric.tag,
        InterTokenLatencyMetric.tag,
        GoodputMetric.tag,
    }

    def _derive_value(self, metric_results: MetricResultsDict) -> float:
        # Get throughput (higher is better)
        throughput = metric_results.get_or_raise(RequestThroughputMetric)

        # Get TTFT values (lower is better)
        ttft_values = metric_results.get_or_raise(TTFTMetric)
        avg_ttft_ms = sum(ttft_values) / len(ttft_values) / 1_000_000

        # Get ITL values (lower is better)
        itl_values = metric_results.get_or_raise(InterTokenLatencyMetric)
        avg_itl_ms = sum(itl_values) / len(itl_values) / 1_000_000

        # Get goodput (higher is better)
        goodput = metric_results.get_or_raise(GoodputMetric)

        # Compute weighted score (higher is better)
        # Normalize and weight components
        throughput_score = throughput / 100.0  # Normalize to ~1.0
        latency_score = 100.0 / (avg_ttft_ms + avg_itl_ms)  # Invert for lower=better
        quality_score = goodput / 100.0  # Normalize to ~1.0

        # Weighted combination
        return (
            0.4 * throughput_score +
            0.3 * latency_score +
            0.3 * quality_score
        ) * 100.0  # Scale to 0-100
```

## Performance Considerations

### Aggregate Metrics

**Efficient Aggregation**:

```python
# Good: Simple increment
def _aggregate_value(self, value: int) -> None:
    self._value += value

# Good: Simple comparison
def _aggregate_value(self, value: int) -> None:
    self._value = max(self._value, value)

# Less efficient: Complex computation
def _aggregate_value(self, value: int) -> None:
    self._value = compute_complex_function(self._value, value)
```

**Memory Efficiency**:

```python
# Good: Scalar accumulator
def __init__(self):
    super().__init__(default_value=0)  # 8 bytes

# Less efficient: Large accumulator
def __init__(self):
    super().__init__(default_value=[])  # Grows with each record
```

### Derived Metrics

**Computation Efficiency**:

```python
# Good: Simple arithmetic
def _derive_value(self, metric_results) -> float:
    return metric_results.get_or_raise(A) / metric_results.get_or_raise(B)

# Less efficient: Expensive computation
def _derive_value(self, metric_results) -> float:
    values = metric_results.get_or_raise(RecordMetric)
    # Avoid sorting millions of values if not necessary
    return sorted(values)[len(values) // 2]
```

**Memory Access**:

```python
# Good: Access metrics once
def _derive_value(self, metric_results) -> float:
    values = metric_results.get_or_raise(RecordMetric)  # Access once
    return sum(values) / len(values)

# Less efficient: Repeated access
def _derive_value(self, metric_results) -> float:
    total = sum(metric_results.get_or_raise(RecordMetric))
    count = len(metric_results.get_or_raise(RecordMetric))  # Access again
    return total / count
```

## Testing

### Testing Aggregate Metrics

```python
def test_request_count_metric():
    """Test request count aggregation."""
    metric = RequestCountMetric()

    # Simulate worker results
    worker_results = [1, 1, 1, 1, 1]  # 5 records

    # Aggregate
    for value in worker_results:
        metric.aggregate_value(value)

    # Verify
    assert metric.current_value == 5

def test_max_latency_metric():
    """Test maximum latency tracking."""
    metric = MaxLatencyMetric()

    # Simulate worker results
    latencies = [100, 250, 150, 300, 200]

    # Aggregate
    for latency in latencies:
        metric.aggregate_value(latency)

    # Verify
    assert metric.current_value == 300
```

### Testing Derived Metrics

```python
def test_request_throughput_metric():
    """Test throughput calculation."""
    # Create mock results
    metric_results = MetricResultsDict()
    metric_results[RequestCountMetric.tag] = 1000
    metric_results[BenchmarkDurationMetric.tag] = 10_000_000_000  # 10 seconds in ns

    # Compute derived metric
    metric = RequestThroughputMetric()
    throughput = metric.derive_value(metric_results)

    # Verify: 1000 requests / 10 seconds = 100 req/s
    assert throughput == 100.0

def test_goodput_metric():
    """Test goodput calculation."""
    metric_results = MetricResultsDict()
    metric_results[GoodRequestCountMetric.tag] = 800
    metric_results[BenchmarkDurationMetric.tag] = 10_000_000_000  # 10 seconds

    metric = GoodputMetric()
    goodput = metric.derive_value(metric_results)

    # Verify: 800 good requests / 10 seconds = 80 req/s
    assert goodput == 80.0
```

## Debugging

### Inspecting Aggregate Metrics

```python
# Check current value during processing
metric = RequestCountMetric()
print(f"Current count: {metric.current_value}")

# Debug aggregation
def _aggregate_value(self, value: int) -> None:
    print(f"Aggregating {value}, current: {self._value}")
    self._value += value
    print(f"New total: {self._value}")
```

### Inspecting Derived Metrics

```python
def _derive_value(self, metric_results: MetricResultsDict) -> float:
    # Debug dependency values
    count = metric_results.get_or_raise(RequestCountMetric)
    duration = metric_results.get_or_raise(BenchmarkDurationMetric)

    print(f"Computing throughput:")
    print(f"  Count: {count}")
    print(f"  Duration: {duration}")

    result = count / duration
    print(f"  Result: {result}")

    return result
```

## Key Takeaways

1. **Two-Phase Processing**: Aggregate metrics split record processing from aggregation for parallelism

2. **Hierarchy Matters**: Record → Aggregate → Derived ensures correct dependency ordering

3. **Type Safety**: Use generic types and typed access methods for correctness

4. **Unit Conversion**: MetricResultsDict handles automatic unit conversions

5. **Counter Pattern**: BaseAggregateCounterMetric simplifies simple counting metrics

6. **No Record Access**: Derived metrics only see aggregated results, not raw records

7. **Dependency Flexibility**: Derived metrics can depend on any metric type

8. **Statistical Power**: Derived metrics can compute complex statistics from record metric lists

9. **Memory Efficiency**: Aggregate metrics should use scalar accumulators when possible

10. **Testing is Simple**: Mock MetricResultsDict for testing derived metrics

## What's Next

With a complete understanding of all three metric tiers, we now move to the HTTP client layer that captures the timing data these metrics analyze:

- **Chapter 23: HTTP Client Architecture** - Explore the high-performance HTTP client that captures nanosecond-precision timing data

---

**Remember**: Aggregate and derived metrics transform per-request data into benchmark-level insights. Master these patterns to build powerful analytical capabilities.
