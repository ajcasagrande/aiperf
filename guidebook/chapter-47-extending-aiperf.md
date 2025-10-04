<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Chapter 47: Extending AIPerf

## Overview

This chapter covers extension strategies for AIPerf, including extension points, integration patterns, and best practices for adding functionality without modifying core code.

## Table of Contents

- [Extension Philosophy](#extension-philosophy)
- [Extension Points](#extension-points)
- [Service Extensions](#service-extensions)
- [Metric Extensions](#metric-extensions)
- [Dataset Extensions](#dataset-extensions)
- [Endpoint Extensions](#endpoint-extensions)
- [Hook Extensions](#hook-extensions)
- [Best Practices](#best-practices)

---

## Extension Philosophy

### Design Principles

AIPerf is designed for extensibility:

1. **Open/Closed Principle**: Open for extension, closed for modification
2. **Factory Pattern**: Register new implementations without changing core
3. **Protocol-Based**: Define interfaces, not inheritance requirements
4. **Hook System**: Inject behavior at specific points
5. **Configuration-Driven**: Control behavior through config

### Extension vs. Modification

**Prefer Extension:**
- Add new metrics
- Support new endpoints
- Add new dataset formats
- Create custom services
- Inject custom behavior

**Avoid Modification:**
- Changing core AIPerf code
- Modifying existing metrics
- Altering base classes
- Breaking existing APIs

---

## Extension Points

### Factory Extension Points

All factory-based components can be extended:

```python
from aiperf.common.factories import (
    ServiceFactory,        # Custom services
    MetricFactory,        # (via MetricRegistry)
    CustomDatasetFactory, # Custom datasets
    RequestConverterFactory,  # Request converters
    ResponseExtractorFactory, # Response extractors
    DataExporterFactory,  # Data exporters
    ComposerFactory,      # Dataset composers
)
```

### Hook Extension Points

Available hooks for behavior injection:

```python
from aiperf.common.hooks import (
    on_init,              # Initialization
    on_start,             # Service start
    on_stop,              # Service stop
    on_state_change,      # State transitions
    on_message,           # Message received
    on_command,           # Command received
    on_request,           # Request received
    background_task,      # Background tasks
    on_worker_update,     # Worker status
    on_realtime_metrics,  # Realtime metrics
)
```

### Mixin Extension Points

Available mixins for composition:

```python
from aiperf.common.mixins import (
    AIPerfLoggerMixin,        # Logging
    HooksMixin,               # Hook support
    MessageBusMixin,          # Message bus
    WorkerTrackerMixin,       # Worker tracking
    ProgressTrackerMixin,     # Progress tracking
    RealtimeMetricsMixin,     # Realtime metrics
    AIPerfLifecycleMixin,     # Lifecycle management
)
```

---

## Service Extensions

### Custom Service

Create a completely new service:

```python
from aiperf.common.base_service import BaseService
from aiperf.common.factories import ServiceFactory
from aiperf.common.enums import ServiceType
from aiperf.common.config import ServiceConfig, UserConfig


# Define service type (extend enum)
class CustomServiceType(ServiceType):
    ANALYTICS = "analytics"


@ServiceFactory.register(CustomServiceType.ANALYTICS)
class AnalyticsService(BaseService):
    """Custom analytics service"""

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        **kwargs
    ):
        super().__init__(service_config, user_config, **kwargs)
        self.analytics_data = []

    async def _initialize(self):
        """Initialize analytics"""
        self.info("Initializing analytics service")
        await self._connect_analytics_backend()

    async def _start(self):
        """Start collecting analytics"""
        self.info("Starting analytics collection")
        await self._start_collection()

    async def _stop(self):
        """Stop and export analytics"""
        self.info("Stopping analytics, exporting data")
        await self._export_analytics()

    async def _connect_analytics_backend(self):
        """Connect to analytics backend"""
        # Implementation
        pass

    async def _start_collection(self):
        """Begin collecting analytics"""
        # Implementation
        pass

    async def _export_analytics(self):
        """Export analytics data"""
        # Implementation
        pass
```

### Service with Hooks

Add hooks for extensibility:

```python
from aiperf.common.hooks import (
    provides_hooks,
    on_start,
    on_message,
    background_task
)
from aiperf.common.enums import AIPerfHook, MessageType


@provides_hooks(
    AIPerfHook.ON_START,
    AIPerfHook.ON_MESSAGE,
    AIPerfHook.BACKGROUND_TASK
)
class ExtensibleService(BaseService):
    """Service with extension hooks"""

    @on_start
    async def _setup_monitoring(self):
        """Setup monitoring (can be extended)"""
        self.info("Setting up monitoring")

    @on_message(MessageType.STATUS)
    async def _handle_status(self, message):
        """Handle status messages (can be extended)"""
        self.debug(f"Status: {message.status}")

    @background_task(interval=10.0)
    async def _periodic_check(self):
        """Periodic health check (can be extended)"""
        health = await self.check_health()
        self.debug(f"Health: {health}")
```

---

## Metric Extensions

### Custom Metric with Dependencies

```python
from aiperf.metrics import BaseDerivedMetric
from aiperf.common.enums import GenericMetricUnit, MetricFlags
from aiperf.metrics.metric_dicts import MetricResultsDict


class CustomEfficiencyMetric(BaseDerivedMetric[float]):
    """Custom efficiency metric"""

    tag = "custom_efficiency"
    header = "Custom Efficiency Score"
    unit = GenericMetricUnit.RATIO
    display_order = 600
    flags = MetricFlags.LARGER_IS_BETTER

    # Depend on existing metrics
    required_metrics = {
        "request_throughput",
        "request_latency",
        "error_rate"
    }

    def _derive(self, metrics: MetricResultsDict) -> float:
        """Compute custom efficiency score"""
        throughput = metrics["request_throughput"]
        latency_avg = metrics["request_latency"]["avg"]
        error_rate = metrics["error_rate"]

        # Custom formula
        # Higher throughput, lower latency and errors = better
        if latency_avg > 0 and error_rate < 100:
            efficiency = (throughput * 1000) / (latency_avg * (1 + error_rate/100))
            return efficiency
        return 0.0
```

### Conditional Metric

Metric that applies only in specific scenarios:

```python
from aiperf.metrics import BaseRecordMetric
from aiperf.common.enums import MetricFlags, TimeMetricUnit
from aiperf.common.exceptions import NoMetricValue


class ConditionalLatencyMetric(BaseRecordMetric[float]):
    """Latency metric for large responses only"""

    tag = "large_response_latency"
    header = "Large Response Latency"
    unit = TimeMetricUnit.MILLISECONDS
    display_order = 130
    flags = MetricFlags.PRODUCES_TOKENS_ONLY | MetricFlags.SMALLER_IS_BETTER

    LARGE_RESPONSE_THRESHOLD = 1000  # tokens

    def _parse_record(self, record, record_metrics):
        """Compute only for large responses"""
        if record.output_token_count < self.LARGE_RESPONSE_THRESHOLD:
            raise NoMetricValue("Response not large enough")

        latency = (record.request_end_time - record.request_start_time) * 1000
        return latency
```

---

## Dataset Extensions

### Custom Format Support

Add support for proprietary formats:

```python
from aiperf.common.factories import CustomDatasetFactory
from aiperf.common.enums import CustomDatasetType
from aiperf.common.models import Conversation, Turn, Text


# Extend enum
class MyCustomDatasetType(CustomDatasetType):
    PROPRIETARY = "proprietary"


@CustomDatasetFactory.register(MyCustomDatasetType.PROPRIETARY)
class ProprietaryDatasetLoader:
    """Load proprietary dataset format"""

    def __init__(self, filename: str, config: dict = None):
        self.filename = filename
        self.config = config or {}

    def load_dataset(self) -> dict:
        """Load proprietary format"""
        # Custom parsing logic
        data = self._parse_proprietary_format()
        return data

    def convert_to_conversations(self, data: dict) -> list[Conversation]:
        """Convert to AIPerf conversations"""
        conversations = []

        for session_id, records in data.items():
            turns = []
            for record in records:
                turn = Turn(
                    texts=[Text(contents=[record["content"]])],
                    role=record.get("role", "user"),
                    images=[],
                    audios=[]
                )
                turns.append(turn)

            conversation = Conversation(
                session_id=session_id,
                turns=turns
            )
            conversations.append(conversation)

        return conversations

    def _parse_proprietary_format(self):
        """Parse proprietary format"""
        # Custom implementation
        pass
```

---

## Endpoint Extensions

### Custom Protocol Support

Add support for non-OpenAI protocols:

```python
from aiperf.common.factories import (
    RequestConverterFactory,
    ResponseExtractorFactory
)
from aiperf.common.enums import EndpointType


# Extend enum
class CustomEndpointType(EndpointType):
    GRPC_INFERENCE = "grpc_inference"


@RequestConverterFactory.register(CustomEndpointType.GRPC_INFERENCE)
class GRPCRequestConverter:
    """Convert to gRPC request"""

    async def format_payload(self, model_endpoint, turn):
        """Format gRPC payload"""
        return {
            "method": "Infer",
            "params": {
                "model": model_endpoint.primary_model_name,
                "input": turn.texts[0].contents[0]
            }
        }


@ResponseExtractorFactory.register(CustomEndpointType.GRPC_INFERENCE)
class GRPCResponseExtractor:
    """Extract gRPC response"""

    def __init__(self, model_endpoint):
        self.model_endpoint = model_endpoint

    async def extract(self, response):
        """Extract from gRPC response"""
        from aiperf.common.models import ParsedResponseRecord

        return ParsedResponseRecord(
            response_text=response.get("output", ""),
            input_token_count=response.get("input_tokens"),
            output_token_count=response.get("output_tokens"),
            valid=True
        )
```

---

## Hook Extensions

### Custom Hook Implementation

Extend with custom hooks:

```python
from aiperf.common.hooks import (
    AIPerfHook,
    provides_hooks,
    _hook_decorator
)


# Define custom hook type
class MyCustomHook(AIPerfHook):
    ON_DATA_PROCESSED = "@on_data_processed"


# Create decorator for custom hook
def on_data_processed(func):
    """Decorator for data processed hook"""
    return _hook_decorator(MyCustomHook.ON_DATA_PROCESSED, func)


# Use in service
@provides_hooks(MyCustomHook.ON_DATA_PROCESSED)
class DataProcessingService(BaseService):
    """Service with custom hook"""

    @on_data_processed
    async def _log_processed_data(self, data):
        """Called when data is processed"""
        self.info(f"Processed {len(data)} items")

    async def process_data(self, data):
        """Process data and trigger hook"""
        # Process data
        processed = await self._do_processing(data)

        # Trigger custom hook
        await self.run_hooks(
            MyCustomHook.ON_DATA_PROCESSED,
            data=processed
        )

        return processed
```

---

## Best Practices

### 1. Use Factories

Always register with factories:

```python
# Good: Factory registration
@CustomDatasetFactory.register(CustomDatasetType.MY_FORMAT)
class MyDatasetLoader:
    pass

# Bad: Direct instantiation without registration
loader = MyDatasetLoader()  # Not discoverable
```

### 2. Follow Protocols

Implement expected protocols:

```python
from aiperf.common.decorators import implements_protocol
from aiperf.common.protocols import ServiceProtocol

# Good: Explicit protocol implementation
@implements_protocol(ServiceProtocol)
class MyService:
    pass

# Bad: Missing protocol methods
class MyService:
    # Missing required methods
    pass
```

### 3. Document Extensions

Provide clear documentation:

```python
class MyCustomMetric(BaseRecordMetric[float]):
    """
    Custom metric for measuring XYZ.

    This metric computes ABC based on DEF.

    **Applicability:**
    - Only for token-generating endpoints
    - Only for streaming responses

    **Dependencies:**
    - Requires 'request_latency' metric
    - Requires 'output_token_count' metric

    **Formula:**
    value = (output_tokens / latency) * efficiency_factor

    **Example:**
    ```python
    metric = MyCustomMetric()
    value = metric.parse_record(record, record_metrics)
    ```
    """
    pass
```

### 4. Test Extensions

Comprehensive testing:

```python
import pytest


class TestMyExtension:
    """Test suite for custom extension"""

    def test_registration(self):
        """Test factory registration"""
        assert MyCustomType.MY_VALUE in Factory.get_all_class_types()

    def test_creation(self):
        """Test instance creation"""
        instance = Factory.create_instance(MyCustomType.MY_VALUE)
        assert instance is not None

    @pytest.mark.integration
    def test_integration(self):
        """Test in full benchmark"""
        results = run_benchmark_with_extension()
        assert results.success
```

### 5. Handle Errors

Graceful error handling:

```python
from aiperf.common.exceptions import AIPerfError


class MyExtension:
    def process(self, data):
        try:
            return self._process_impl(data)
        except AIPerfError:
            # Re-raise AIPerf errors
            raise
        except Exception as e:
            # Wrap other errors
            raise AIPerfError(f"Extension error: {e}") from e
```

### 6. Version Compatibility

Check AIPerf version:

```python
import aiperf


def check_compatibility():
    """Check AIPerf version compatibility"""
    required_version = "1.0.0"
    current_version = aiperf.__version__

    if current_version < required_version:
        raise RuntimeError(
            f"Requires AIPerf >= {required_version}, "
            f"but found {current_version}"
        )
```

---

## Extension Checklist

- [ ] Use factory registration
- [ ] Implement required protocols
- [ ] Add comprehensive documentation
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Handle errors gracefully
- [ ] Check version compatibility
- [ ] Follow naming conventions
- [ ] Add type hints
- [ ] Log debug information
- [ ] Validate inputs
- [ ] Test edge cases

---

## Key Takeaways

1. **Extension Points**: Use factories, hooks, and protocols
2. **No Core Modification**: Extend, don't modify
3. **Factory Registration**: Register all components
4. **Protocol Implementation**: Follow interfaces
5. **Testing**: Comprehensive test coverage
6. **Documentation**: Clear and complete
7. **Error Handling**: Graceful failures
8. **Version Compatibility**: Check requirements

---

## Navigation

- [Previous Chapter: Chapter 46 - Custom Endpoints](chapter-46-custom-endpoints.md)
- [Next Chapter: Chapter 48 - Plugin Architecture](chapter-48-plugin-architecture.md)
- [Return to Index](INDEX.md)

---

**Document Information**
- **File**: `/home/anthony/nvidia/projects/aiperf/guidebook/chapter-47-extending-aiperf.md`
- **Purpose**: Guide to extending AIPerf functionality
- **Target Audience**: Developers extending AIPerf
- **Related Files**:
  - `/home/anthony/nvidia/projects/aiperf/aiperf/common/factories.py`
  - `/home/anthony/nvidia/projects/aiperf/aiperf/common/hooks.py`
  - `/home/anthony/nvidia/projects/aiperf/aiperf/common/protocols.py`
