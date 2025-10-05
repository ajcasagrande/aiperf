# Chapter 20: Metrics Foundation

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Overview

The Metrics Foundation is AIPerf's extensible metric computation framework, built on a type-safe hierarchy with automatic registration, dependency resolution, and flexible aggregation. Every metric - from simple counters to complex statistical aggregations - inherits from a common base and participates in a registry-based discovery system. This chapter explores the metrics architecture, type hierarchy, registry system, auto-registration mechanism, dependency management, and the patterns enabling AIPerf's comprehensive metric suite.

## Metrics Architecture

### Design Philosophy

AIPerf's metric system follows these principles:

1. **Type Safety**: Strong typing via generic parameters and Pydantic validation
2. **Auto-Registration**: Metrics register automatically via `__init_subclass__`
3. **Declarative Dependencies**: Metrics declare required dependencies
4. **Lazy Evaluation**: Metrics computed on-demand
5. **Extensibility**: Easy to add custom metrics via inheritance

### Metric Computation Pipeline

```
Raw Request → Record Processor → Metric Records → Results Processor → Metric Results
                 (per-request)                       (aggregated)
```

**Record Metrics**: Computed per-request (TTFT, latency, token counts)
**Aggregate Metrics**: Accumulated across requests (average latency, p99)
**Derived Metrics**: Computed from other metrics (throughput from tokens/latency)

## Type Hierarchy

### BaseMetric

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/base_metric.py`:

```python
class BaseMetric(Generic[MetricValueTypeVarT], ABC):
    """A definition of a metric type.

    Class attributes:
    - tag: Unique identifier for the metric
    - header: User-friendly name for display
    - short_header: Abbreviated name for dashboard
    - unit: Internal representation unit
    - display_unit: Display unit (if different from unit)
    - short_header_hide_unit: Hide unit in dashboard
    - display_order: Order in console export
    - flags: Computation and display flags
    - required_metrics: Dependencies on other metrics
    """

    # User-defined attributes to be overridden by subclasses
    tag: ClassVar[MetricTagT]
    header: ClassVar[str] = ""
    short_header: ClassVar[str | None] = None
    short_header_hide_unit: ClassVar[bool] = False
    unit: ClassVar[MetricUnitT]
    display_unit: ClassVar[MetricUnitT | None] = None
    display_order: ClassVar[int | None] = None
    flags: ClassVar[MetricFlags] = MetricFlags.NONE
    required_metrics: ClassVar[set[MetricTagT] | None] = None

    # Auto-derived attributes
    value_type: ClassVar[MetricValueType]  # Auto set based on generic type
    type: ClassVar[MetricType]  # Set by base subclasses

    def __init_subclass__(cls, **kwargs):
        """Called when a class is subclassed from Metric.
        Automatically registers the subclass in the MetricRegistry."""
        super().__init_subclass__(**kwargs)

        # Only register concrete classes (not abstract ones)
        if inspect.isabstract(cls) or (
            hasattr(cls, "__is_abstract__") and cls.__is_abstract__
        ):
            return

        # Verify that the class is a valid metric type
        cls._verify_base_class()

        # Import MetricRegistry here to avoid circular imports
        from aiperf.metrics.metric_registry import MetricRegistry

        # Enforce that subclasses define a non-empty tag
        if not cls.tag or not isinstance(cls.tag, str):
            raise TypeError(
                f"Concrete metric class {cls.__name__} must define a "
                f"non-empty 'tag' class attribute"
            )

        # Auto-detect value type from generic parameter
        cls.value_type = cls._detect_value_type()

        MetricRegistry.register_metric(cls)

    @classmethod
    def _verify_base_class(cls) -> None:
        """Verify that the class is a subclass of BaseRecordMetric,
        BaseAggregateMetric, or BaseDerivedMetric."""
        from aiperf.metrics import (
            BaseAggregateMetric,
            BaseDerivedMetric,
            BaseRecordMetric,
        )

        valid_base_classes = {
            BaseRecordMetric,
            BaseAggregateMetric,
            BaseDerivedMetric,
        }
        if not any(issubclass(cls, base) for base in valid_base_classes):
            raise TypeError(
                f"Concrete metric class {cls.__name__} must be a subclass of "
                f"BaseRecordMetric, BaseAggregateMetric, or BaseDerivedMetric"
            )

    @classmethod
    def _detect_value_type(cls) -> MetricValueType:
        """Automatically detect the MetricValueType from the generic type parameter."""
        # Look through the class hierarchy for the first Generic[Type] definition
        for base in cls.__orig_bases__:
            if get_origin(base) is not None:
                args = get_args(base)
                if args:
                    # the first argument is the generic type
                    generic_type = args[0]
                    return MetricValueType.from_python_type(generic_type)

        raise ValueError(
            f"Unable to detect the value type for {cls.__name__}. "
            f"Please check the generic type parameter."
        )

    def _require_valid_record(self, record: ParsedResponseRecord) -> None:
        """Check that the record is valid."""
        if (not record or not record.valid) and not self.has_flags(
            MetricFlags.ERROR_ONLY
        ):
            raise NoMetricValue("Invalid Record")

    def _check_metrics(self, metrics: MetricRecordDict | MetricResultsDict) -> None:
        """Check that the required metrics are available."""
        if self.required_metrics is None:
            return
        for tag in self.required_metrics:
            if tag not in metrics:
                raise NoMetricValue(f"Missing required metric: '{tag}'")

    @classmethod
    def has_flags(cls, flags: MetricFlags) -> bool:
        """Return True if the metric has the given flag(s)."""
        return cls.flags.has_flags(flags)
