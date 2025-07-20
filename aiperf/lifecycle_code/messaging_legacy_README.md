<!--
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
-->
# Legacy-Compatible Messaging System

This is a drop-in replacement for the simple messaging system (`messaging.py`) that utilizes the real pub/sub clients from the legacy aiperf infrastructure instead of an in-memory message bus.

## Overview

The legacy-compatible messaging system provides the same simple API as the original messaging system but uses the real ZMQ (ZeroMQ) pub/sub infrastructure from the legacy aiperf codebase. This allows you to:

1. **Use the same simple messaging API** with `Message`, `Command`, and `MessageBus` classes
2. **Leverage real ZMQ communication** with TCP or IPC transport
3. **Integrate with existing aiperf services** that use the legacy messaging infrastructure
4. **Configure communication** via `ServiceConfig` and `UserConfig` as the legacy system expects

## Key Features

- **Drop-in compatibility** with the original messaging API
- **Real ZMQ pub/sub messaging** instead of in-memory queues
- **Service configuration integration** using `ServiceConfig` and `UserConfig`
- **Legacy message type mapping** to bridge simple and complex message hierarchies
- **Event bus proxy support** for proper message routing
- **Command/response patterns** with timeout handling

## Basic Usage

### Simple Message Bus

```python
from aiperf.lifecycle.messaging_legacy import MessageBus, Message, Command
from aiperf.common.config import ServiceConfig
from aiperf.common.enums import CommunicationBackend

# Create service configuration
service_config = ServiceConfig(comm_backend=CommunicationBackend.ZMQ_TCP)

# Create message bus
bus = MessageBus(service_config=service_config)

# Start the bus (initializes ZMQ infrastructure)
await bus.start()

# Subscribe to messages
async def handle_data(message):
    print(f"Received: {message.content}")

bus.subscribe("DATA_MESSAGE", handle_data)

# Publish messages
await bus.publish(Message(
    type="DATA_MESSAGE",
    content="Hello World!",
    sender_id="my_service"
))

# Stop the bus
await bus.stop()
```

### Service Integration

```python
class MyService:
    def __init__(self, service_id: str, service_config: ServiceConfig):
        self.service_id = service_id
        self.message_bus = MessageBus(service_config=service_config)

    async def start(self):
        await self.message_bus.start()

        # Register for targeted messages
        self.message_bus.register_service(
            self.service_id,
            self.handle_targeted_message
        )

        # Subscribe to broadcast messages
        self.message_bus.subscribe("DATA_UPDATE", self.handle_data)

    async def handle_targeted_message(self, message: Message):
        print(f"Targeted message: {message.type}")

    async def handle_data(self, message: Message):
        print(f"Data update: {message.content}")

    async def send_data(self, data):
        await self.message_bus.publish(Message(
            type="DATA_UPDATE",
            content=data,
            sender_id=self.service_id
        ))
```

### Command/Response Pattern

```python
# Send a command and wait for response
command = Command(
    type="GET_STATUS",
    content={"service_id": "target_service"},
    sender_id="my_service",
    target_id="target_service",
    timeout=10.0
)

try:
    response = await bus.send_command(command)
    print(f"Response: {response}")
except asyncio.TimeoutError:
    print("Command timed out")

# Handle commands and send responses
async def handle_status_request(message: Message):
    # Process the command
    status = {"status": "healthy", "uptime": "5 minutes"}

    # Send response
    await bus.send_response(message, status)

bus.subscribe("GET_STATUS", handle_status_request)
```

## Configuration

### Communication Backends

The system supports both ZMQ transport types:

```python
# TCP transport (default)
service_config = ServiceConfig(
    comm_backend=CommunicationBackend.ZMQ_TCP,
    # Uses default TCP ports (5663/5664 for event bus)
)

# IPC transport
service_config = ServiceConfig(
    comm_backend=CommunicationBackend.ZMQ_IPC,
    # Uses IPC sockets in /tmp/aiperf_ipc/
)
```

### Custom Configuration

```python
from aiperf.common.config.zmq_config import ZMQTCPConfig

# Custom TCP configuration
tcp_config = ZMQTCPConfig(
    host="localhost",
    event_bus_proxy_config=ZMQTCPProxyConfig(
        frontend_port=6000,
        backend_port=6001,
    )
)

service_config = ServiceConfig(
    comm_backend=CommunicationBackend.ZMQ_TCP,
    comm_config=tcp_config
)

bus = MessageBus(service_config=service_config)
```

## Message Type Mapping

The system automatically maps simple message types to legacy message types:

### Automatic Mapping

