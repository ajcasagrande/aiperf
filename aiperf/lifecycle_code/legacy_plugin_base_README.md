<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# Clean Legacy Plugin Base Class

This module provides a dramatically simplified base class for creating plugins that use legacy ZMQ messaging with modern decorator patterns.

## 🎯 The Problem Solved

Previously, creating plugins required complex manual setup:

```python
# OLD WAY - Complex and error-prone
class MyPlugin(LegacyMessagingBase):
    async def start(self):
        await self.start_messaging()  # Manual call required
        # Your logic here

    async def stop(self):
        await self.stop_messaging()  # Manual call required

    async def _handle_targeted_message(self, message):
        # Complex message routing logic
        handlers = self._message_handlers.get(message.type, [])
        # ... lots of boilerplate
```

## 🚀 The Solution: LegacyPlugin Base Class

The new `LegacyPlugin` class abstracts away all complexities:

```python
# NEW WAY - Clean and simple
class MyPlugin(LegacyPlugin):
    async def start(self):
        await super().start()  # Standard inheritance!
        # Your logic here

    async def stop(self):
        # Your cleanup here
        await super().stop()  # Standard inheritance!

    @message_handler("DATA")
    async def handle_data(self, message):
        # Just use decorators - everything else is automatic!
```

## ✨ Key Benefits

### 1. **Standard Inheritance Chains**
- Use `super().start()` and `super().stop()` like normal Python classes
- No more manual method calls or complex setup
- Works with multiple inheritance patterns

### 2. **Automatic Everything**
- **Decorator Discovery**: Automatically finds `@message_handler` and `@command_handler` methods
- **ZMQ Setup**: Handles all communication infrastructure setup
- **Subscription Management**: Automatically subscribes to decorated message types
- **Error Handling**: Built-in error handling and logging

### 3. **Simple API**
- `await self.publish(type, content)` - Send messages
- `await self.send_command(type, target)` - Send commands
- `self.logger` - Pre-configured logger
- `self.is_started` - Check plugin state

### 4. **Focus on Business Logic**
- No messaging infrastructure code needed
- No manual subscription setup
- No complex message routing
- Just your decorators and business logic

## 📚 Complete Usage Guide

### Basic Plugin Structure

```python
from aiperf.lifecycle.legacy_plugin_base import LegacyPlugin
from aiperf.lifecycle.decorators import message_handler, command_handler

class MyPlugin(LegacyPlugin):
    def __init__(self, service_config=None, **kwargs):
        super().__init__(
            service_id="my_plugin",  # Unique ID for this plugin
            service_config=service_config,  # ZMQ configuration
            **kwargs
        )
        # Your initialization here
        self.data = []

    async def start(self):
        """Standard lifecycle method - always call super() first!"""
        await super().start()  # Sets up all messaging infrastructure

        # Your initialization logic here
        self.data.clear()
        self.logger.info("Plugin ready!")

    async def stop(self):
        """Standard lifecycle method - call super() last!"""
        # Your cleanup logic here
        self.logger.info("Plugin shutting down")

        await super().stop()  # Cleans up messaging infrastructure

    @message_handler("PROCESS_DATA")
    async def handle_data(self, message):
        """Handle broadcast messages - just use the decorator!"""
        data = message.content
        self.data.append(data)

        # Publish result
        await self.publish("DATA_PROCESSED", {
            "result": f"Processed {data}",
            "count": len(self.data)
        })

    @command_handler("GET_STATUS")
    async def get_status(self, message):
        """Handle commands - return response directly!"""
        return {
            "items_processed": len(self.data),
            "status": "healthy",
            "plugin_id": self.service_id
        }
```

### Message Handling

```python
@message_handler("DATA_UPDATE", "SYSTEM_EVENT")  # Multiple types
async def handle_events(self, message):
    """Handle multiple message types with one handler."""
    if message.type == "DATA_UPDATE":
        await self.process_data_update(message.content)
    elif message.type == "SYSTEM_EVENT":
        await self.handle_system_event(message.content)

@message_handler("USER_ACTION")
def handle_user_sync(self, message):  # Can be sync or async
    """Synchronous handlers work too."""
    self.logger.info(f"User action: {message.content}")
```