```

**Key Features:**

1. **Generic Type Parameter**: `Generic[MetricValueTypeVarT]` enables type-safe metrics
2. **Auto-Registration**: `__init_subclass__` registers concrete metrics
3. **Value Type Detection**: Automatically infers value type from generic
4. **Dependency Checking**: `_check_metrics()` validates required metrics
5. **Flag System**: Control computation/display behavior

### BaseRecordMetric

Per-request metrics:

```python
class BaseRecordMetric(BaseMetric[MetricValueTypeVarT], ABC):
    """Base class for record-level metrics.

    Record metrics are computed for each individual request/response pair.
    """

    type: ClassVar[MetricType] = MetricType.RECORD
    __is_abstract__ = True

    @abstractmethod
    def parse_record(
        self,
        record: ParsedResponseRecord,
        metrics: MetricRecordDict,
    ) -> MetricValueTypeVarT:
        """Parse a record and return the metric value."""
        ...
```

**Example:**

```python
class RequestLatencyMetric(BaseRecordMetric[int]):
    """Request latency in nanoseconds."""

    tag: ClassVar[MetricTagT] = "request_latency"
    header: ClassVar[str] = "Request Latency"
    unit: ClassVar[MetricUnitT] = MetricUnit.NANOSECONDS
    display_unit: ClassVar[MetricUnitT] = MetricUnit.MILLISECONDS
    display_order: ClassVar[int] = 100

    def parse_record(
        self,
        record: ParsedResponseRecord,
        metrics: MetricRecordDict,
    ) -> int:
        """Compute request latency."""
        self._require_valid_record(record)
        return record.request_duration_ns
```

### BaseAggregateMetric

Accumulated metrics:

```python
class BaseAggregateMetric(BaseMetric[MetricValueTypeVarT], ABC):
    """Base class for aggregate metrics.

    Aggregate metrics accumulate values across multiple requests and compute
    statistics (avg, min, max, percentiles).
    """

    type: ClassVar[MetricType] = MetricType.AGGREGATE
    __is_abstract__ = True

    def __init__(self):
        self.metric_array = MetricArray[MetricValueTypeVarT](
            value_type=self.value_type,
        )

    async def add_value(self, value: MetricValueTypeVarT) -> None:
        """Add a value to the aggregation."""
        await self.metric_array.add(value)

    async def compute(self) -> MetricResult:
        """Compute aggregate statistics."""
        return await self.metric_array.compute()

    @abstractmethod
    def parse_record(
        self,
        record: ParsedResponseRecord,
        metrics: MetricRecordDict,
    ) -> MetricValueTypeVarT:
        """Parse a record and return the value to aggregate."""
        ...
