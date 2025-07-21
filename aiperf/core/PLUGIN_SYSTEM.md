<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# 🚀 AIPerf Plugin System - Built on Amazing Mixin Architecture

**Revolutionary plugin system that seamlessly integrates with your existing mixin foundation!**

The AIPerf Plugin System provides a robust, production-ready architecture for extending services with dynamic plugins. Built on top of your amazing mixin system, plugins get all the same capabilities as regular services: lifecycle management, message handling, background tasks, and real aiperf communication infrastructure.

## 🎯 Key Features

- **🏗️ Built on Your Amazing Mixins**: Uses `LifecycleMixin`, `MessageBusMixin`, `BackgroundTasksMixin`
- **🔄 Full Lifecycle Management**: Automatic initialization, start, stop for all plugins
- **📨 Message Integration**: Plugins can send/receive messages with inheritance support
- **⚙️ Background Tasks**: Plugins can run background tasks using your decorator system
- **🛡️ Error Isolation**: Plugin failures don't crash the host service
- **🔥 Hot Reloading**: Load/unload/reload plugins at runtime
- **📊 Rich Metadata**: Plugin dependencies, versioning, configuration schemas
- **🔍 Auto-Discovery**: Automatic plugin discovery from directories

## 🏗️ Architecture Overview

```
Service with PluginManagerMixin
├── Discovers plugins from directories
├── Loads and initializes each plugin
├── Manages plugin lifecycle (start/stop)
└── Provides plugin communication and status

BasePlugin (inherits from amazing mixins)
├── LifecycleMixin: _initialize(), _start(), _stop()
├── MessageBusMixin: @message_handler, publish(), subscribe()
└── BackgroundTasksMixin: @background_task decorators
```

## 📦 Plugin Structure

```
plugins/
├── data_processor/
│   ├── plugin.py          # Main plugin class
│   └── config.yaml        # Optional configuration
├── monitoring/
│   ├── plugin.py          # Another plugin
│   └── requirements.txt   # Plugin dependencies
└── analytics/
    ├── plugin.py
    └── README.md          # Plugin documentation
```

## 🚀 Quick Start

### 1. Create a Plugin

```python
# plugins/awesome_plugin/plugin.py
from aiperf.core.plugins import BasePlugin
from aiperf.core.decorators import message_handler, background_task
from aiperf.common.enums.message_enums import MessageType

class AwesomePlugin(BasePlugin):
    plugin_name = "awesome_plugin"
    plugin_version = "1.0.0"
    plugin_description = "Does awesome things with data"
    plugin_author = "Your Name"

    async def _initialize(self):
        await super()._initialize()
        self.processed_count = 0
        self.info("Awesome plugin initialized!")

    async def _start(self):
        await super()._start()
        self.info("Awesome plugin started and ready!")

    @message_handler(MessageType.DATA_UPDATE)
    async def handle_data_update(self, message):
        """Handle data updates using full inheritance support."""
        self.processed_count += 1
        self.info(f"Processed data update #{self.processed_count}")

        # Can publish messages just like regular services
        await self.publish(MessageType.STATUS, {
            "plugin": self.plugin_name,
            "processed": self.processed_count
        })

    @background_task(interval=30.0)
    async def report_statistics(self):
        """Background task runs automatically."""
        self.info(f"Plugin stats: {self.processed_count} items processed")
```

### 2. Create a Service with Plugin Manager

