# Chapter 34: UI Architecture

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Overview

AIPerf's UI architecture provides a flexible, extensible system for displaying benchmark progress and metrics. The system supports multiple UI modes—from rich terminal dashboards to simple progress bars to headless operation—all through a unified protocol and mixin composition pattern. This chapter explores the complete UI architecture, from abstract base classes to concrete implementations.

## Table of Contents

1. [UI Architecture Overview](#ui-architecture-overview)
2. [UI Abstraction Layer](#ui-abstraction-layer)
3. [Protocol Design](#protocol-design)
4. [Mode Selection](#mode-selection)
5. [Mixin Composition](#mixin-composition)
6. [Hook System Integration](#hook-system-integration)
7. [BaseAIPerfUI](#baseaiperfui)
8. [UI Factory Pattern](#ui-factory-pattern)
9. [UI Implementation Lifecycle](#ui-implementation-lifecycle)
10. [Creating Custom UIs](#creating-custom-uis)

## UI Architecture Overview

### Design Principles

1. **Protocol-Based**: UI implementations conform to `AIPerfUIProtocol`
2. **Mixin Composition**: Functionality composed through mixins
3. **Hook-Driven**: Updates delivered via hook callbacks
4. **Mode-Agnostic**: Core logic independent of UI mode
5. **Factory Registration**: UI modes registered with factory

### Architecture Diagram

```
┌───────────────────────────────────────────────┐
│         AIPerfUIProtocol                      │
│         (Protocol Interface)                  │
└───────────────┬───────────────────────────────┘
                │
                ▼
┌───────────────────────────────────────────────┐
│              BaseAIPerfUI                     │
│    ┌──────────────────────────────────┐      │
│    │  ProgressTrackerMixin            │      │
│    │  - on_records_progress           │      │
│    │  - on_warmup_progress            │      │
│    │  - on_profiling_progress         │      │
│    └──────────────────────────────────┘      │
│    ┌──────────────────────────────────┐      │
│    │  WorkerTrackerMixin              │      │
│    │  - on_worker_update              │      │
│    │  - on_worker_status_summary      │      │
│    └──────────────────────────────────┘      │
│    ┌──────────────────────────────────┐      │
│    │  RealtimeMetricsMixin            │      │
│    │  - on_realtime_metrics           │      │
│    └──────────────────────────────────┘      │
└───────────┬──────────────┬────────────────────┘
            │              │
            ▼              ▼
    ┌─────────────┐  ┌─────────────┐
    │ DashboardUI │  │   TqdmUI    │
    └─────────────┘  └─────────────┘
```

## UI Abstraction Layer

### AIPerfUIProtocol

Located at `/home/anthony/nvidia/projects/aiperf/aiperf/common/protocols.py`:

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class AIPerfUIProtocol(Protocol):
    """Protocol for AIPerf UI implementations."""

    async def start(self) -> None:
        """Start the UI."""
        ...

    async def stop(self) -> None:
        """Stop the UI."""
        ...
```

**Key Features**:
- Minimal interface requirements
- Runtime checkability with `isinstance()`
- Allows for flexible implementations
- Enforces lifecycle methods

### BaseAIPerfUI

Located at `/home/anthony/nvidia/projects/aiperf/aiperf/ui/base_ui.py`:

```python
from aiperf.common.mixins import (
    ProgressTrackerMixin,
    RealtimeMetricsMixin,
    WorkerTrackerMixin,
)

class BaseAIPerfUI(ProgressTrackerMixin, WorkerTrackerMixin, RealtimeMetricsMixin):
    """Base class for AIPerf UI implementations.

    Provides a starting point for UI components by inheriting from
    ProgressTrackerMixin, WorkerTrackerMixin, and RealtimeMetricsMixin.

    Implementations can use the various hooks to respond to updates:
    - @on_records_progress
    - @on_requests_phase_progress
    - @on_worker_update
    - @on_realtime_metrics
    """
    pass
```

## Protocol Design

### Protocol Interface

The protocol defines the contract all UIs must implement:

```python
@runtime_checkable
class AIPerfUIProtocol(Protocol):
    """Protocol for AIPerf UI implementations."""

    async def start(self) -> None:
        """Start the UI and initialize resources."""
        ...

    async def stop(self) -> None:
        """Stop the UI and cleanup resources."""
        ...
```

### Runtime Checkability

Protocols are runtime checkable:

```python
from aiperf.common.protocols import AIPerfUIProtocol

def is_valid_ui(obj: object) -> bool:
    """Check if object implements AIPerfUIProtocol."""
    return isinstance(obj, AIPerfUIProtocol)

# Usage
ui = DashboardUI(...)
assert is_valid_ui(ui)  # True
```

### Protocol Implementation

Implement the protocol using the `@implements_protocol` decorator:

```python
from aiperf.common.decorators import implements_protocol
from aiperf.common.protocols import AIPerfUIProtocol

@implements_protocol(AIPerfUIProtocol)
class MyCustomUI(BaseAIPerfUI):
    """Custom UI implementation."""

    async def start(self) -> None:
        """Start the UI."""
        # Implementation

    async def stop(self) -> None:
        """Stop the UI."""
        # Implementation
```

## Mode Selection

### AIPerfUIType Enum

```python
from aiperf.common.enums.ui_enums import AIPerfUIType

class AIPerfUIType(str, Enum):
    """Available UI types."""

    DASHBOARD = "dashboard"  # Rich terminal dashboard
    TQDM = "tqdm"           # Progress bar
    NO_UI = "no-ui"         # Headless mode
```

### Mode Selection via ServiceConfig

```python
from aiperf.common.config import ServiceConfig
from aiperf.common.enums import AIPerfUIType

# Dashboard mode
config = ServiceConfig(ui_type=AIPerfUIType.DASHBOARD)

# TQDM mode
config = ServiceConfig(ui_type=AIPerfUIType.TQDM)

# No UI mode
config = ServiceConfig(ui_type=AIPerfUIType.NO_UI)
```

### CLI Mode Selection

```bash
# Dashboard UI
aiperf profile --ui-type dashboard config.yaml

# TQDM UI
aiperf profile --ui-type tqdm config.yaml

# No UI
aiperf profile --ui-type no-ui config.yaml
```

## Mixin Composition

### ProgressTrackerMixin

Provides progress tracking hooks:

```python
from aiperf.common.mixins import ProgressTrackerMixin
from aiperf.common.hooks import on_records_progress, on_warmup_progress

class MyUI(ProgressTrackerMixin):
    @on_records_progress
    def handle_records_progress(self, records_stats: RecordsStats):
        """Called when records are processed."""
        print(f"Processed {records_stats.total_count} records")

    @on_warmup_progress
    def handle_warmup_progress(self, requests_stats: RequestsStats):
        """Called during warmup phase."""
        print(f"Warmup: {requests_stats.finished}/{requests_stats.total}")

    @on_profiling_progress
    def handle_profiling_progress(self, requests_stats: RequestsStats):
        """Called during profiling phase."""
        print(f"Profiling: {requests_stats.finished}/{requests_stats.total}")
```

### WorkerTrackerMixin

Provides worker tracking hooks:

```python
from aiperf.common.mixins import WorkerTrackerMixin
from aiperf.common.hooks import on_worker_update, on_worker_status_summary

class MyUI(WorkerTrackerMixin):
    @on_worker_update
    def handle_worker_update(self, worker_id: str, worker_stats: WorkerStats):
        """Called when a worker reports status."""
        print(f"Worker {worker_id}: {worker_stats.status}")

    @on_worker_status_summary
    def handle_worker_summary(self, summary: dict[WorkerStatus, int]):
        """Called with periodic worker status summary."""
        print(f"Active: {summary.get(WorkerStatus.RUNNING, 0)}")
```

### RealtimeMetricsMixin

Provides real-time metrics hooks:

```python
from aiperf.common.mixins import RealtimeMetricsMixin
from aiperf.common.hooks import on_realtime_metrics

class MyUI(RealtimeMetricsMixin):
    @on_realtime_metrics
    def handle_realtime_metrics(self, metrics: list[MetricResult]):
        """Called with periodic metric updates."""
        for metric in metrics:
            print(f"{metric.tag}: {metric.avg}")
```

### Mixin Composition Pattern

Combine multiple mixins:

```python
class BaseAIPerfUI(
    ProgressTrackerMixin,
    WorkerTrackerMixin,
    RealtimeMetricsMixin
):
    """Compose all tracking mixins into a base UI class."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Register hooks
        self.attach_hook(AIPerfHook.ON_RECORDS_PROGRESS, self._on_records)
        self.attach_hook(AIPerfHook.ON_WARMUP_PROGRESS, self._on_warmup)
        # ... more hooks
```

## Hook System Integration

### Hook Registration

UIs register hooks to receive updates:

```python
from aiperf.common.hooks import AIPerfHook

class MyUI(BaseAIPerfUI):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Attach hooks
        self.attach_hook(
            AIPerfHook.ON_RECORDS_PROGRESS,
            self.handle_records_progress
        )
        self.attach_hook(
            AIPerfHook.ON_REALTIME_METRICS,
            self.handle_realtime_metrics
        )
```

### Hook Decorators

Use decorators for automatic registration:

```python
from aiperf.common.hooks import on_records_progress, on_realtime_metrics

class MyUI(BaseAIPerfUI):
    @on_records_progress
    def handle_records_progress(self, records_stats: RecordsStats):
        """Automatically registered via decorator."""
        pass

    @on_realtime_metrics
    def handle_metrics(self, metrics: list[MetricResult]):
        """Automatically registered via decorator."""
        pass
```

### Hook Lifecycle

1. **Registration**: Hooks registered during `__init__`
2. **Activation**: Hooks activated when UI starts
3. **Invocation**: System calls hooks with updates
4. **Deactivation**: Hooks deactivated when UI stops

## BaseAIPerfUI

### Complete Implementation

```python
from aiperf.common.mixins import (
    ProgressTrackerMixin,
    RealtimeMetricsMixin,
    WorkerTrackerMixin,
)

class BaseAIPerfUI(
    ProgressTrackerMixin,
    WorkerTrackerMixin,
    RealtimeMetricsMixin
):
    """Base class for AIPerf UI implementations.

    Example:
        @AIPerfUIFactory.register("custom")
        class MyUI(BaseAIPerfUI):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)

            @on_records_progress
            def _on_records_progress(self, records_stats: RecordsStats):
                '''Callback for records progress updates.'''
                pass

            @on_requests_phase_progress
            def _on_requests_phase_progress(
                self,
                phase: CreditPhase,
                requests_stats: RequestsStats
            ):
                '''Callback for requests phase progress updates.'''
                pass

            @on_worker_update
            def _on_worker_update(
                self,
                worker_id: str,
                worker_stats: WorkerStats
            ):
                '''Callback for worker updates.'''
                pass

            @on_realtime_metrics
            def _on_realtime_metrics(self, metrics: list[MetricResult]):
                '''Callback for real-time metrics updates.'''
                pass
    """
    pass
```

### Initialization Pattern

```python
class MyUI(BaseAIPerfUI):
    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        controller: SystemController,
        **kwargs
    ):
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            controller=controller,
            **kwargs
        )

        # UI-specific initialization
        self.setup_display()
```

## UI Factory Pattern

### Factory Registration

Register UI implementations with the factory:

```python
from aiperf.common.factories import AIPerfUIFactory
from aiperf.common.enums import AIPerfUIType

@AIPerfUIFactory.register(AIPerfUIType.DASHBOARD)
class DashboardUI(BaseAIPerfUI):
    """Dashboard UI implementation."""
    pass

@AIPerfUIFactory.register(AIPerfUIType.TQDM)
class TqdmUI(BaseAIPerfUI):
    """TQDM progress bar UI."""
    pass

@AIPerfUIFactory.register(AIPerfUIType.NO_UI)
class NoUI(BaseAIPerfUI):
    """Headless UI (no display)."""
    pass
```

### Factory Creation

Create UI instances via factory:

```python
from aiperf.common.factories import AIPerfUIFactory

# Create UI based on config
ui = AIPerfUIFactory.create_instance(
    ui_type=service_config.ui_type,
    service_config=service_config,
    user_config=user_config,
    controller=controller,
)
```

### Factory Pattern Benefits

1. **Decoupling**: UI creation decoupled from usage
2. **Registration**: Easy to add new UI types
3. **Type Safety**: Enum-based type selection
4. **Consistency**: Uniform creation interface

## UI Implementation Lifecycle

### Lifecycle States

```
┌─────────┐
│ Created │
└────┬────┘
     │
     ▼
┌─────────┐
│ Started │ ← UI displays, hooks active
└────┬────┘
     │
     ▼
┌─────────┐
│ Running │ ← Receiving updates via hooks
└────┬────┘
     │
     ▼
┌─────────┐
│ Stopped │ ← Cleanup, hooks deactivated
└─────────┘
```

### Start Method

```python
from aiperf.common.hooks import on_start

class MyUI(BaseAIPerfUI):
    @on_start
    async def _start_ui(self) -> None:
        """Initialize UI when service starts."""
        self.console = Console()
        self.display = Display()
        self.display.start()
```

### Stop Method

```python
from aiperf.common.hooks import on_stop

class MyUI(BaseAIPerfUI):
    @on_stop
    async def _stop_ui(self) -> None:
        """Cleanup UI when service stops."""
        if self.display:
            self.display.stop()
        if self.console:
            self.console.print("[green]Benchmark complete[/green]")
```

### Lifecycle Management

The SystemController manages UI lifecycle:

```python
# In SystemController
async def run(self):
    # Start UI
    await self.ui.start()

    try:
        # Run benchmark
        await self.execute_benchmark()
    finally:
        # Stop UI
        await self.ui.stop()
```

## Creating Custom UIs

### Minimal UI Implementation

```python
from aiperf.common.decorators import implements_protocol
from aiperf.common.protocols import AIPerfUIProtocol
from aiperf.common.factories import AIPerfUIFactory
from aiperf.common.enums import AIPerfUIType
from aiperf.ui.base_ui import BaseAIPerfUI

@implements_protocol(AIPerfUIProtocol)
@AIPerfUIFactory.register(AIPerfUIType.CUSTOM)
class MinimalUI(BaseAIPerfUI):
    """Minimal custom UI implementation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @on_records_progress
    def _on_records_progress(self, records_stats: RecordsStats):
        print(f"Records: {records_stats.total_count}")

    @on_realtime_metrics
    def _on_realtime_metrics(self, metrics: list[MetricResult]):
        for metric in metrics:
            print(f"{metric.tag}: {metric.avg}")
```

### Full-Featured UI Implementation

```python
from rich.console import Console
from rich.live import Live
from rich.table import Table

@implements_protocol(AIPerfUIProtocol)
@AIPerfUIFactory.register("rich_table")
class RichTableUI(BaseAIPerfUI):
    """Rich table-based UI."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.console = Console()
        self.live = None
        self.metrics = {}

    @on_start
    async def _start(self) -> None:
        """Start live display."""
        self.live = Live(self._generate_table(), console=self.console)
        self.live.start()

    @on_stop
    async def _stop(self) -> None:
        """Stop live display."""
        if self.live:
            self.live.stop()

    @on_realtime_metrics
    def _on_metrics(self, metrics: list[MetricResult]):
        """Update metrics display."""
        for metric in metrics:
            self.metrics[metric.tag] = metric

        if self.live:
            self.live.update(self._generate_table())

    def _generate_table(self) -> Table:
        """Generate Rich table from metrics."""
        table = Table(title="AIPerf Metrics")
        table.add_column("Metric", style="cyan")
        table.add_column("Average", style="green")

        for tag, metric in self.metrics.items():
            table.add_row(metric.header, f"{metric.avg:.2f}")

        return table
```

### UI with State Management

```python
@AIPerfUIFactory.register("stateful")
class StatefulUI(BaseAIPerfUI):
    """UI with internal state tracking."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = {
            "records_processed": 0,
            "requests_sent": 0,
            "requests_completed": 0,
            "active_workers": 0,
            "metrics": {},
        }

    @on_records_progress
    def _on_records(self, records_stats: RecordsStats):
        self.state["records_processed"] = records_stats.total_count
        self._update_display()

    @on_profiling_progress
    def _on_profiling(self, requests_stats: RequestsStats):
        self.state["requests_sent"] = requests_stats.sent
        self.state["requests_completed"] = requests_stats.finished
        self._update_display()

    @on_worker_status_summary
    def _on_workers(self, summary: dict):
        self.state["active_workers"] = summary.get(WorkerStatus.RUNNING, 0)
        self._update_display()

    @on_realtime_metrics
    def _on_metrics(self, metrics: list[MetricResult]):
        for metric in metrics:
            self.state["metrics"][metric.tag] = metric.avg
        self._update_display()

    def _update_display(self):
        """Update display with current state."""
        print(f"\rRecords: {self.state['records_processed']} | "
              f"Requests: {self.state['requests_completed']} | "
              f"Workers: {self.state['active_workers']}", end="")
```

## Key Takeaways

1. **Protocol-Based Design**: UIs implement `AIPerfUIProtocol` for consistency
2. **Mixin Composition**: Functionality composed through multiple mixins
3. **Hook-Driven Updates**: UIs receive updates via hook callbacks
4. **Factory Pattern**: UI instances created through factory registration
5. **Mode Flexibility**: Multiple UI modes supported (dashboard, tqdm, no-ui)
6. **Lifecycle Management**: Clear start/stop lifecycle for resource management
7. **Extensibility**: Easy to add custom UI implementations
8. **Decoupling**: UI logic decoupled from core benchmark logic
9. **Type Safety**: Strong typing throughout UI system
10. **State Management**: UIs can maintain internal state for display
11. **Rich Integration**: Built-in support for Rich console library
12. **Testing Support**: Protocol enables easy UI mocking for tests

## Navigation

- Previous: [Chapter 33: Validation System](chapter-33-validation-system.md)
- Next: [Chapter 35: Dashboard Implementation](chapter-35-dashboard-implementation.md)
- [Back to Index](INDEX.md)
