# Chapter 48: Plugin Architecture

<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->

## Overview

This chapter explores AIPerf's plugin architecture, including plugin patterns, loading mechanisms, registration, and lifecycle management. Learn how to create modular, distributable extensions.

## Table of Contents

- [Plugin System Overview](#plugin-system-overview)
- [Plugin Patterns](#plugin-patterns)
- [Loading Mechanisms](#loading-mechanisms)
- [Registration](#registration)
- [Lifecycle Management](#lifecycle-management)
- [Distribution](#distribution)
- [Complete Plugin Example](#complete-plugin-example)

---

## Plugin System Overview

### Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    Plugin Architecture                      │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐     ┌──────────────┐                    │
│  │   Plugin     │────▶│   Factory    │                    │
│  │   Loader     │     │  Registry    │                    │
│  └──────────────┘     └──────────────┘                    │
│          │                     │                           │
│          ▼                     ▼                           │
│  ┌──────────────┐     ┌──────────────┐                    │
│  │   Plugin     │     │  Component   │                    │
│  │   Manager    │     │  Instances   │                    │
│  └──────────────┘     └──────────────┘                    │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### Plugin Types

1. **Metric Plugins**: Custom metrics
2. **Dataset Plugins**: Custom dataset loaders
3. **Endpoint Plugins**: Custom endpoint support
4. **Exporter Plugins**: Custom data exporters
5. **Service Plugins**: Custom services

---

## Plugin Patterns

### Pattern 1: Simple Plugin

Single file with automatic registration:

```python
# my_plugin.py
"""
Simple AIPerf plugin for custom metric.

Install: pip install my-aiperf-plugin
Usage: Simply import before running AIPerf
"""

from aiperf.metrics import BaseRecordMetric
from aiperf.common.enums import GenericMetricUnit, MetricFlags


class MyCustomMetric(BaseRecordMetric[float]):
    """Custom metric from plugin"""

    tag = "plugin_metric"
    header = "Plugin Metric"
    unit = GenericMetricUnit.RATIO
    flags = MetricFlags.LARGER_IS_BETTER

    def _parse_record(self, record, record_metrics):
        # Implementation
        return 0.0


# Auto-registered upon import
```

**Usage:**
```python
# Import plugin before running
import my_plugin
from aiperf.cli_runner import run_system_controller

# Plugin metric now available
run_system_controller(user_config, service_config)
```

### Pattern 2: Package Plugin

Structured plugin with setup:

```
my-aiperf-plugin/
├── pyproject.toml
├── README.md
├── src/
│   └── aiperf_my_plugin/
│       ├── __init__.py
│       ├── metrics.py
│       ├── datasets.py
│       └── endpoints.py
└── tests/
    └── test_plugin.py
```

**Plugin Init:**
```python
# src/aiperf_my_plugin/__init__.py
"""My AIPerf Plugin"""

__version__ = "0.1.0"

# Import modules for auto-registration
from . import metrics
from . import datasets
from . import endpoints

__all__ = ["metrics", "datasets", "endpoints"]
```

**Setup:**
```toml
# pyproject.toml
[project]
name = "aiperf-my-plugin"
version = "0.1.0"
dependencies = ["aiperf>=1.0.0"]

[project.entry-points."aiperf.plugins"]
my_plugin = "aiperf_my_plugin"
```

### Pattern 3: Dynamic Plugin

Plugin with configuration:

```python
# dynamic_plugin.py
"""Dynamic plugin with configuration"""

from aiperf.common.config import BaseConfig
from pydantic import Field


class PluginConfig(BaseConfig):
    """Plugin configuration"""
    enabled: bool = Field(default=True)
    threshold: float = Field(default=0.5)
    options: dict = Field(default_factory=dict)


class ConfigurablePlugin:
    """Plugin with configuration support"""

    def __init__(self, config: PluginConfig = None):
        self.config = config or PluginConfig()

    def initialize(self):
        """Initialize with configuration"""
        if not self.config.enabled:
            return

        # Register components based on config
        self._register_metrics()
        self._register_datasets()

    def _register_metrics(self):
        """Register metrics"""
        # Dynamic registration
        pass

    def _register_datasets(self):
        """Register datasets"""
        # Dynamic registration
        pass
```

---

## Loading Mechanisms

### Manual Loading

Explicit import:

```python
# Load plugin manually
import my_aiperf_plugin

# Plugin components now registered
from aiperf.metrics.metric_registry import MetricRegistry
assert "plugin_metric" in MetricRegistry.all_tags()
```

### Entry Points

Using setuptools entry points:

```python
# pyproject.toml
[project.entry-points."aiperf.plugins"]
my_plugin = "my_aiperf_plugin"
```

**Plugin Loader:**
```python
from importlib.metadata import entry_points


def load_plugins():
    """Load all registered plugins"""
    plugins = entry_points(group="aiperf.plugins")

    for plugin in plugins:
        try:
            # Load plugin module
            plugin.load()
            print(f"Loaded plugin: {plugin.name}")
        except Exception as e:
            print(f"Failed to load plugin {plugin.name}: {e}")
```

### Auto-Discovery

Discover plugins in directories:

```python
import importlib.util
from pathlib import Path


def discover_plugins(plugin_dir: Path):
    """Discover and load plugins from directory"""
    for plugin_file in plugin_dir.glob("*.py"):
        if plugin_file.name.startswith("_"):
            continue

        try:
            # Load module
            spec = importlib.util.spec_from_file_location(
                plugin_file.stem,
                plugin_file
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            print(f"Loaded plugin: {plugin_file.name}")
        except Exception as e:
            print(f"Failed to load {plugin_file.name}: {e}")
```

---

## Registration

### Factory Registration

Register with AIPerf factories:

```python
from aiperf.common.factories import CustomDatasetFactory
from aiperf.common.enums import CustomDatasetType


# Extend enum
class PluginDatasetType(CustomDatasetType):
    PLUGIN_FORMAT = "plugin_format"


# Register loader
@CustomDatasetFactory.register(PluginDatasetType.PLUGIN_FORMAT)
class PluginDatasetLoader:
    """Plugin dataset loader"""

    def __init__(self, filename: str):
        self.filename = filename

    def load_dataset(self):
        """Load dataset"""
        pass

    def convert_to_conversations(self, data):
        """Convert to conversations"""
        pass
```

### Metric Registration

Automatic via inheritance:

```python
from aiperf.metrics import BaseRecordMetric


# Automatically registered
class PluginMetric(BaseRecordMetric[float]):
    tag = "plugin_metric"
    header = "Plugin Metric"
    # ...
```

### Multiple Components

Register multiple components:

```python
# plugin_package/__init__.py
"""Plugin with multiple components"""

from .metrics import (
    PluginMetric1,
    PluginMetric2
)
from .datasets import (
    PluginDatasetLoader
)
from .endpoints import (
    PluginRequestConverter,
    PluginResponseExtractor
)

# All auto-registered upon import
```

---

## Lifecycle Management

### Plugin Lifecycle

```
┌──────────┐
│   Load   │ ─── Import/discover plugin
└────┬─────┘
     │
     ▼
┌──────────┐
│   Init   │ ─── Initialize configuration
└────┬─────┘
     │
     ▼
┌──────────┐
│ Register │ ─── Register components
└────┬─────┘
     │
     ▼
┌──────────┐
│  Active  │ ─── Plugin operational
└────┬─────┘
     │
     ▼
┌──────────┐
│ Unload   │ ─── Cleanup (if needed)
└──────────┘
```

### Lifecycle Hooks

```python
class ManagedPlugin:
    """Plugin with lifecycle management"""

    def __init__(self):
        self.initialized = False

    def on_load(self):
        """Called when plugin is loaded"""
        print("Plugin loaded")

    def on_init(self):
        """Called during initialization"""
        if not self.initialized:
            self._initialize_components()
            self.initialized = True

    def on_start(self):
        """Called when benchmark starts"""
        print("Plugin active")

    def on_stop(self):
        """Called when benchmark stops"""
        self._cleanup()

    def _initialize_components(self):
        """Initialize plugin components"""
        pass

    def _cleanup(self):
        """Cleanup resources"""
        pass
```

### Resource Management

```python
from contextlib import contextmanager


class ResourceManagedPlugin:
    """Plugin with resource management"""

    @contextmanager
    def managed_resources(self):
        """Context manager for resources"""
        # Acquire resources
        resources = self._acquire_resources()

        try:
            yield resources
        finally:
            # Release resources
            self._release_resources(resources)

    def _acquire_resources(self):
        """Acquire plugin resources"""
        return {}

    def _release_resources(self, resources):
        """Release plugin resources"""
        pass
```

---

## Distribution

### Package Structure

```
aiperf-my-plugin/
├── LICENSE
├── README.md
├── pyproject.toml
├── src/
│   └── aiperf_my_plugin/
│       ├── __init__.py
│       ├── metrics.py
│       ├── datasets.py
│       ├── endpoints.py
│       └── config.py
├── tests/
│   ├── test_metrics.py
│   ├── test_datasets.py
│   └── test_integration.py
└── docs/
    └── usage.md
```

### PyPI Distribution

**pyproject.toml:**
```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "aiperf-my-plugin"
version = "0.1.0"
description = "Custom plugin for AIPerf"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "aiperf>=1.0.0",
]
keywords = ["aiperf", "benchmark", "plugin"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "Programming Language :: Python :: 3.10",
]

[project.urls]
Homepage = "https://github.com/user/aiperf-my-plugin"
Documentation = "https://github.com/user/aiperf-my-plugin/docs"

[project.entry-points."aiperf.plugins"]
my_plugin = "aiperf_my_plugin"
```

**Install:**
```bash
pip install aiperf-my-plugin
```

### Local Development

```bash
# Install in development mode
cd aiperf-my-plugin
pip install -e .

# Run tests
pytest tests/

# Use plugin
python -c "import aiperf_my_plugin; print('Plugin loaded')"
```

---

## Complete Plugin Example

### Full Featured Plugin

**Structure:**
```
aiperf-analytics-plugin/
├── pyproject.toml
├── README.md
├── src/
│   └── aiperf_analytics/
│       ├── __init__.py
│       ├── config.py
│       ├── metrics.py
│       ├── exporters.py
│       └── services.py
└── tests/
    └── test_plugin.py
```

**Plugin Code:**

```python
# src/aiperf_analytics/__init__.py
"""AIPerf Analytics Plugin"""

__version__ = "0.1.0"

from .config import AnalyticsConfig
from .metrics import AnalyticsMetric
from .exporters import AnalyticsExporter
from .services import AnalyticsService

__all__ = [
    "AnalyticsConfig",
    "AnalyticsMetric",
    "AnalyticsExporter",
    "AnalyticsService"
]
```

```python
# src/aiperf_analytics/config.py
from aiperf.common.config import BaseConfig
from pydantic import Field


class AnalyticsConfig(BaseConfig):
    """Analytics plugin configuration"""
    api_endpoint: str = Field(description="Analytics API endpoint")
    api_key: str = Field(description="API key")
    batch_size: int = Field(default=100)
```

```python
# src/aiperf_analytics/metrics.py
from aiperf.metrics import BaseDerivedMetric
from aiperf.common.enums import GenericMetricUnit


class AnalyticsMetric(BaseDerivedMetric[float]):
    """Custom analytics metric"""

    tag = "analytics_score"
    header = "Analytics Score"
    unit = GenericMetricUnit.RATIO

    required_metrics = {"request_throughput", "error_rate"}

    def _derive(self, metrics):
        throughput = metrics["request_throughput"]
        error_rate = metrics["error_rate"]

        # Custom scoring
        score = throughput * (100 - error_rate) / 100
        return score
```

```python
# src/aiperf_analytics/exporters.py
from aiperf.common.factories import DataExporterFactory
from aiperf.common.enums import DataExporterType
import aiohttp


class CustomExporterType(DataExporterType):
    ANALYTICS = "analytics"


@DataExporterFactory.register(CustomExporterType.ANALYTICS)
class AnalyticsExporter:
    """Export results to analytics service"""

    def __init__(self, exporter_config, config: AnalyticsConfig):
        self.exporter_config = exporter_config
        self.config = config

    async def export(self, results):
        """Export to analytics API"""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.config.api_endpoint,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                json=results.model_dump()
            ) as response:
                response.raise_for_status()
```

**README.md:**
```markdown
# AIPerf Analytics Plugin

Custom analytics plugin for AIPerf.

## Installation

```bash
pip install aiperf-analytics-plugin
```

## Usage

```python
import aiperf_analytics
from aiperf.cli_runner import run_system_controller

# Plugin components automatically registered
# Use analytics metric and exporter
```

## Configuration

Set environment variables:
- `ANALYTICS_API_ENDPOINT`: Analytics API URL
- `ANALYTICS_API_KEY`: API key
```

---

## Key Takeaways

1. **Plugin Patterns**: Simple, package, and dynamic plugins
2. **Loading**: Manual, entry points, and auto-discovery
3. **Registration**: Automatic via factories
4. **Lifecycle**: Load, init, register, active, unload
5. **Distribution**: PyPI packaging
6. **Testing**: Comprehensive test coverage
7. **Documentation**: Clear usage instructions

---

## Navigation

- [Previous Chapter: Chapter 47 - Extending AIPerf](chapter-47-extending-aiperf.md)
- [Next Chapter: Chapter 49 - Deployment Guide](chapter-49-deployment-guide.md)
- [Return to Index](INDEX.md)

---

**Document Information**
- **File**: `/home/anthony/nvidia/projects/aiperf/guidebook/chapter-48-plugin-architecture.md`
- **Purpose**: Guide to creating AIPerf plugins
- **Target Audience**: Plugin developers
- **Related Files**:
  - `/home/anthony/nvidia/projects/aiperf/aiperf/common/factories.py`
  - `/home/anthony/nvidia/projects/aiperf/examples/`