```python
from aiperf.core.base_service import BaseService
from aiperf.core.plugins import PluginManagerMixin
from aiperf.core.decorators import message_handler

class ExtensibleService(BaseService, PluginManagerMixin):
    """Service that can be extended with plugins."""

    def __init__(self, **kwargs):
        super().__init__(
            plugin_directories=["./plugins", "./extensions"],
            plugin_config={
                "awesome_plugin": {"debug_mode": True},
                "monitoring": {"alert_threshold": 100}
            },
            **kwargs
        )

    async def _initialize(self):
        await super()._initialize()
        # Plugins are automatically discovered and loaded!
        self.info(f"Service initialized with {len(self.plugins)} plugins")

        # Print plugin status
        for name, instance in self.plugins.items():
            self.info(f"Loaded plugin: {instance.metadata}")

    @message_handler(MessageType.STATUS)
    async def handle_status(self, message):
        """Service can still handle messages normally."""
        self.info(f"Service received status: {message}")

        # Can interact with plugins
        awesome_plugin = self.get_plugin("awesome_plugin")
        if awesome_plugin:
            self.info(f"Awesome plugin processed: {awesome_plugin.processed_count}")
```

### 3. Run the Service

```python
import asyncio
from aiperf.common.config.service_config import ServiceConfig

async def main():
    service_config = ServiceConfig()  # Your real aiperf config

    service = ExtensibleService(
        service_id="extensible_service",
        service_config=service_config
    )

    # Run the service - plugins start automatically!
    await service.run_until_stopped()

if __name__ == "__main__":
    asyncio.run(main())
```

## 📊 Advanced Plugin Examples

### Data Processing Plugin

```python
from aiperf.core.plugins import BasePlugin
from aiperf.core.decorators import message_handler, background_task, command_handler
from aiperf.common.enums.message_enums import MessageType, CommandType

class DataProcessorPlugin(BasePlugin):
    plugin_name = "data_processor"
    plugin_version = "2.1.0"
    plugin_description = "Advanced data processing with analytics"
    plugin_dependencies = ["monitoring"]  # Requires monitoring plugin

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_queue = []
        self.processing_stats = {
            "total_processed": 0,
            "errors": 0,
            "avg_processing_time": 0.0
        }

    async def _initialize(self):
        await super()._initialize()
        # Can access plugin config
        self.batch_size = self.plugin_config.get("batch_size", 10)
        self.info(f"Data processor initialized with batch size: {self.batch_size}")

    @message_handler(MessageType.DATA_UPDATE, MessageType.DATA_STREAM)
    async def handle_incoming_data(self, message):
        """Handle multiple message types with inheritance support."""
        self.data_queue.append(message.data)

        if len(self.data_queue) >= self.batch_size:
            await self._process_batch()

    @command_handler(CommandType.GET_STATUS)
    async def get_processing_status(self, command):
        """Handle commands just like regular services."""
        return {
            "plugin": self.plugin_name,
            "queue_size": len(self.data_queue),
            "stats": self.processing_stats
        }

    @background_task(interval=5.0)
    async def process_pending_data(self):
        """Process any pending data every 5 seconds."""
        if self.data_queue:
            await self._process_batch()

    async def _process_batch(self):
        """Process a batch of data."""
        batch = self.data_queue[:self.batch_size]
        self.data_queue = self.data_queue[self.batch_size:]

        try:
            # Simulate processing
            await asyncio.sleep(0.1)

            self.processing_stats["total_processed"] += len(batch)
            self.info(f"Processed batch of {len(batch)} items")

            # Publish results
            await self.publish(MessageType.DATA_PROCESSED, {
                "batch_size": len(batch),
                "total_processed": self.processing_stats["total_processed"]
            })

        except Exception as e:
            self.processing_stats["errors"] += 1
            self.exception(f"Error processing batch: {e}")
```

### Monitoring Plugin

