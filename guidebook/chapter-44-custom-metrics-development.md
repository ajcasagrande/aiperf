# Chapter 44: Custom Metrics Development

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Overview

This chapter provides a comprehensive guide to creating custom metrics in AIPerf. Learn how to define, register, test, and deploy custom metrics that integrate seamlessly with AIPerf's metric system.

## Table of Contents

- [Metric System Architecture](#metric-system-architecture)
- [Metric Types](#metric-types)
- [Creating Record Metrics](#creating-record-metrics)
- [Creating Aggregate Metrics](#creating-aggregate-metrics)
- [Creating Derived Metrics](#creating-derived-metrics)
- [Metric Registration](#metric-registration)
- [Metric Flags](#metric-flags)
- [Metric Units](#metric-units)
- [Testing Custom Metrics](#testing-custom-metrics)
- [Complete Examples](#complete-examples)

---

## Metric System Architecture

### Metric Flow

```
┌────────────────────────────────────────────────────────────┐
│                    Metric Computation Flow                  │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  Raw Records                                                │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────────┐                                          │
│  │   Record     │ ← Computed per request                   │
│  │   Metrics    │                                          │
│  └───────┬──────┘                                          │
│          │                                                  │
│          ▼                                                  │
│  ┌──────────────┐                                          │
│  │  Aggregate   │ ← Statistics (mean, p99, etc.)           │
│  │   Metrics    │                                          │
│  └───────┬──────┘                                          │
│          │                                                  │
│          ▼                                                  │
│  ┌──────────────┐                                          │
│  │   Derived    │ ← Computed from other metrics            │
│  │   Metrics    │                                          │
│  └──────────────┘                                          │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### Base Classes

**Location**: `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/`

- `BaseRecordMetric`: Per-request metrics
- `BaseAggregateMetric`: Aggregated statistics
- `BaseDerivedMetric`: Computed from other metrics

---

## Metric Types

### 1. Record Metrics

Computed for each individual request:

```python
from aiperf.metrics import BaseRecordMetric
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.metric_dicts import MetricRecordDict

class RequestLatencyMetric(BaseRecordMetric[float]):
    """Compute latency for each request"""

    tag = "request_latency"
    header = "Request Latency"
    unit = TimeMetricUnit.MILLISECONDS

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict
    ) -> float:
        latency_seconds = record.request_end_time - record.request_start_time
        return latency_seconds * 1000  # Convert to milliseconds
```

### 2. Aggregate Metrics

Statistics computed from record metrics:

```python
from aiperf.metrics import BaseAggregateMetric

class RequestLatencyP99Metric(BaseAggregateMetric[float]):
    """Compute 99th percentile latency"""

    tag = "request_latency_p99"
    header = "Request Latency P99"
    unit = TimeMetricUnit.MILLISECONDS
    required_metrics = {"request_latency"}

    def _aggregate(
        self,
        metric_tag: str,
        values: list[float]
    ) -> float:
        return np.percentile(values, 99)
```

### 3. Derived Metrics

Computed from other aggregate metrics:

```python
from aiperf.metrics import BaseDerivedMetric
from aiperf.metrics.metric_dicts import MetricResultsDict

class ThroughputMetric(BaseDerivedMetric[float]):
    """Compute throughput from count and duration"""

    tag = "throughput"
    header = "Throughput"
    unit = GenericMetricUnit.RATIO
    required_metrics = {"request_count", "benchmark_duration"}

    def _derive(
        self,
        metrics: MetricResultsDict
    ) -> float:
        count = metrics["request_count"]
        duration = metrics["benchmark_duration"]
        return count / duration if duration > 0 else 0.0
```

---

## Creating Record Metrics

### Basic Record Metric

**Example**: Custom token ratio metric

**File**: `/home/anthony/nvidia/projects/aiperf/examples/custom-metrics/custom_record_metric.py`

```python
from aiperf.metrics import BaseRecordMetric
from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.common.exceptions import NoMetricValue
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.metric_dicts import MetricRecordDict


class OutputToInputRatioMetric(BaseRecordMetric[float]):
    """
    Compute the ratio of output tokens to input tokens.

    This metric helps understand how much output the model generates
    relative to the input prompt size.

    Formula:
        ratio = output_tokens / input_tokens
    """

    # Required: Unique identifier for this metric
    tag = "output_to_input_ratio"

    # Required: Display name shown in results
    header = "Output/Input Ratio"

    # Optional: Short name for compact displays (dashboards)
    short_header = "O/I Ratio"

    # Required: Unit of measurement
    unit = GenericMetricUnit.RATIO

    # Optional: Control display order (lower = earlier)
    display_order = 500

    # Required: Flags controlling when/how metric is computed
    flags = MetricFlags.PRODUCES_TOKENS_ONLY | MetricFlags.LARGER_IS_BETTER

    # Optional: Dependencies on other metrics (none in this case)
    required_metrics = None

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> float:
        """
        Compute the metric value for a single record.

        Args:
            record: Parsed response record with token counts
            record_metrics: Previously computed metrics (for dependencies)

        Returns:
            The output/input ratio

        Raises:
            NoMetricValue: If token counts are not available
        """
        # Check if token counts are available
        if record.input_token_count is None or record.input_token_count == 0:
            raise NoMetricValue("Input token count not available or zero")

        if record.output_token_count is None:
            raise NoMetricValue("Output token count not available")

        # Compute ratio
        ratio = record.output_token_count / record.input_token_count

        return ratio
```

### Complex Record Metric

**Example**: Inter-token latency with validation

```python
from aiperf.metrics import BaseRecordMetric
from aiperf.common.enums import TimeMetricUnit, MetricFlags
from aiperf.common.exceptions import NoMetricValue
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.metric_dicts import MetricRecordDict


class InterTokenLatencyMetric(BaseRecordMetric[float]):
    """
    Compute the average time between consecutive tokens.

    Only applicable to streaming responses with multiple tokens.
    """

    tag = "inter_token_latency"
    header = "Inter Token Latency"
    short_header = "ITL"
    unit = TimeMetricUnit.MILLISECONDS
    display_order = 200
    flags = (
        MetricFlags.PRODUCES_TOKENS_ONLY
        | MetricFlags.STREAMING_ONLY
        | MetricFlags.SMALLER_IS_BETTER
    )

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> float:
        # Validate streaming response
        if not record.inter_token_times:
            raise NoMetricValue("No inter-token times available")

        # Need at least 2 tokens
        if len(record.inter_token_times) < 1:
            raise NoMetricValue("Insufficient tokens for inter-token latency")

        # Compute average inter-token latency
        avg_latency = sum(record.inter_token_times) / len(record.inter_token_times)

        # Convert to milliseconds
        return avg_latency * 1000
```

### Record Metric with Dependencies

**Example**: Efficiency metric depending on other record metrics

```python
from aiperf.metrics import BaseRecordMetric
from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.metric_dicts import MetricRecordDict


class TokenGenerationEfficiencyMetric(BaseRecordMetric[float]):
    """
    Compute token generation efficiency as tokens per second.

    Depends on output_token_count and request_latency metrics.
    """

    tag = "token_generation_efficiency"
    header = "Token Generation Efficiency"
    short_header = "TGE"
    unit = GenericMetricUnit.TOKENS_PER_SECOND
    display_order = 300
    flags = MetricFlags.PRODUCES_TOKENS_ONLY | MetricFlags.LARGER_IS_BETTER

    # Declare dependencies
    required_metrics = {"output_sequence_length", "request_latency"}

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict,
    ) -> float:
        # Access dependent metrics (already validated)
        output_tokens = record_metrics["output_sequence_length"]
        latency_ms = record_metrics["request_latency"]

        # Convert latency to seconds
        latency_s = latency_ms / 1000

        # Compute tokens per second
        if latency_s > 0:
            return output_tokens / latency_s
        else:
            return 0.0
```

---

## Creating Aggregate Metrics

### Statistical Aggregate

```python
from aiperf.metrics import BaseAggregateMetric
from aiperf.common.enums import TimeMetricUnit, MetricFlags
import numpy as np


class LatencyPercentileMetric(BaseAggregateMetric[float]):
    """Compute specific percentile of latency"""

    tag = "request_latency_p95"
    header = "Request Latency P95"
    unit = TimeMetricUnit.MILLISECONDS
    display_order = 150
    flags = MetricFlags.SMALLER_IS_BETTER

    required_metrics = {"request_latency"}

    def _aggregate(
        self,
        metric_tag: str,
        values: list[float]
    ) -> float:
        if not values:
            return 0.0
        return float(np.percentile(values, 95))
```

### Custom Aggregate Logic

```python
from aiperf.metrics import BaseAggregateCounterMetric
from aiperf.common.enums import GenericMetricUnit, MetricFlags


class SuccessRateMetric(BaseAggregateCounterMetric[float]):
    """Compute success rate as percentage of valid requests"""

    tag = "success_rate"
    header = "Success Rate"
    unit = GenericMetricUnit.PERCENTAGE
    display_order = 50
    flags = MetricFlags.LARGER_IS_BETTER

    def _compute_aggregate(
        self,
        total_count: int,
        valid_count: int,
        error_count: int
    ) -> float:
        if total_count == 0:
            return 0.0
        return (valid_count / total_count) * 100
```

---

## Creating Derived Metrics

### Simple Derived Metric

```python
from aiperf.metrics import BaseDerivedMetric
from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.metrics.metric_dicts import MetricResultsDict


class RequestThroughputMetric(BaseDerivedMetric[float]):
    """Compute overall request throughput"""

    tag = "request_throughput"
    header = "Request Throughput"
    short_header = "Req/s"
    unit = GenericMetricUnit.REQUESTS_PER_SECOND
    display_order = 10
    flags = MetricFlags.LARGER_IS_BETTER

    required_metrics = {"request_count", "benchmark_duration"}

    def _derive(
        self,
        metrics: MetricResultsDict
    ) -> float:
        count = metrics["request_count"]
        duration = metrics["benchmark_duration"]

        if duration > 0:
            return count / duration
        return 0.0
```

### Complex Derived Metric

```python
from aiperf.metrics import BaseDerivedMetric
from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.metrics.metric_dicts import MetricResultsDict
from aiperf.common.exceptions import NoMetricValue


class GoodputMetric(BaseDerivedMetric[float]):
    """
    Compute goodput: successful throughput excluding errors.

    Goodput = (successful_requests / total_time) * (1 - error_rate)
    """

    tag = "goodput"
    header = "Goodput"
    short_header = "Goodput"
    unit = GenericMetricUnit.REQUESTS_PER_SECOND
    display_order = 15
    flags = MetricFlags.LARGER_IS_BETTER

    required_metrics = {
        "good_request_count",
        "request_count",
        "benchmark_duration"
    }

    def _derive(
        self,
        metrics: MetricResultsDict
    ) -> float:
        good_requests = metrics["good_request_count"]
        total_requests = metrics["request_count"]
        duration = metrics["benchmark_duration"]

        if duration <= 0:
            raise NoMetricValue("Benchmark duration must be positive")

        if total_requests == 0:
            return 0.0

        # Goodput = successful requests per second
        goodput = good_requests / duration

        return goodput
```

---

## Metric Registration

### Automatic Registration

Metrics are automatically registered when the class is defined:

```python
from aiperf.metrics import BaseRecordMetric

# Automatically registered upon class definition
class MyMetric(BaseRecordMetric[float]):
    tag = "my_metric"
    # ...
```

### Verify Registration

```python
from aiperf.metrics.metric_registry import MetricRegistry

# Check if metric is registered
assert "my_metric" in MetricRegistry.all_tags()

# Get metric class
metric_class = MetricRegistry.get_class("my_metric")

# Get metric instance
metric_instance = MetricRegistry.get_instance("my_metric")
```

### Dependency Order

Metrics are computed in dependency order:

```python
# Compute dependency order
dependency_order = MetricRegistry.create_dependency_order()

# Order ensures dependencies computed first
for tag in dependency_order:
    metric = MetricRegistry.get_instance(tag)
    # Compute metric...
```

---

## Metric Flags

### Available Flags

```python
from aiperf.common.enums import MetricFlags

# Applicability flags
MetricFlags.PRODUCES_TOKENS_ONLY    # Only for token-generating endpoints
MetricFlags.STREAMING_ONLY           # Only for streaming responses
MetricFlags.ERROR_ONLY              # Only computed for errors

# Display flags
MetricFlags.LARGER_IS_BETTER        # Higher values are better
MetricFlags.SMALLER_IS_BETTER       # Lower values are better

# Visibility flags
MetricFlags.INTERNAL                # Internal use only
MetricFlags.EXPERIMENTAL            # Experimental metric
```

### Using Flags

```python
class MyMetric(BaseRecordMetric[float]):
    # Multiple flags
    flags = (
        MetricFlags.PRODUCES_TOKENS_ONLY
        | MetricFlags.STREAMING_ONLY
        | MetricFlags.SMALLER_IS_BETTER
    )
```

### Conditional Computation

```python
# Filter metrics by flags
applicable_metrics = MetricRegistry.tags_applicable_to(
    required_flags=MetricFlags.PRODUCES_TOKENS_ONLY,
    disallowed_flags=MetricFlags.STREAMING_ONLY,
    MetricType.RECORD
)
```

---

## Metric Units

### Available Units

```python
from aiperf.common.enums import (
    TimeMetricUnit,
    DataMetricUnit,
    GenericMetricUnit
)

# Time units
TimeMetricUnit.SECONDS
TimeMetricUnit.MILLISECONDS
TimeMetricUnit.MICROSECONDS

# Data units
DataMetricUnit.BYTES
DataMetricUnit.KILOBYTES
DataMetricUnit.MEGABYTES

# Generic units
GenericMetricUnit.COUNT
GenericMetricUnit.RATIO
GenericMetricUnit.PERCENTAGE
GenericMetricUnit.TOKENS
GenericMetricUnit.TOKENS_PER_SECOND
GenericMetricUnit.REQUESTS_PER_SECOND
```

### Unit Conversion

```python
class MyMetric(BaseRecordMetric[float]):
    tag = "my_metric"
    unit = TimeMetricUnit.SECONDS
    display_unit = TimeMetricUnit.MILLISECONDS  # Display in ms
```

---

## Testing Custom Metrics

### Unit Tests

```python
import pytest
from aiperf.common.models import ParsedResponseRecord
from aiperf.common.exceptions import NoMetricValue


def test_output_to_input_ratio():
    """Test OutputToInputRatioMetric"""
    metric = OutputToInputRatioMetric()

    # Create test record
    record = ParsedResponseRecord(
        input_token_count=100,
        output_token_count=200,
        valid=True
    )

    # Compute metric
    result = metric.parse_record(record, {})

    # Assert expected value
    assert result == 2.0


def test_output_to_input_ratio_no_input():
    """Test with zero input tokens"""
    metric = OutputToInputRatioMetric()

    record = ParsedResponseRecord(
        input_token_count=0,
        output_token_count=200,
        valid=True
    )

    # Should raise NoMetricValue
    with pytest.raises(NoMetricValue):
        metric.parse_record(record, {})


def test_output_to_input_ratio_missing_output():
    """Test with missing output tokens"""
    metric = OutputToInputRatioMetric()

    record = ParsedResponseRecord(
        input_token_count=100,
        output_token_count=None,
        valid=True
    )

    with pytest.raises(NoMetricValue):
        metric.parse_record(record, {})
```

### Integration Tests

```python
def test_metric_in_benchmark(mock_server):
    """Test custom metric in full benchmark"""
    from aiperf.cli_runner import run_system_controller
    from aiperf.common.config import UserConfig, EndpointConfig, LoadGeneratorConfig

    # Configure benchmark
    endpoint_config = EndpointConfig(
        model_names=["test-model"],
        url=mock_server.url,
        type="chat",
        streaming=True
    )

    loadgen_config = LoadGeneratorConfig(
        request_count=10,
        concurrency=1
    )

    user_config = UserConfig(
        endpoint=endpoint_config,
        loadgen=loadgen_config
    )

    # Run benchmark
    results = run_system_controller(user_config, service_config)

    # Verify custom metric is computed
    assert "output_to_input_ratio" in results.metrics
    assert results.metrics["output_to_input_ratio"]["avg"] > 0
```

---

## Complete Examples

### Example 1: Custom Error Rate Metric

```python
from aiperf.metrics import BaseDerivedMetric
from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.metrics.metric_dicts import MetricResultsDict


class ErrorRateMetric(BaseDerivedMetric[float]):
    """Compute error rate as percentage of failed requests"""

    tag = "error_rate"
    header = "Error Rate"
    short_header = "Errors"
    unit = GenericMetricUnit.PERCENTAGE
    display_order = 40
    flags = MetricFlags.SMALLER_IS_BETTER

    required_metrics = {"error_request_count", "request_count"}

    def _derive(self, metrics: MetricResultsDict) -> float:
        errors = metrics["error_request_count"]
        total = metrics["request_count"]

        if total == 0:
            return 0.0

        return (errors / total) * 100
```

### Example 2: Custom Latency Breakdown

```python
from aiperf.metrics import BaseRecordMetric
from aiperf.common.enums import TimeMetricUnit, MetricFlags
from aiperf.common.exceptions import NoMetricValue
from aiperf.common.models import ParsedResponseRecord
from aiperf.metrics.metric_dicts import MetricRecordDict


class ProcessingTimeMetric(BaseRecordMetric[float]):
    """
    Compute processing time excluding network overhead.

    Processing time = request_latency - network_latency
    """

    tag = "processing_time"
    header = "Processing Time"
    unit = TimeMetricUnit.MILLISECONDS
    display_order = 120
    flags = MetricFlags.SMALLER_IS_BETTER

    def _parse_record(
        self,
        record: ParsedResponseRecord,
        record_metrics: MetricRecordDict
    ) -> float:
        # Total latency
        total_latency = (
            record.request_end_time - record.request_start_time
        ) * 1000  # Convert to ms

        # Estimate network latency (time to first byte)
        if record.first_token_time is None:
            raise NoMetricValue("TTFB not available")

        network_latency = (
            record.first_token_time - record.request_start_time
        ) * 1000

        # Processing time
        processing_time = total_latency - network_latency

        return max(0.0, processing_time)  # Ensure non-negative
```

### Example 3: Business Metric

```python
from aiperf.metrics import BaseDerivedMetric
from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.metrics.metric_dicts import MetricResultsDict


class CostPerRequestMetric(BaseDerivedMetric[float]):
    """
    Estimate cost per request based on token usage.

    Assumes pricing model: $0.01 per 1000 input tokens, $0.02 per 1000 output tokens
    """

    tag = "cost_per_request"
    header = "Cost Per Request"
    unit = GenericMetricUnit.CURRENCY
    display_order = 1000
    flags = MetricFlags.SMALLER_IS_BETTER

    required_metrics = {
        "input_sequence_length",
        "output_sequence_length",
        "request_count"
    }

    # Pricing (per 1000 tokens)
    INPUT_PRICE = 0.01
    OUTPUT_PRICE = 0.02

    def _derive(self, metrics: MetricResultsDict) -> float:
        avg_input_tokens = metrics["input_sequence_length"]["avg"]
        avg_output_tokens = metrics["output_sequence_length"]["avg"]

        # Calculate cost
        input_cost = (avg_input_tokens / 1000) * self.INPUT_PRICE
        output_cost = (avg_output_tokens / 1000) * self.OUTPUT_PRICE

        total_cost = input_cost + output_cost

        return total_cost
```

---

## Key Takeaways

1. **Three Metric Types**: Record, Aggregate, and Derived metrics
2. **Automatic Registration**: Metrics register upon class definition
3. **Type Safety**: Strong typing with generic type parameters
4. **Dependencies**: Declare required metrics for dependency resolution
5. **Flags**: Control applicability and display behavior
6. **Units**: Define measurement units with conversion support
7. **Testing**: Comprehensive unit and integration tests
8. **Documentation**: Clear docstrings and examples

---

## Navigation

- [Previous Chapter: Chapter 43 - Common Patterns](chapter-43-common-patterns.md)
- [Next Chapter: Chapter 45 - Custom Dataset Development](chapter-45-custom-dataset-development.md)
- [Return to Index](INDEX.md)

---

**Document Information**
- **File**: `/home/anthony/nvidia/projects/aiperf/guidebook/chapter-44-custom-metrics-development.md`
- **Purpose**: Guide to creating custom metrics in AIPerf
- **Target Audience**: Developers adding custom metrics
- **Related Files**:
  - `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/base_metric.py`
  - `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/base_record_metric.py`
  - `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/metric_registry.py`
  - `/home/anthony/nvidia/projects/aiperf/examples/custom-metrics/`