```python
# Simple type -> Legacy type
"DATA_MESSAGE" -> MessageType.TEST
"STATUS" -> MessageType.STATUS
"ERROR" -> MessageType.ERROR
"HEARTBEAT" -> MessageType.HEARTBEAT
"REGISTRATION" -> MessageType.REGISTRATION
"HEALTH_CHECK" -> MessageType.SERVICE_HEALTH

# Commands
"GET_STATUS" -> CommandType.PROFILE_START
"CONFIGURE" -> CommandType.PROFILE_CONFIGURE
"START" -> CommandType.PROFILE_START
"STOP" -> CommandType.PROFILE_STOP
"SHUTDOWN" -> CommandType.SHUTDOWN
```

### Custom Message Types

Unknown message types are automatically mapped:

```python
# If you use "CUSTOM_MESSAGE", it will:
# 1. Try to find a legacy type with matching name
# 2. Fall back to MessageType.TEST for messages
# 3. Fall back to CommandType.PROFILE_START for commands
```

## Architecture

### Legacy Integration

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Simple API    │    │   Legacy API    │    │   ZMQ Network   │
│                 │    │                 │    │                 │
│  Message()      │───▶│ LegacyMessage   │───▶│  TCP/IPC Sockets│
│  Command()      │    │ CommandMessage  │    │  Pub/Sub Proxy  │
│  MessageBus()   │    │ PubClient       │    │  Event Bus      │
│                 │    │ SubClient       │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Message Flow

1. **Simple Message Created**: User creates `Message` or `Command`
2. **Legacy Conversion**: Message converted to legacy format via `to_legacy_message()`
3. **ZMQ Publication**: Legacy message published via `PubClient`
4. **ZMQ Subscription**: Legacy message received via `SubClient`
5. **Simple Conversion**: Legacy message converted back via `from_legacy_message()`
6. **Handler Invocation**: Simple message passed to user handlers

## Differences from Original

| Feature | Original | Legacy-Compatible |
|---------|----------|-------------------|
| Transport | In-memory queue | Real ZMQ TCP/IPC |
| Configuration | None required | ServiceConfig required |
| Message Types | Simple strings | Mapped to legacy types |
| Infrastructure | Standalone | Integrates with legacy system |
| Performance | Fast (in-memory) | Network latency |
| Scalability | Single process | Multi-process/distributed |

## Migration Guide

### From Original Messaging

```python
# OLD - Original messaging
from aiperf.lifecycle.messaging import MessageBus, Message

bus = MessageBus()
await bus.start()

# NEW - Legacy-compatible messaging
from aiperf.lifecycle.messaging_legacy import MessageBus, Message
from aiperf.common.config import ServiceConfig
from aiperf.common.enums import CommunicationBackend

service_config = ServiceConfig(comm_backend=CommunicationBackend.ZMQ_TCP)
bus = MessageBus(service_config=service_config)
await bus.start()
```

### Adding Configuration

The only required change is providing a `ServiceConfig`:

```python
# Minimal configuration change
def get_message_bus():
    service_config = ServiceConfig()  # Uses defaults
    return MessageBus(service_config=service_config)
```

## Requirements

### ZMQ Infrastructure

For the legacy-compatible messaging to work, you need:

1. **ZMQ Event Bus Proxy**: The system expects an event bus proxy to be running
2. **Proper Network Configuration**: TCP ports or IPC paths must be accessible
3. **Service Configuration**: `ServiceConfig` with appropriate communication backend

### Running with Legacy Services

When integrating with existing aiperf services:

```python
# Use the same ServiceConfig as other services
from aiperf.common.config import load_service_config

service_config = load_service_config()  # From environment/config files
bus = MessageBus(service_config=service_config)
```

## Troubleshooting

### Connection Issues

```python
# Check if ZMQ proxy is running
# For TCP: netstat -an | grep 5663
# For IPC: ls /tmp/aiperf_ipc/

# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Message Not Received

```python
# Add delays for subscription establishment
await bus.start()
bus.subscribe("MY_MESSAGE", handler)
await asyncio.sleep(0.5)  # Wait for subscription
await bus.publish(message)
```

### Performance Tuning

```python
# Use IPC for same-machine communication
service_config = ServiceConfig(comm_backend=CommunicationBackend.ZMQ_IPC)

# Use TCP for distributed communication
service_config = ServiceConfig(comm_backend=CommunicationBackend.ZMQ_TCP)
```

## Examples

See `messaging_legacy_demo.py` for complete working examples demonstrating:

- Simple usage patterns
- Service-to-service communication
- Command/response patterns
- Error handling
- Configuration options

## API Reference

The API is identical to the original messaging system - see the docstrings in `messaging_legacy.py` for detailed method documentation.