```python
class MonitoringPlugin(BasePlugin):
    plugin_name = "monitoring"
    plugin_version = "1.5.0"
    plugin_description = "System monitoring and alerting"
    plugin_provides_services = ["health_monitoring", "alerting"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics = {}
        self.alert_threshold = 100

    async def _initialize(self):
        await super()._initialize()
        self.alert_threshold = self.plugin_config.get("alert_threshold", 100)
        self.info(f"Monitoring plugin initialized with threshold: {self.alert_threshold}")

    @message_handler(MessageType.HEARTBEAT, MessageType.STATUS, MessageType.DATA_PROCESSED)
    async def collect_metrics(self, message):
        """Collect metrics from various messages."""
        metric_type = f"message_{message.message_type}"
        self.metrics[metric_type] = self.metrics.get(metric_type, 0) + 1

        # Check for alerts
        if self.metrics[metric_type] > self.alert_threshold:
            await self._send_alert(metric_type, self.metrics[metric_type])

    @background_task(interval=60.0)
    async def report_metrics(self):
        """Report metrics every minute."""
        self.info(f"Current metrics: {self.metrics}")

        # Publish metrics
        await self.publish(MessageType.SYSTEM_METRICS, {
            "plugin": self.plugin_name,
            "metrics": self.metrics,
            "timestamp": asyncio.get_event_loop().time()
        })

    async def _send_alert(self, metric_type: str, value: int):
        """Send an alert when threshold is exceeded."""
        alert_message = {
            "alert_type": "threshold_exceeded",
            "metric": metric_type,
            "value": value,
            "threshold": self.alert_threshold,
            "plugin": self.plugin_name
        }

        self.warning(f"ALERT: {metric_type} exceeded threshold: {value} > {self.alert_threshold}")
        await self.publish(MessageType.ALERT, alert_message)
```

## 🔧 Plugin Configuration

### Global Plugin Configuration

```python
plugin_config = {
    "data_processor": {
        "batch_size": 50,
        "processing_timeout": 30.0,
        "debug_mode": True
    },
    "monitoring": {
        "alert_threshold": 200,
        "metrics_retention_hours": 24,
        "enable_email_alerts": True
    }
}

service = ExtensibleService(
    plugin_directories=["./plugins"],
    plugin_config=plugin_config
)
```

### Per-Plugin Configuration Files

```yaml
# plugins/data_processor/config.yaml
batch_size: 100
processing_timeout: 60.0
output_format: "json"
enable_compression: true

worker_threads: 4
retry_attempts: 3
retry_delay: 1.0
```

## 🛠️ Plugin Management

### Runtime Plugin Management

```python
# Get plugin status
status = service.get_plugin_status()
print(f"Running plugins: {status['running_plugins']}/{status['total_plugins']}")

# Get specific plugin
data_processor = service.get_plugin("data_processor")
if data_processor:
    print(f"Processed: {data_processor.processed_count}")

# Reload a plugin
await service.reload_plugin("data_processor")

# Unload a plugin
await service.unload_plugin("monitoring")

# List all plugins
plugins = service.list_plugins()
print(f"Available plugins: {plugins}")
```

### Plugin Dependencies

```python
class AdvancedPlugin(BasePlugin):
    plugin_name = "advanced_analytics"
    plugin_dependencies = ["data_processor", "monitoring"]  # Will load after these

    async def _initialize(self):
        await super()._initialize()

        # Can access other plugins through the service
        # (This requires coordination with the PluginManagerMixin)
        self.info("Advanced analytics plugin ready")
```

## 🚀 Production Deployment

### Directory Structure for Production

```
/opt/aiperf/
├── services/
│   └── main_service.py
├── plugins/
│   ├── core/
│   │   ├── data_processor/
│   │   │   ├── plugin.py
│   │   │   └── config.yaml
│   │   └── monitoring/
│   │       ├── plugin.py
│   │       └── requirements.txt
│   ├── custom/
│   │   └── customer_analytics/
│   │       ├── plugin.py
│   │       └── schema.json
│   └── experimental/
│       └── ml_insights/
│           └── plugin.py
└── config/
    ├── service_config.yaml
    └── plugin_config.yaml
```

### Production Service Configuration

