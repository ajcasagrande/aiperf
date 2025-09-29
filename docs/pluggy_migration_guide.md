<!--
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
-->
# Pluggy Plugin System Migration Guide

This guide explains how to migrate from the traditional `RequestConverterFactory` system to the new pluggy-based plugin system in AIPerf.

## Overview

The new pluggy-based system provides:

- **Dynamic plugin discovery**: Plugins are automatically discovered and loaded
- **Priority-based selection**: Higher priority plugins override lower priority ones
- **Multiple endpoint support**: Single plugins can handle multiple endpoint types
- **Backward compatibility**: Works alongside the existing factory system
- **Extensibility**: Easy to create custom plugins without modifying core code

## Key Components

### 1. Plugin Manager
- `RequestConverterPluginManager`: Manages plugin registration and discovery
- Handles plugin lifecycle and caching
- Provides plugin selection based on endpoint type and priority

### 2. Hook Specifications
- `RequestConverterHookSpec`: Defines the interface that plugins must implement
- Uses pluggy's hookspec system for type safety and validation

### 3. Factories
- `PluggyRequestConverterFactory`: Pure pluggy-based factory
- `HybridRequestConverterFactory`: Combines pluggy and traditional factory systems

## Migration Paths

### Path 1: Hybrid Approach (Recommended)

Use the hybrid factory to gradually migrate while maintaining compatibility:

```python
from aiperf.common.plugins import get_hybrid_factory

# Replace this:
from aiperf.common.factories import RequestConverterFactory
converter = RequestConverterFactory.create_instance(endpoint_type)

# With this:
factory = get_hybrid_factory(prefer_pluggy=True)
converter = factory.create_instance(endpoint_type)
```

### Path 2: Pure Pluggy

For new code, use the pure pluggy system:

```python
from aiperf.common.plugins import get_plugin_manager

manager = get_plugin_manager()
result = await manager.format_payload(endpoint_type, model_endpoint, turn)
```

### Path 3: Custom Plugins

Create custom plugins to extend functionality:

```python
from aiperf.common.plugins import request_converter_plugin
from aiperf.common.enums import EndpointType

@request_converter_plugin(
    endpoint_types=EndpointType.CHAT,
    name="My Custom Plugin",
    priority=100
)
class MyCustomPlugin:
    async def format_payload(self, endpoint_type, model_endpoint, turn):
        # Custom logic here
        return {"custom": True, "messages": [...]}
```

## Converting Existing Converters

### Before (Traditional Factory)

```python
from aiperf.common.factories import RequestConverterFactory
from aiperf.common.enums import EndpointType

@RequestConverterFactory.register(EndpointType.CHAT)
class OpenAIChatConverter:
    async def format_payload(self, model_endpoint, turn):
        # Implementation
        pass
```

### After (Pluggy Plugin)

```python
from aiperf.common.plugins import request_converter_plugin
from aiperf.common.enums import EndpointType

@request_converter_plugin(
    endpoint_types=EndpointType.CHAT,
    name="OpenAI Chat Plugin",
    priority=100
)
class OpenAIChatPlugin:
    async def format_payload(self, endpoint_type, model_endpoint, turn):
        if endpoint_type != EndpointType.CHAT:
            return None
        # Implementation
        pass
```

### Key Differences

1. **Method Signature**: The pluggy version includes `endpoint_type` as the first parameter
2. **Return Value**: Plugins should return `None` for unsupported endpoint types
3. **Registration**: Uses decorator instead of factory registration
4. **Priority**: Explicit priority system for conflict resolution

## Plugin Development Guide

### Basic Plugin Structure

```python
from aiperf.common.plugins import request_converter_plugin

@request_converter_plugin(
    endpoint_types=[EndpointType.CHAT, EndpointType.COMPLETIONS],
    name="Multi-Endpoint Plugin",
    priority=50,
    auto_register=True  # Automatically register when imported
)
class MultiEndpointPlugin:
    async def format_payload(self, endpoint_type, model_endpoint, turn):
        if endpoint_type == EndpointType.CHAT:
            return self._format_chat(model_endpoint, turn)
        elif endpoint_type == EndpointType.COMPLETIONS:
            return self._format_completions(model_endpoint, turn)
        else:
            return None

    def _format_chat(self, model_endpoint, turn):
        # Chat-specific formatting
        pass

    def _format_completions(self, model_endpoint, turn):
        # Completions-specific formatting
        pass
```

### Using Base Classes

