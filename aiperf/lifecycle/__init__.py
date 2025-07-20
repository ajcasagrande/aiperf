# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
AIPerf Lifecycle - Composable Service Management System

This module provides a clean, composable approach to service lifecycle management,
message handling, and background task management. You can use exactly what you need!

Building Blocks:
- BackgroundTasks: Just background task management
- Messaging: Just messaging with decorators
- Lifecycle: Just lifecycle with initialize/start/stop

Combinations:
- LifecycleWithTasks: Lifecycle + background tasks
- LifecycleWithMessaging: Lifecycle + messaging
- Service: Everything (lifecycle + tasks + messaging)

Plugin System:
- PluginManager: Dynamic plugin discovery and management
- Automatic plugin loading from plugins/ directory
- Full lifecycle integration for plugins

Legacy/Convenience:
- LifecycleService: Basic lifecycle (from base.py)
- AIPerf: Alias for Service (full-featured)

Choose exactly what you need:

Example - Just background tasks:
    class MyWorker(BackgroundTasks):
        @background_task(interval=5.0)
        async def do_work(self):
            pass

Example - Just messaging:
    class MyHandler(Messaging):
        @message_handler("DATA")
        async def handle_data(self, message):
            pass

Example - Just lifecycle:
    class MyComponent(Lifecycle):
        async def initialize(self):
            await super().initialize()

Example - Lifecycle + tasks:
    class MyService(LifecycleWithTasks):
        async def initialize(self):
            await super().initialize()

        @background_task(interval=10.0)
        async def periodic_work(self):
            pass

Example - Everything:
    class MyFullService(Service):  # or AIPerf
        async def initialize(self):
            await super().initialize()

        @message_handler("DATA")
        async def handle_data(self, message):
            pass

        @background_task(interval=10.0)
        async def periodic_work(self):
            pass

Example - Plugin system:
    from aiperf.lifecycle import PluginManager, load_and_start_plugins

    # Start all plugins automatically
    plugin_manager = await load_and_start_plugins("./plugins")

    # Or manage manually
    plugin_manager = PluginManager(plugins_dir="./plugins")
    await plugin_manager.initialize()
    await plugin_manager.start()  # Discovers and starts all plugins
"""

# Core building blocks
from .base import LifecycleService, LifecycleState
from .components import (
    AIPerf,  # Alias for Service
    BackgroundTasks,
    Lifecycle,
    LifecycleWithMessaging,
    LifecycleWithTasks,
    Messaging,
    Service,
)

# Decorators
from .decorators import background_task, command_handler, message_handler

# Infrastructure
from .messaging import Command, Message, MessageBus

# Plugin System
from .plugins import (
    PluginInstance,
    PluginManager,
    PluginMetadata,
    get_plugin_manager,
    load_and_start_plugins,
)

# Legacy from service.py (now superseded by components.py)
from .service import ManagedLifecycleService
from .tasks import TaskManager

__all__ = [
    # Building blocks - use exactly what you need
    "BackgroundTasks",  # Just background tasks
    "Messaging",  # Just messaging
    "Lifecycle",  # Just lifecycle
    # Combinations - common patterns
    "LifecycleWithTasks",  # Lifecycle + tasks
    "LifecycleWithMessaging",  # Lifecycle + messaging
    "Service",  # Everything
    # Plugin System
    "PluginManager",  # Dynamic plugin management
    "PluginMetadata",  # Plugin metadata class
    "PluginInstance",  # Plugin instance wrapper
    "get_plugin_manager",  # Get plugin manager instance
    "load_and_start_plugins",  # Convenience function
    # Convenience/Legacy
    "AIPerf",  # Alias for Service
    "LifecycleService",  # Basic lifecycle from base.py
    "ManagedLifecycleService",  # Legacy full service
    # Core types
    "LifecycleState",
    # Decorators
    "message_handler",
    "background_task",
    "command_handler",
    # Infrastructure
    "MessageBus",
    "Message",
    "Command",
    "TaskManager",
]