### Command Handling

```python
@command_handler("GET_DATA")
async def get_data(self, message):
    """Commands expect responses."""
    request = message.content or {}
    limit = request.get("limit", 10)

    return {
        "data": self.data[-limit:],
        "total": len(self.data),
        "limit": limit
    }

@command_handler("CLEAR_DATA")
async def clear_data(self, message):
    """Commands can modify state and return results."""
    old_count = len(self.data)
    self.data.clear()

    return {
        "cleared": old_count,
        "new_count": 0
    }
```

### Publishing Messages

```python
# Broadcast message
await self.publish("EVENT_OCCURRED", {
    "event": "data_processed",
    "timestamp": time.time()
})

# Targeted message
await self.publish("PRIVATE_MESSAGE", {
    "data": "secret"
}, target_id="specific_service")
```

### Sending Commands

```python
# Send command and wait for response
try:
    response = await self.send_command(
        "GET_STATUS",
        "other_service",
        content={"detailed": True},
        timeout=5.0
    )
    self.logger.info(f"Other service status: {response}")

except asyncio.TimeoutError:
    self.logger.error("Command timed out")
```

## 🔧 Advanced Features

### Multiple Inheritance

```python
class DatabaseMixin:
    async def start(self):
        await super().start()
        self.db = await connect_database()

    async def stop(self):
        await self.db.close()
        await super().stop()

class MyPlugin(LegacyPlugin, DatabaseMixin):
    async def start(self):
        await super().start()  # Calls both parents correctly
        # Your logic here
```

### Custom Configuration

```python
class ConfigurablePlugin(LegacyPlugin):
    def __init__(self, config_file=None, **kwargs):
        super().__init__(**kwargs)

        # Load configuration
        if config_file:
            with open(config_file) as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = self.get_default_config()

    def get_default_config(self):
        return {
            "batch_size": 100,
            "timeout": 30,
            "retries": 3
        }
```

### Error Handling

```python
@message_handler("RISKY_OPERATION")
async def handle_risky_operation(self, message):
    """Built-in error handling logs errors automatically."""
    # If this raises an exception, it's automatically logged
    # and doesn't crash the plugin
    result = await self.risky_operation(message.content)
    await self.publish("OPERATION_RESULT", result)

@command_handler("RISKY_COMMAND")
async def handle_risky_command(self, message):
    """Command errors are sent back as error responses."""
    # If this raises an exception, an error response is automatically
    # sent back to the sender with the error details
    return await self.another_risky_operation(message.content)
```

### Plugin Information

```python
# Check if plugin is running
if self.is_started:
    await self.publish("STATUS_UPDATE", {"status": "active"})

# Get handler information
info = self.get_handler_info()
self.logger.info(f"Registered handlers: {info}")
```

## 🎭 Integration with Plugin System

### Plugin Factory

```python
from aiperf.lifecycle.plugins import PluginInstance, PluginMetadata

def create_my_plugin(service_config=None):
    """Factory function for plugin creation."""
    component = MyPlugin(service_config=service_config)

    metadata = PluginMetadata(
        name="my_plugin",
        version="1.0.0",
        description="My awesome plugin",
        author="Me",
    )

    return PluginInstance(
        name="my_plugin",
        component=component,
        metadata=metadata,
        module_path=__file__,
    )
```

### Plugin Module Structure

```python
# plugins/my_plugin/plugin.py
from aiperf.lifecycle.legacy_plugin_base import LegacyPlugin
from aiperf.lifecycle.decorators import message_handler, command_handler

class MyAwesomePlugin(LegacyPlugin):
    # Plugin implementation here
    pass

# Required exports for plugin system
PLUGIN_COMPONENTS = [MyAwesomePlugin]

PLUGIN_METADATA = {
    "name": "My Awesome Plugin",
    "version": "1.0.0",
    "description": "Does awesome things",
    "author": "Plugin Developer",
}
```

## 🏗️ Architecture

