<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Plugin System

The AIPerf Plugin System provides dynamic plugin discovery, loading, and lifecycle management for AIPerf components. Plugins are automatically discovered from a `plugins/` directory and integrated seamlessly with the AIPerf lifecycle and messaging systems.

## 🚀 Quick Start

```python
from aiperf.lifecycle import PluginManager, load_and_start_plugins

# Method 1: Convenience function (recommended)
plugin_manager = await load_and_start_plugins("./plugins")

# Method 2: Manual management
plugin_manager = PluginManager(plugins_dir="./plugins")
await plugin_manager.initialize()
await plugin_manager.start()  # Discovers and starts all plugins

# Query loaded plugins
plugins = await plugin_manager.send_command("LIST_PLUGINS", plugin_manager.service_id)
print(f"Loaded {plugins['total_plugins']} plugins")

# Stop everything
await plugin_manager.stop()
```

## 📁 Plugin Directory Structure

Plugins are organized in directories under the main `plugins/` folder:

```
plugins/
├── my_plugin/
│   ├── plugin.py           # Main plugin file (required)
│   └── config.yaml         # Optional configuration
├── data_processor/
│   ├── __init__.py
│   ├── processor.py        # Alternative naming
│   └── requirements.txt    # Plugin dependencies
└── monitoring/
    ├── __init__.py
    └── monitor.py          # Another alternative
```

The plugin system looks for Python files in this order:
1. `plugin.py`
2. `{directory_name}.py`
3. `__init__.py`

## 📝 Writing Plugins

### Basic Plugin Structure

Each plugin module must export:
- **`PLUGIN_COMPONENTS`**: List of component classes to instantiate
- **`PLUGIN_METADATA`**: Optional dictionary with plugin information

```python
# plugins/my_plugin/plugin.py
from aiperf.lifecycle import Service, message_handler, background_task

class MyPluginService(Service):
    """Example plugin service."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.data_count = 0

    async def on_init(self):
        await super().on_init()
        self.logger.info("My plugin initialized!")

    @message_handler("PROCESS_DATA")
    async def handle_data(self, message):
        """Process incoming data."""
        self.data_count += 1
        data = message.content

        # Process the data
        result = await self.process_data(data)

        # Send result
        await self.publish_message("DATA_PROCESSED", {
            "result": result,
            "count": self.data_count
        })

    @background_task(interval=30.0)
    async def periodic_cleanup(self):
        """Periodic maintenance task."""
        self.logger.info(f"Cleanup - processed {self.data_count} items")

    async def process_data(self, data):
        """Plugin-specific data processing logic."""
        return f"Processed: {data}"

# Required exports
PLUGIN_COMPONENTS = [MyPluginService]

PLUGIN_METADATA = {
    "name": "My Plugin",
    "version": "1.0.0",
    "description": "Example plugin for data processing",
    "author": "Your Name",
    "provides_services": ["data_processing"],
    "requires_services": []  # Optional dependencies
}
```

### Plugin Types

Plugins can inherit from any AIPerf component:

#### Service Plugin (Full Features)
```python
from aiperf.lifecycle import Service

class MyService(Service):
    # Has lifecycle, messaging, and background tasks
    pass
```

#### Background Tasks Only
```python
from aiperf.lifecycle import BackgroundTasks

class MyWorker(BackgroundTasks):
    # Just background tasks, no messaging or lifecycle
    pass
```

#### Messaging Only
```python
from aiperf.lifecycle import Messaging

class MyHandler(Messaging):
    # Just message handling, no lifecycle or tasks
    pass
```

#### Lifecycle Only
```python
from aiperf.lifecycle import Lifecycle

class MyComponent(Lifecycle):
    # Just init/start/stop lifecycle
    pass
```

## 🔧 Plugin Manager Features

### Automatic Discovery
- Scans `plugins/` directory on startup
- Loads Python modules dynamically
- Instantiates component classes automatically
- Resolves basic dependencies

### Lifecycle Management
- Initializes plugins in dependency order
- Starts all plugins when manager starts
- Stops all plugins when manager stops
- Handles errors gracefully (isolates failing plugins)

### Messaging Integration
- Plugins automatically connect to shared message bus
- Can communicate with each other via messaging
- Main application can communicate with plugins

### Hot Reloading
```python
plugin_manager = PluginManager(plugins_dir="./plugins", auto_reload=True)
# Automatically reloads plugins when files change (every 5 seconds)

# Or manual reload
await plugin_manager.send_command("RELOAD_PLUGINS", plugin_manager.service_id)
```

### Plugin Querying
```python
# List all plugins
plugins = await plugin_manager.send_command("LIST_PLUGINS", plugin_manager.service_id)

# Get detailed plugin status
status = await plugin_manager.send_command("GET_PLUGIN_STATUS", plugin_manager.service_id, {
    "plugin_name": "my_plugin_MyPluginService"
})
```

## 📡 Inter-Plugin Communication

Plugins communicate through the shared message bus:

### Plugin A (Data Producer)
```python
class DataProducer(Service):
    @background_task(interval=5.0)
    async def generate_data(self):
        data = {"timestamp": time.time(), "value": random.randint(1, 100)}
        await self.publish_message("NEW_DATA", data)
```

### Plugin B (Data Consumer)
```python
class DataConsumer(Service):
    @message_handler("NEW_DATA")
    async def handle_new_data(self, message):
        data = message.content
        processed = self.analyze_data(data)

        await self.publish_message("DATA_ANALYZED", {
            "original": data,
            "analysis": processed
        })
```

### Main Application (Coordinator)
```python
class MainApp(Service):
    @message_handler("DATA_ANALYZED")
    async def handle_analysis(self, message):
        analysis = message.content["analysis"]
        self.logger.info(f"Received analysis: {analysis}")
```

## ⚡ Advanced Features

### Plugin Dependencies
```python
PLUGIN_METADATA = {
    "name": "Advanced Plugin",
    "dependencies": ["numpy>=1.20.0", "requests>=2.25.0"],
    "requires_services": ["data_processor", "authentication"],
    "provides_services": ["advanced_analytics"]
}
```

### Error Handling
```python
class RobustPlugin(Service):
    async def on_start(self):
        try:
            await super().on_start()
            await self.setup_external_connections()
        except Exception as e:
            self.logger.error(f"Plugin startup failed: {e}")
            # Plugin manager will mark this plugin as failed
            # but continue with other plugins
            raise
```

### Configuration
```python
# plugins/my_plugin/config.yaml
database:
  host: localhost
  port: 5432
processing:
  batch_size: 100
  timeout: 30

# plugins/my_plugin/plugin.py
import yaml
from pathlib import Path

class ConfigurablePlugin(Service):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Load configuration
        config_file = Path(__file__).parent / "config.yaml"
        if config_file.exists():
            with open(config_file) as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = {}
```

## 🛠️ Best Practices

### 1. Clear Plugin Boundaries
```python
# Good: Clear, single responsibility
class DataValidator(Service):
    @message_handler("VALIDATE_DATA")
    async def validate(self, message):
        # Only does validation
        pass

# Avoid: Too many responsibilities
class EverythingPlugin(Service):
    # Don't make plugins that do everything
    pass
```

### 2. Graceful Error Handling
```python
class RobustPlugin(Service):
    @message_handler("PROCESS_REQUEST")
    async def handle_request(self, message):
        try:
            result = await self.process_safely(message.content)
            await self.publish_message("REQUEST_PROCESSED", result)
        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            await self.publish_message("REQUEST_FAILED", {
                "error": str(e),
                "request_id": message.content.get("id")
            })
```

### 3. Proper Lifecycle Management
```python
class DatabasePlugin(Service):
    async def on_init(self):
        await super().on_init()
        self.db = await self.connect_database()

    async def on_stop(self):
        if self.db:
            await self.db.close()
        await super().on_stop()
```

### 4. Documentation
```python
PLUGIN_METADATA = {
    "name": "Data Processor Plugin",
    "version": "2.1.0",
    "description": "Processes user data with validation and transformation",
    "author": "Data Team <data@company.com>",
    "provides_services": [
        "data_validation",    # Validates incoming data
        "data_transformation" # Transforms data format
    ],
    "requires_services": [
        "authentication"      # Needs auth service
    ]
}
```

## 🚨 Troubleshooting

### Plugin Not Loading
```python
# Check plugin manager logs
plugin_manager.logger.setLevel(logging.DEBUG)

# Query failed plugins
failed = plugin_manager.failed_plugins
for name, error in failed.items():
    print(f"Plugin {name} failed: {error}")
```

### Plugin Not Receiving Messages
```python
# Verify message handler registration
@message_handler("MY_MESSAGE")  # Make sure decorator is applied
async def handle_message(self, message):
    pass

# Check if plugin is started
status = await plugin_manager.send_command("GET_PLUGIN_STATUS",
                                         plugin_manager.service_id,
                                         {"plugin_name": "my_plugin"})
print(f"Plugin state: {status['state']}")
```

### Plugin Communication Issues
```python
# Verify service IDs match
await self.publish_message("TEST", {"data": "test"})

# Check message bus status
print(f"Message bus running: {self.message_bus._running}")
```

## 📚 Examples

See `aiperf/lifecycle/plugin_demo.py` for a comprehensive demonstration of:
- Setting up the plugin manager
- Creating plugins dynamically
- Inter-plugin communication
- Plugin lifecycle management
- Error handling
- Hot reloading

Run the demo:
```bash
python -m aiperf.lifecycle.plugin_demo
```

## 🔮 Future Enhancements

- **Dependency Resolution**: Advanced dependency graph resolution
- **Plugin Marketplace**: Registry for sharing plugins
- **Sandboxing**: Isolated execution environments for plugins
- **API Versioning**: Version compatibility checking
- **Plugin Templates**: CLI tool for generating plugin scaffolds
- **Metrics Integration**: Built-in plugin performance metrics