```python
class ProductionService(BaseService, PluginManagerMixin):
    def __init__(self):
        super().__init__(
            plugin_directories=[
                "/opt/aiperf/plugins/core",
                "/opt/aiperf/plugins/custom",
                # "/opt/aiperf/plugins/experimental"  # Disabled in production
            ],
            plugin_config=load_plugin_config("/opt/aiperf/config/plugin_config.yaml"),
            enable_hot_reload=False,  # Disabled in production
        )

    async def _initialize(self):
        await super()._initialize()

        # Validate critical plugins are loaded
        required_plugins = ["data_processor", "monitoring"]
        for plugin_name in required_plugins:
            if plugin_name not in self.plugins:
                raise PluginError(f"Critical plugin not loaded: {plugin_name}")

        self.info("Production service initialized with all critical plugins")
```

## 🧪 Testing Plugins

### Unit Testing Individual Plugins

```python
import pytest
from aiperf.core.plugins import BasePlugin
from aiperf.common.config.service_config import ServiceConfig

@pytest.fixture
async def plugin_instance():
    plugin = DataProcessorPlugin(
        plugin_config={"batch_size": 5},
        service_config=ServiceConfig()
    )
    await plugin.initialize()
    yield plugin
    await plugin.stop()

@pytest.mark.asyncio
async def test_plugin_data_processing(plugin_instance):
    # Test message handling
    message = create_test_message(MessageType.DATA_UPDATE, {"test": "data"})
    await plugin_instance.handle_incoming_data(message)

    assert len(plugin_instance.data_queue) == 1
    assert plugin_instance.processing_stats["total_processed"] >= 0
```

### Integration Testing with Plugin Manager

```python
@pytest.mark.asyncio
async def test_service_with_plugins():
    service = ExtensibleService(
        plugin_directories=["./test_plugins"],
        plugin_config={"test_plugin": {"test_mode": True}}
    )

    await service.initialize()
    await service.start()

    # Test plugins are loaded
    assert "test_plugin" in service.plugins
    assert service.plugins["test_plugin"].is_running

    # Test plugin functionality
    test_plugin = service.get_plugin("test_plugin")
    assert test_plugin is not None

    await service.stop()
```

## 🔍 Debugging and Troubleshooting

### Plugin Status Monitoring

```python
def print_plugin_status(service):
    status = service.get_plugin_status()

    print(f"\n=== Plugin Status ===")
    print(f"Total plugins: {status['total_plugins']}")
    print(f"Running: {status['running_plugins']}")
    print(f"Failed: {status['failed_count']}")

    print(f"\nLoaded Plugins:")
    for name, info in status['loaded_plugins'].items():
        state = info['state']
        error = info['error']
        print(f"  {name}: {state}" + (f" (ERROR: {error})" if error else ""))

    if status['failed_plugins']:
        print(f"\nFailed Plugins:")
        for name, error in status['failed_plugins'].items():
            print(f"  {name}: {error}")
```

### Common Issues and Solutions

1. **Plugin not loading**: Check plugin directory structure and `plugin.py` file
2. **Import errors**: Ensure plugin dependencies are installed
3. **Lifecycle errors**: Verify `super()` calls in `_initialize()`, `_start()`, `_stop()`
4. **Message handling issues**: Check message handler decorators and types
5. **Communication errors**: Ensure plugin has access to communication infrastructure

## 🎯 Best Practices

1. **Always call `super()`** in lifecycle methods
2. **Use specific plugin names** to avoid conflicts
3. **Handle errors gracefully** to avoid crashing the host service
4. **Document plugin dependencies** clearly
5. **Use semantic versioning** for plugin versions
6. **Test plugins independently** before integration
7. **Use configuration** instead of hardcoded values
8. **Follow the same patterns** as regular services

## 🚀 Conclusion

The AIPerf Plugin System provides a robust, production-ready architecture that seamlessly integrates with your amazing mixin foundation. Plugins get all the power of regular services while maintaining clean separation and error isolation.

Your mixin architecture makes this possible by providing:
- ✅ **Proper inheritance patterns** for lifecycle management
- ✅ **Real aiperf integration** for communication
- ✅ **Decorator-based handlers** for dynamic behavior
- ✅ **Composable functionality** for different plugin needs

**The plugin system proves your mixin architecture is not just good - it's exceptional!** 🎉