```python
from aiperf.common.plugins import BaseRequestConverterPlugin

class MyPlugin(BaseRequestConverterPlugin):
    def get_supported_endpoint_types(self):
        return [EndpointType.EMBEDDINGS]

    async def format_payload(self, endpoint_type, model_endpoint, turn):
        if endpoint_type != EndpointType.EMBEDDINGS:
            return None
        # Implementation
        pass
```

### Manual Registration

```python
from aiperf.common.plugins import register_plugin_instance

plugin = MyPlugin()
register_plugin_instance(plugin)
```

## Priority System

Plugins are selected based on priority (higher number = higher priority):

- **Built-in plugins**: Priority 100
- **Third-party plugins**: Priority 50 (default)
- **Custom plugins**: Any priority you choose

```python
@request_converter_plugin(
    endpoint_types=EndpointType.CHAT,
    priority=200  # Overrides built-in plugins
)
class HighPriorityPlugin:
    # Implementation
    pass
```

## Testing Plugins

### Unit Testing

```python
import pytest
from aiperf.common.plugins import RequestConverterPluginManager

@pytest.fixture
def plugin_manager():
    return RequestConverterPluginManager()

def test_my_plugin(plugin_manager):
    plugin = MyPlugin()
    plugin_manager.register_plugin(plugin)

    selected = plugin_manager.get_plugin_for_endpoint_type(EndpointType.CHAT)
    assert selected == plugin
```

### Integration Testing

```python
async def test_format_payload():
    manager = get_plugin_manager()
    manager.register_plugin(MyPlugin())

    result = await manager.format_payload(
        EndpointType.CHAT, model_endpoint, turn
    )

    assert result is not None
    assert "messages" in result
```

## CLI Tools

Use the built-in CLI tools to inspect the plugin system:

```bash
# List all plugins
python -m aiperf.common.plugins.cli list-plugins

# Show supported endpoint types
python -m aiperf.common.plugins.cli list-supported-types

# Test specific endpoint type
python -m aiperf.common.plugins.cli test-endpoint CHAT

# Show system information
python -m aiperf.common.plugins.cli system-info
```

## Best Practices

### 1. Plugin Naming
- Use descriptive names that indicate functionality
- Include the system/protocol name (e.g., "OpenAI Chat Plugin")

### 2. Error Handling
- Always handle unsupported endpoint types gracefully
- Return `None` for unsupported types instead of raising exceptions
- Log warnings for configuration issues

### 3. Priority Management
- Use consistent priority ranges:
  - 200+: High-priority custom plugins
  - 100-199: Built-in plugins
  - 50-99: Standard third-party plugins
  - 0-49: Low-priority or experimental plugins

### 4. Testing
- Test all supported endpoint types
- Test error conditions and edge cases
- Use fixtures for common test data

### 5. Documentation
- Document supported endpoint types
- Provide examples of expected input/output
- Document any special configuration requirements

## Troubleshooting

### Plugin Not Found
- Check that the plugin is properly registered
- Verify endpoint type matching
- Check priority conflicts

### Import Errors
- Ensure all dependencies are available
- Check for circular imports
- Verify plugin module structure

### Priority Issues
- Use CLI tools to inspect plugin priorities
- Check for conflicts between plugins
- Consider adjusting priority values

## Performance Considerations

### Plugin Discovery
- Discovery happens once per manager instance
- Results are cached for performance
- Consider manual registration for critical paths

### Plugin Selection
- First selection is cached by endpoint type
- Cache is invalidated when plugins change
- Minimize plugin registration/unregistration in hot paths

## Backward Compatibility

The pluggy system is designed to work alongside the existing factory system:

1. **Hybrid Factory**: Tries pluggy first, falls back to traditional factory
2. **Existing Code**: No changes required for existing code
3. **Gradual Migration**: Migrate components one at a time
4. **Testing**: Both systems can be tested in parallel

## Future Enhancements

Planned improvements to the plugin system:

1. **Configuration-based plugins**: Load plugins from configuration files
2. **Remote plugins**: Support for loading plugins from remote sources
3. **Plugin dependencies**: Declare and resolve plugin dependencies
4. **Hot reloading**: Reload plugins without restarting the application
5. **Plugin marketplace**: Centralized repository for community plugins

## Getting Help

- Check the example code in `examples/pluggy_demo.py`
- Use the CLI tools for system inspection
- Review the test suite for usage patterns
- Consult the API documentation for detailed method signatures
