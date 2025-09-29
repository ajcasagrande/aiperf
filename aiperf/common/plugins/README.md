<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# AIPerf Pluggy Plugin System

A fully featured plugin system for AIPerf request converters using [pluggy](https://pluggy.readthedocs.io/).

## Overview

This plugin system provides a flexible, extensible alternative to the traditional `RequestConverterFactory` approach. It uses pluggy's hook-based architecture to enable dynamic plugin discovery, priority-based selection, and easy extensibility.

## Features

- **🔌 Dynamic Plugin Discovery**: Automatically discover and load plugins from directories
- **⚡ Priority-Based Selection**: Higher priority plugins override lower priority ones
- **🎯 Multi-Endpoint Support**: Single plugins can handle multiple endpoint types
- **🔄 Backward Compatibility**: Works alongside existing factory system
- **🛠️ Easy Extension**: Create custom plugins without modifying core code
- **🧪 Comprehensive Testing**: Full test suite with fixtures and examples
- **📊 CLI Tools**: Built-in commands for plugin management and inspection

## Quick Start

### Using the Hybrid Factory (Recommended)

```python
from aiperf.common.plugins import get_hybrid_factory

# Get a converter that tries pluggy first, falls back to original factory
factory = get_hybrid_factory(prefer_pluggy=True)
converter = factory.create_instance(EndpointType.CHAT)

# Use the converter
result = await converter.format_payload(model_endpoint, turn)
```

### Direct Plugin Manager Usage

```python
from aiperf.common.plugins import get_plugin_manager

manager = get_plugin_manager()
result = await manager.format_payload(
    EndpointType.CHAT, model_endpoint, turn
)
```

### Creating a Custom Plugin

```python
from aiperf.common.plugins import request_converter_plugin
from aiperf.common.enums import EndpointType

@request_converter_plugin(
    endpoint_types=EndpointType.CHAT,
    name="My Custom Chat Plugin",
    priority=200  # Higher than built-in plugins
)
class MyCustomChatPlugin:
    async def format_payload(self, endpoint_type, model_endpoint, turn):
        if endpoint_type != EndpointType.CHAT:
            return None

        return {
            "messages": [{"role": "user", "content": "custom formatting"}],
            "model": model_endpoint.primary_model_name,
            "custom_feature": True
        }
```

## Architecture

### Core Components

1. **Hook Specifications** (`hookspecs.py`)
   - Defines the plugin interface using pluggy hookspecs
   - Ensures type safety and consistent plugin behavior

2. **Plugin Manager** (`manager.py`)
   - Manages plugin registration, discovery, and selection
   - Handles caching and priority resolution

3. **Base Classes** (`base.py`)
   - Provides base classes and decorators for easy plugin development
   - Handles common plugin functionality

4. **Factories** (`factory.py`, `hybrid_factory.py`)
   - Bridge between pluggy system and existing code
   - Provides compatibility layers

### Built-in Plugins

The system includes plugins for all OpenAI endpoint types:

- **ChatPlugin**: Handles chat completion requests
- **CompletionsPlugin**: Handles text completion requests
- **EmbeddingsPlugin**: Handles embedding requests
- **RankingsPlugin**: Handles ranking/reranking requests
- **ResponsesPlugin**: Handles response generation requests

## Plugin Development

### Method 1: Using the Decorator

```python
@request_converter_plugin(
    endpoint_types=[EndpointType.CHAT, EndpointType.COMPLETIONS],
    name="Universal Plugin",
    priority=100,
    auto_register=True
)
class UniversalPlugin:
    async def format_payload(self, endpoint_type, model_endpoint, turn):
        if endpoint_type == EndpointType.CHAT:
            return self._format_chat(model_endpoint, turn)
        elif endpoint_type == EndpointType.COMPLETIONS:
            return self._format_completions(model_endpoint, turn)
        else:
            return None
```

### Method 2: Using Base Class

```python
from aiperf.common.plugins import BaseRequestConverterPlugin

class MyPlugin(BaseRequestConverterPlugin):
    def get_supported_endpoint_types(self):
        return [EndpointType.EMBEDDINGS]

    async def format_payload(self, endpoint_type, model_endpoint, turn):
        if endpoint_type != EndpointType.EMBEDDINGS:
            return None
        return {"model": model_endpoint.primary_model_name, "input": [...]}
```

### Method 3: Manual Registration

```python
from aiperf.common.plugins import register_plugin_instance

class ManualPlugin:
    def get_plugin_name(self):
        return "Manual Plugin"

    def get_supported_endpoint_types(self):
        return [EndpointType.RANKINGS]

    async def format_payload(self, endpoint_type, model_endpoint, turn):
        # Implementation here
        pass

plugin = ManualPlugin()
register_plugin_instance(plugin)
```

## Priority System

Plugins are selected based on priority (higher number = higher priority):

- **200+**: High-priority custom plugins
- **100-199**: Built-in plugins (default: 100)
- **50-99**: Standard third-party plugins
- **0-49**: Low-priority or experimental plugins

## CLI Tools

The plugin system includes CLI tools for management and inspection:

```bash
# List all registered plugins
python -m aiperf.common.plugins.cli list-plugins

# Show supported endpoint types
python -m aiperf.common.plugins.cli list-supported-types --format json

# Test specific endpoint type
python -m aiperf.common.plugins.cli test-endpoint CHAT

# Discover plugins in custom directories
python -m aiperf.common.plugins.cli discover-plugins --plugin-dir /path/to/plugins

# Show detailed system information
python -m aiperf.common.plugins.cli system-info
```

## Testing

The plugin system includes comprehensive tests and fixtures:

```python
import pytest
from aiperf.common.plugins import RequestConverterPluginManager

def test_my_plugin():
    manager = RequestConverterPluginManager()
    plugin = MyPlugin()
    manager.register_plugin(plugin)

    selected = manager.get_plugin_for_endpoint_type(EndpointType.CHAT)
    assert selected == plugin
```

Run the tests:

```bash
pytest tests/plugins/
```

## Examples

See `examples/pluggy_demo.py` for a comprehensive demonstration of:

- Creating custom plugins
- Using the plugin manager
- Working with the hybrid factory
- Plugin discovery and registration
- System inspection and debugging

## Migration Guide

See `docs/pluggy_migration_guide.md` for detailed migration instructions from the traditional factory system.

## API Reference

### Plugin Interface

All plugins must implement these methods:

- `get_supported_endpoint_types() -> list[EndpointType]`
- `get_plugin_name() -> str`
- `get_plugin_priority() -> int` (optional, default: 0)
- `can_handle_endpoint_type(endpoint_type: EndpointType) -> bool` (optional)
- `async format_payload(endpoint_type, model_endpoint, turn) -> dict | None`

### Manager Methods

- `register_plugin(plugin)`: Register a plugin instance
- `register_plugin_class(plugin_class)`: Register a plugin class
- `get_plugin_for_endpoint_type(endpoint_type)`: Get best plugin for endpoint type
- `format_payload(endpoint_type, model_endpoint, turn)`: Format payload using plugins
- `list_plugins()`: List all registered plugins
- `discover_and_load_plugins(dirs)`: Discover plugins in directories

## Performance Considerations

- Plugin discovery happens once per manager instance
- Plugin selection results are cached by endpoint type
- Cache is invalidated when plugins are registered/unregistered
- Minimal overhead for plugin selection after initial discovery

## Error Handling

The system includes comprehensive error handling:

- Graceful fallback when plugins fail
- Detailed error messages and logging
- Plugin validation during registration
- Safe handling of malformed plugins

## Future Enhancements

Planned improvements:

- Configuration-based plugin loading
- Remote plugin repositories
- Plugin dependency management
- Hot reloading capabilities
- Plugin marketplace integration

## Contributing

To contribute to the plugin system:

1. Follow the existing code style and patterns
2. Add comprehensive tests for new features
3. Update documentation and examples
4. Ensure backward compatibility
5. Add appropriate logging and error handling

## License

This plugin system is part of AIPerf and follows the same Apache-2.0 license.