```

**Example:**

```python
class TTFTMetric(BaseAggregateMetric[int]):
    """Time to First Token in nanoseconds."""

    tag: ClassVar[MetricTagT] = "ttft"
    header: ClassVar[str] = "Time To First Token"
    unit: ClassVar[MetricUnitT] = MetricUnit.NANOSECONDS
    display_unit: ClassVar[MetricUnitT] = MetricUnit.MILLISECONDS
    display_order: ClassVar[int] = 200

    def parse_record(
        self,
        record: ParsedResponseRecord,
        metrics: MetricRecordDict,
    ) -> int:
        """Extract TTFT from record."""
        self._require_valid_record(record)
        if not record.responses:
            raise NoMetricValue("No responses")
        return record.responses[0].perf_ns - record.start_perf_ns
```

### BaseDerivedMetric

Computed from other metrics:

```python
class BaseDerivedMetric(BaseMetric[MetricValueTypeVarT], ABC):
    """Base class for derived metrics.

    Derived metrics are computed from other metrics (record or aggregate).
    """

    type: ClassVar[MetricType] = MetricType.DERIVED
    __is_abstract__ = True

    @abstractmethod
    async def compute(
        self, metrics: MetricResultsDict
    ) -> MetricResult:
        """Compute derived metric from other metrics."""
        ...
```

**Example:**

```python
class OutputTokenThroughputMetric(BaseDerivedMetric[float]):
    """Output tokens per second."""

    tag: ClassVar[MetricTagT] = "output_token_throughput"
    header: ClassVar[str] = "Output Token Throughput"
    unit: ClassVar[MetricUnitT] = MetricUnit.TOKENS_PER_SECOND
    display_order: ClassVar[int] = 300

    required_metrics: ClassVar[set[MetricTagT]] = {
        "output_token_count",
        "request_latency",
    }

    async def compute(self, metrics: MetricResultsDict) -> MetricResult:
        """Compute throughput from token count and latency."""
        self._check_metrics(metrics)

        output_tokens = metrics["output_token_count"].avg
        latency_sec = metrics["request_latency"].avg / NANOS_PER_SECOND

        throughput = output_tokens / latency_sec

        return MetricResult(
            tag=self.tag,
            unit=str(self.unit),
            header=self.header,
            avg=throughput,
        )
```

## Registry System

### MetricRegistry

Located in `/home/anthony/nvidia/projects/aiperf/aiperf/metrics/metric_registry.py`:

```python
class MetricRegistry:
    """Registry for metrics.

    Stores all available metrics and provides methods to:
    - Lookup metrics by tag
    - Get metrics by type, flag
    - Create dependency order
    - Create instances
    """

    # Map of metric tags to their classes
    _metrics_map: dict[MetricTagT, type["BaseMetric"]] = {}

    # Map of metric tags to their instances
    _instances_map: dict[MetricTagT, "BaseMetric"] = {}
    _instance_lock = Lock()

    def __init__(self) -> None:
        raise TypeError(
            "MetricRegistry is a singleton and cannot be instantiated directly"
        )

    @classmethod
    def _discover_metrics(cls) -> None:
        """Dynamically import all metric type modules from the 'types' directory
        to ensure all metric classes are registered via __init_subclass__."""
        types_dir = Path(__file__).parent / "types"

        if not types_dir.exists() or not types_dir.is_dir():
            raise MetricTypeError(
                f"Types directory '{types_dir.resolve()}' does not exist"
            )

        module_prefix = ".".join([*cls.__module__.split(".")[:-1], "types"])

        # Import all metric type modules to trigger registration
        cls._import_metric_type_modules(types_dir, module_prefix)

    @classmethod
    def _import_metric_type_modules(cls, types_dir: Path, module_prefix: str) -> None:
        """Import all metric type modules from the given directory."""
        for python_file in types_dir.glob("*.py"):
            if python_file.name != "__init__.py":
                module_name = python_file.stem
                module_path = f"{module_prefix}.{module_name}"
                try:
                    importlib.import_module(module_path)
                except ImportError as err:
                    raise MetricTypeError(
                        f"Error importing metric type module '{module_path}'"
                    ) from err

    @classmethod
    def register_metric(cls, metric: type["BaseMetric"]):
        """Register a metric class."""
        if metric.tag in cls._metrics_map:
            raise MetricTypeError(
                f"Metric class with tag {metric.tag} already registered by "
                f"{cls._metrics_map[metric.tag].__name__}"
            )

        cls._metrics_map[metric.tag] = metric

    @classmethod
    def get_class(cls, tag: MetricTagT) -> type["BaseMetric"]:
        """Get a metric class by its tag."""
        try:
            return cls._metrics_map[tag]
        except KeyError as e:
            raise MetricTypeError(f"Metric class with tag '{tag}' not found") from e

    @classmethod
    def get_instance(cls, tag: MetricTagT) -> "BaseMetric":
        """Get an instance of a metric class by its tag."""
        # Check first without lock for performance
        if tag not in cls._instances_map:
            with cls._instance_lock:
                # Check again after acquiring lock
                if tag not in cls._instances_map:
                    metric_class = cls.get_class(tag)
                    cls._instances_map[tag] = metric_class()
        return cls._instances_map[tag]
