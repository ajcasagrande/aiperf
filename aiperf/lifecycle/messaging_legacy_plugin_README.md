<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# Legacy Messaging Plugin Demo

This demonstration shows how to create plugins that use the legacy-compatible messaging system with message decorators.

## What This Demo Shows

### 🔌 **Plugin Architecture**
- **`LegacyMessagingBase`**: Base class that integrates legacy ZMQ messaging with decorators
- **Plugin lifecycle management**: Start/stop messaging with proper cleanup
- **Decorator discovery**: Automatically finds `@message_handler` and `@command_handler` methods
- **Plugin factory pattern**: Shows how to create proper `PluginInstance` objects

### 📨 **Message Decorators in Action**
```python
@message_handler("DATA_INCOMING", "RAW_DATA")
async def handle_data_incoming(self, message: Message) -> None:
    # Handle broadcast messages of these types

@command_handler("GET_STATUS")
async def get_status(self, message: Message) -> dict:
    # Handle commands and return responses
```

### 🔄 **Real ZMQ Communication**
- Uses the legacy `CommunicationFactory` and `ServiceConfig`
- Real TCP/IPC transport instead of in-memory queues
- Integration with event bus proxies
- Cross-plugin communication via ZMQ

### 🎯 **Practical Examples**

#### DataProcessorPlugin
- **Processes incoming data** using `@message_handler("DATA_INCOMING")`
- **Responds to status requests** using `@command_handler("GET_STATUS")`
- **Publishes results** to other plugins/services
- **Maintains data cache** with automatic cleanup

#### MonitoringPlugin
- **Monitors system activity** using `@message_handler("DATA_PROCESSED", "DATA_ACK")`
- **Provides system health checks** using `@command_handler("GET_SYSTEM_HEALTH")`
- **Cross-plugin communication** by sending commands to other plugins
- **Activity logging** with configurable limits

## Running the Demo

### Prerequisites
Make sure you have a proper aiperf development environment with:
- Python virtual environment activated
- All aiperf dependencies installed
- Access to ZMQ libraries

### Basic Run
```bash
# From the project root
source .venv/bin/activate
python -m aiperf.lifecycle.messaging_legacy_plugin_demo
```

### Expected Output
The demo will show:
1. **Plugin startup** with messaging initialization
2. **Basic messaging** - sending data for processing
3. **Command/response patterns** - getting plugin status
4. **Cross-plugin communication** - health checks between plugins
5. **Activity monitoring** - viewing logged activities
6. **Clean shutdown** of all plugins

### Sample Output
```
=== Legacy Messaging Plugin Demo ===
--- Starting plugins ---
INFO:__main__:Plugin data_processor_plugin messaging started
INFO:__main__:DataProcessorPlugin started and ready
INFO:__main__:Plugin monitoring_plugin messaging started
INFO:__main__:MonitoringPlugin started and monitoring

--- Demo: Basic messaging ---
INFO:__main__:Processing incoming data: item1
INFO:__main__:Monitored activity: DATA_PROCESSED from data_processor_plugin
INFO:__main__:Processing incoming data: item2
INFO:__main__:Monitored activity: DATA_ACK from data_processor_plugin

--- Demo: Command/Response ---
INFO:__main__:Status requested by demo_orchestrator: {'service_id': 'data_processor_plugin', ...}
INFO:__main__:Data processor status: {'service_id': 'data_processor_plugin', 'status': 'healthy', ...}

--- Demo: Cross-plugin communication ---
INFO:__main__:System health: healthy

--- Demo: Activity monitoring ---
INFO:__main__:Recent activities: 6
  - DATA_ACK from data_processor_plugin
  - DATA_PROCESSED from data_processor_plugin
  - DATA_ACK from data_processor_plugin

=== Demo Complete ===
```

## Architecture

### Message Flow
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Demo Script    │    │  ZMQ Event Bus  │    │   Plugins       │
│                 │    │                 │    │                 │
│ publish() ────────────> Proxy ──────────────> @message_handler │
│ send_command()  │    │                 │    │ @command_handler│
│  <─────────────────── Proxy <─────────────── publish_message()│
│                 │    │                 │    │ send_response() │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Plugin Integration
1. **Inherit from `LegacyMessagingBase`**: Gets messaging capabilities
2. **Use decorators**: `@message_handler` and `@command_handler`
3. **Implement lifecycle**: `start()` calls `start_messaging()`
4. **Use plugin factory**: Create `PluginInstance` with metadata

### Key Classes

#### `LegacyMessagingBase`
- Integrates legacy messaging with decorator patterns
- Provides `publish_message()` and `send_command()` convenience methods
- Automatically discovers and registers decorated handlers
- Manages ZMQ subscriptions and targeted message handling

#### `DataProcessorPlugin`
- Example of data processing with messaging
- Shows async message handlers
- Demonstrates command handlers with return values
- Cache management and cleanup

#### `MonitoringPlugin`
- Example of system monitoring
- Cross-plugin communication patterns
- Activity logging and health checking
- Multiple message type handlers

## Integration with Legacy Services

The plugins can communicate with existing aiperf services because:

1. **Same transport**: Uses ZMQ TCP/IPC like legacy services
2. **Same configuration**: Uses `ServiceConfig` and communication factories
3. **Compatible message types**: Maps to legacy `MessageType` and `CommandType` enums
4. **Event bus integration**: Uses the same proxy infrastructure

## Extending the Demo

### Adding New Plugins
```python
class MyPlugin(LegacyMessagingBase):
    def __init__(self, service_config=None, **kwargs):
        super().__init__(service_id="my_plugin", service_config=service_config, **kwargs)

    @message_handler("MY_MESSAGE_TYPE")
    async def handle_my_message(self, message: Message):
        # Handle the message
        pass

    @command_handler("MY_COMMAND")
    async def handle_my_command(self, message: Message) -> dict:
        # Handle command and return response
        return {"status": "ok"}
```

### Adding New Message Types
Simply use new type strings in decorators:
```python
@message_handler("CUSTOM_EVENT", "SPECIAL_DATA")
async def handle_custom(self, message: Message):
    # The legacy system will map unknown types automatically
    pass
```

### Integration with Real Services
```python
# Use the same ServiceConfig as other aiperf services
from aiperf.common.config import load_service_config

service_config = load_service_config()  # From environment/config
plugin = MyPlugin(service_config=service_config)
```

This allows plugins to participate in the same messaging infrastructure as existing aiperf services.