### How It Works

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Your Plugin   │    │  LegacyPlugin   │    │ Legacy ZMQ      │
│                 │    │   Base Class    │    │ Infrastructure  │
│ @message_handler│───▶│                 │───▶│                 │
│ @command_handler│    │ • Auto-discovery│    │ • MessageBus    │
│ start()/stop()  │    │ • Setup/cleanup │    │ • PubClient     │
│ Business logic  │    │ • Error handling│    │ • SubClient     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Key Components

1. **LegacyPlugin Base Class**
   - Handles all messaging infrastructure
   - Discovers decorators automatically
   - Provides clean lifecycle methods
   - Manages subscriptions and routing

2. **Decorator Integration**
   - `@message_handler` for broadcast messages
   - `@command_handler` for request/response
   - Automatic registration and routing

3. **Legacy ZMQ Integration**
   - Uses real `MessageBus` with ZMQ transport
   - Compatible with existing aiperf services
   - Supports TCP and IPC communication

## 📊 Comparison: Old vs New

| Feature | Old LegacyMessagingBase | New LegacyPlugin |
|---------|-------------------------|------------------|
| **Setup** | Manual `start_messaging()` | Automatic via `super().start()` |
| **Cleanup** | Manual `stop_messaging()` | Automatic via `super().stop()` |
| **Decorators** | Manual discovery and setup | Automatic discovery |
| **Error Handling** | Manual implementation | Built-in with logging |
| **Message Routing** | Complex manual routing | Automatic routing |
| **Inheritance** | Custom method names | Standard Python patterns |
| **Code Lines** | ~50+ lines of boilerplate | ~5 lines of business logic |
| **Bugs** | Many opportunities | Fewer opportunities |
| **Learning Curve** | Steep | Gentle |

## 🚀 Migration Guide

### From LegacyMessagingBase

```python
# OLD
class OldPlugin(LegacyMessagingBase):
    async def start(self):
        await self.start_messaging()  # Remove this
        # Your logic

    async def stop(self):
        await self.stop_messaging()  # Remove this

# NEW
class NewPlugin(LegacyPlugin):
    async def start(self):
        await super().start()  # Change to super()
        # Your logic

    async def stop(self):
        # Your logic
        await super().stop()  # Move super() to end
```

### Update Imports

```python
# OLD
from aiperf.lifecycle.messaging_legacy_plugin_demo import LegacyMessagingBase

# NEW
from aiperf.lifecycle.legacy_plugin_base import LegacyPlugin
```

### Update Plugin Factories

```python
# OLD
return PluginInstance(plugin=component, metadata=metadata)  # Wrong constructor

# NEW
return PluginInstance(
    name="plugin_name",
    component=component,
    metadata=metadata,
    module_path=__file__,
)
```

## 🎯 Best Practices

### 1. Always Call Super()
```python
async def start(self):
    await super().start()  # Always first
    # Your initialization

async def stop(self):
    # Your cleanup first
    await super().stop()  # Always last
```

### 2. Use Descriptive Service IDs
```python
# Good
super().__init__(service_id="data_processor_v2")

# Bad
super().__init__(service_id="plugin1")
```

### 3. Handle Errors Gracefully
```python
@command_handler("RISKY_OPERATION")
async def handle_risky(self, message):
    try:
        result = await self.risky_operation()
        return {"success": True, "result": result}
    except Exception as e:
        # Return error info instead of raising
        return {"success": False, "error": str(e)}
```

### 4. Use Appropriate Message Types
```python
# For notifications/events
@message_handler("DATA_UPDATED")
async def handle_notification(self, message):
    # No response expected
    pass

# For requests/queries
@command_handler("GET_DATA")
async def handle_request(self, message):
    # Response expected
    return {"data": self.data}
```

## 🏃 Running the Demo

```bash
# Clean demo with new base class
python -m aiperf.lifecycle.messaging_legacy_plugin_demo_clean

# Comparison with old approach
python -m aiperf.lifecycle.messaging_legacy_plugin_demo
```

The new demo shows how much simpler and cleaner plugin development becomes with the `LegacyPlugin` base class!