```

**Key Methods:**

- `_discover_metrics()`: Import all metric modules to trigger registration
- `register_metric()`: Register metric class by tag
- `get_class()`: Retrieve metric class by tag
- `get_instance()`: Get singleton metric instance

### Metric Discovery

Metrics discovered at import time:

```python
# At module import
MetricRegistry._discover_metrics()

# This imports all files in metrics/types/
# Each file contains metric classes that auto-register
```

Example metric file structure:

```
aiperf/metrics/types/
├── __init__.py
├── request_latency_metric.py  # RequestLatencyMetric auto-registers
├── ttft_metric.py             # TTFTMetric auto-registers
├── output_token_count.py      # OutputTokenCountMetric auto-registers
└── ...
```

## Auto-Registration

### Registration Mechanism

When a metric class is defined:

```python
class MyCustomMetric(BaseRecordMetric[int]):
    tag: ClassVar[MetricTagT] = "my_custom"
    header: ClassVar[str] = "My Custom Metric"
    unit: ClassVar[MetricUnitT] = MetricUnit.COUNT

    def parse_record(self, record: ParsedResponseRecord, metrics: MetricRecordDict) -> int:
        return 42
```

The `__init_subclass__` hook:

1. Checks if concrete (not abstract)
2. Verifies valid base class
3. Extracts tag
4. Detects value type
5. Calls `MetricRegistry.register_metric()`

No explicit registration required!

### Preventing Registration

For abstract base classes:

```python
class MyAbstractMetric(BaseMetric[int], ABC):
    """Abstract metric - will not register."""

    __is_abstract__ = True  # Prevents registration

    @abstractmethod
    def compute(self):
        ...
```

## Dependency Management

### Declaring Dependencies

Metrics declare dependencies via class variable:

```python
class DerivedMetric(BaseDerivedMetric[float]):
    """Metric that depends on others."""

    tag = "derived"
    required_metrics: ClassVar[set[MetricTagT]] = {
        "metric_a",
        "metric_b",
    }

    async def compute(self, metrics: MetricResultsDict) -> MetricResult:
        self._check_metrics(metrics)  # Validates dependencies present

        value_a = metrics["metric_a"].avg
        value_b = metrics["metric_b"].avg

        return MetricResult(
            tag=self.tag,
            avg=value_a / value_b,
            ...
        )
```

### Dependency Resolution

The registry computes dependency order:

```python
@classmethod
def create_dependency_order(
    cls,
    required_flags: MetricFlags,
    disallowed_flags: MetricFlags,
    *types: MetricType,
) -> list[MetricTagT]:
    """Create a dependency-ordered list of metric tags."""
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

Ensures dependencies computed before dependent metrics.

### Example Dependency Chain

```
RequestLatencyMetric (no deps)
    ↓
OutputTokenCountMetric (no deps)
    ↓
OutputTokenThroughputMetric (depends on both above)
```

Computation order: `[request_latency, output_token_count, output_token_throughput]`

## Metric Flags

### MetricFlags Enum

```python
class MetricFlags(IntFlag):
    """Flags controlling metric behavior."""

    NONE = 0
    HIDE_FROM_CONSOLE = 1 << 0  # Don't show in console export
    HIDE_FROM_DASHBOARD = 1 << 1  # Don't show in dashboard
    ERROR_ONLY = 1 << 2  # Only compute for error records
    INTERNAL = 1 << 3  # Internal metric, not for display
    EXPERIMENTAL = 1 << 4  # Experimental, may change
```

### Flag Usage

```python
class InternalMetric(BaseRecordMetric[int]):
    """Internal metric not shown to users."""

    tag = "internal_counter"
    flags: ClassVar[MetricFlags] = MetricFlags.INTERNAL | MetricFlags.HIDE_FROM_CONSOLE

    def parse_record(self, record: ParsedResponseRecord, metrics: MetricRecordDict) -> int:
        return 1

class ErrorOnlyMetric(BaseRecordMetric[int]):
    """Metric only for error records."""

    tag = "error_code"
    flags: ClassVar[MetricFlags] = MetricFlags.ERROR_ONLY

    def parse_record(self, record: ParsedResponseRecord, metrics: MetricRecordDict) -> int:
        if not record.has_error:
            raise NoMetricValue("Not an error record")
        return record.error.error_code
```

### Filtering by Flags

```python
# Get metrics without INTERNAL flag
metrics = MetricRegistry.tags_applicable_to(
    required_flags=MetricFlags.NONE,
    disallowed_flags=MetricFlags.INTERNAL,
    MetricType.RECORD,
)

# Get error-only metrics
error_metrics = MetricRegistry.tags_applicable_to(
    required_flags=MetricFlags.ERROR_ONLY,
    disallowed_flags=MetricFlags.NONE,
)
```

## Best Practices

### Metric Naming

```python
# Good
class RequestLatencyMetric(BaseRecordMetric[int]):
    tag = "request_latency"
    header = "Request Latency"

# Bad
class Metric1(BaseRecordMetric[int]):
    tag = "m1"
    header = "M1"
```

### Unit Specification

```python
class LatencyMetric(BaseRecordMetric[int]):
    """Always specify unit and display_unit."""

    tag = "latency"
    unit: ClassVar[MetricUnitT] = MetricUnit.NANOSECONDS  # Internal
    display_unit: ClassVar[MetricUnitT] = MetricUnit.MILLISECONDS  # Display
```

### Error Handling

```python
def parse_record(self, record: ParsedResponseRecord, metrics: MetricRecordDict) -> int:
    """Always use NoMetricValue for missing data."""

    self._require_valid_record(record)  # Check validity

    if not record.responses:
        raise NoMetricValue("No responses")  # Not an error, just no value

    return len(record.responses)
```

### Dependencies

```python
class DerivedMetric(BaseDerivedMetric[float]):
    """Always declare dependencies."""

    required_metrics: ClassVar[set[MetricTagT]] = {
        "dependency_1",
        "dependency_2",
    }

    async def compute(self, metrics: MetricResultsDict) -> MetricResult:
        self._check_metrics(metrics)  # Validate dependencies
        # ... compute
```

## Troubleshooting

### Metric Not Registered

**Symptoms:** `MetricTypeError: Metric class with tag 'X' not found`

**Causes:**
1. Metric file not imported
2. Metric class is abstract
3. Tag mismatch

**Solutions:**
- Ensure metric file in `metrics/types/`
- Remove `__is_abstract__` if not abstract
- Check tag spelling

### Circular Dependencies

**Symptoms:** `MetricTypeError: Circular dependency in metrics`

**Causes:**
- Metric A depends on B, B depends on A

**Solutions:**
- Refactor dependencies
- Combine metrics
- Add intermediate metric

### Wrong Value Type

**Symptoms:** Type errors during computation

**Causes:**
- Generic type parameter mismatch
- Return type doesn't match generic

**Solutions:**

```python
# Ensure generic matches return type
class MyMetric(BaseRecordMetric[int]):  # Generic is int
    def parse_record(...) -> int:  # Return type must be int
        return 42  # Correct
        # return 42.0  # Wrong - float!
```

## Key Takeaways

1. **Type-Safe Hierarchy**: BaseMetric with generic type parameter enables compile-time type checking.

2. **Auto-Registration**: `__init_subclass__` hook automatically registers concrete metrics in MetricRegistry.

3. **Three Metric Types**: Record (per-request), Aggregate (accumulated), Derived (computed from others).

4. **Dependency Declaration**: Metrics declare dependencies via `required_metrics` class variable.

5. **Dependency Resolution**: Registry uses topological sort to compute correct computation order.

6. **Metric Discovery**: All metric modules imported at startup to trigger registration.

7. **Flag System**: MetricFlags control visibility, computation conditions, and display behavior.

8. **Value Type Detection**: Automatically inferred from generic type parameter.

9. **NoMetricValue Exception**: Signals missing data without treating as error.

10. **Extensibility**: Easy to add custom metrics via inheritance and auto-registration.

Next: [Chapter 21: Record Metrics](chapter-21-record-metrics.md)
