# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Ultimate AIPerf Lifecycle - The Simplest Way to Build AIPerf Services

This module provides the ultimate user-friendly lifecycle system that uses REAL aiperf
infrastructure while being dramatically simpler than the current complex system.

🎯 ONE CLASS TO RULE THEM ALL:
    from aiperf.lifecycle import AIPerfService
    from aiperf.common.enums import MessageType, CommandType, ServiceType

    class MyService(AIPerfService):
        def __init__(self, service_config, **kwargs):
            super().__init__(
                service_id="my_service",
                service_type=ServiceType.DATASET_MANAGER,
                service_config=service_config,
                **kwargs
            )

        async def initialize(self):
            await super().initialize()  # Always call super()!
            # Your initialization here

        async def start(self):
            await super().start()  # Always call super()!
            # Your start logic here

        @message_handler(MessageType.STATUS)
        async def handle_status(self, message: Message):
            # Handle REAL aiperf messages with full type safety
            pass

        @command_handler(CommandType.PROFILE_START)
        async def handle_profile_start(self, command: CommandMessage):
            # Handle REAL aiperf commands with full type safety
            return {"result": "started"}

        @background_task(interval=30.0)
        async def periodic_cleanup(self):
            # Automatic background task management
            pass

✨ KEY BENEFITS:
- Real aiperf types: MessageType, CommandType, Message, CommandMessage
- Real ZMQ communication: Full integration with aiperf infrastructure
- Clean inheritance: Standard initialize()/start()/stop() with super() calls
- Auto-discovery: Automatic @message_handler/@command_handler registration
- Type safety: Full typing with real aiperf message infrastructure
- Simple API: Easy publish()/send_command() methods
- Zero complexity: Focus on business logic, not infrastructure

🏗️ ARCHITECTURE:
    AIPerfService (core.py) - The ultimate user-friendly base class
    └── Uses real aiperf infrastructure under the hood
        ├── Real MessageType/CommandType enums
        ├── Real Message/CommandMessage classes
        ├── Real PubClient/SubClient communication
        ├── Real ServiceConfig integration
        └── Real ZMQ event bus and proxies

🚀 MIGRATION GUIDE:
    OLD (Complex):
        class MyService(BaseService, AIPerfMessagePubSubMixin, CommandMessageHandlerMixin):
            @supports_hooks(AIPerfHook.initialize, AIPerfHook.start)
            def __init__(self, service_config, **kwargs):
                super().__init__(service_config=service_config, **kwargs)

    NEW (Simple):
        class MyService(AIPerfService):
            def __init__(self, service_config, **kwargs):
                super().__init__(service_id="my_service", service_type=ServiceType.TEST,
                               service_config=service_config, **kwargs)

📦 BUILDING BLOCKS (Optional):
If you need just specific functionality, you can still use the old components:
- BackgroundTasks: Just background task management
- Messaging: Just messaging with decorators
- Lifecycle: Just lifecycle with initialize/start/stop

But 99% of the time, you want AIPerfService - it does everything you need!
"""

# =================================================================
# THE ULTIMATE API - What 99% of people need
# =================================================================

# The ultimate service class - ONE class to rule them all
from aiperf.common.config import ServiceConfig, UserConfig

# =================================================================
# REAL AIPERF TYPES - Re-exported for convenience
# =================================================================
# Import and re-export real aiperf types for user convenience
from aiperf.common.enums import CommandType, MessageType, ServiceType
from aiperf.common.messages import CommandMessage, Message

# =================================================================
# OPTIONAL BUILDING BLOCKS - For special cases
# =================================================================
# Legacy/optional components (for special use cases)
from .components import (
    BackgroundTasks,
    Lifecycle,
    LifecycleWithMessaging,
    LifecycleWithTasks,
    Messaging,
)
from .components import (
    Service as LegacyService,  # Renamed to avoid confusion
)

# Legacy lifecycle state
from .core import AIPerfService, LifecycleState

# Essential decorators for ultimate user-friendliness
from .decorators import background_task, command_handler, message_handler

# Ultimate messaging system using real aiperf infrastructure
from .messaging import MessageBus

# Plugin system (advanced usage)
from .plugins import (
    PluginInstance,
    PluginManager,
    PluginMetadata,
    get_plugin_manager,
    load_and_start_plugins,
)

# =================================================================
# CONVENIENT ALIASES
# =================================================================

# Primary aliases - what most people will use
Service = AIPerfService  # Primary alias
AIPerf = AIPerfService  # Alternative alias

# =================================================================
# ULTIMATE API EXPORTS
# =================================================================

__all__ = [
    # =============================================================
    # THE ULTIMATE API - 99% of users need just these
    # =============================================================
    "AIPerfService",  # The ultimate service class
    "Service",  # Primary alias
    "AIPerf",  # Alternative alias
    # Essential decorators
    "message_handler",  # Handle real aiperf messages
    "command_handler",  # Handle real aiperf commands
    "background_task",  # Automatic background tasks
    # Ultimate messaging
    "MessageBus",  # Real aiperf infrastructure messaging
    # Real aiperf types (re-exported for convenience)
    "MessageType",  # Real aiperf message types
    "CommandType",  # Real aiperf command types
    "ServiceType",  # Real aiperf service types
    "Message",  # Real aiperf message class
    "CommandMessage",  # Real aiperf command message class
    "ServiceConfig",  # Real aiperf service configuration
    "UserConfig",  # Real aiperf user configuration
    # =============================================================
    # OPTIONAL/ADVANCED - Special use cases only
    # =============================================================
    # Optional building blocks (for special cases)
    "BackgroundTasks",  # Just background tasks
    "Messaging",  # Just messaging
    "Lifecycle",  # Just lifecycle
    "LifecycleWithTasks",  # Lifecycle + tasks
    "LifecycleWithMessaging",  # Lifecycle + messaging
    "LegacyService",  # Old Service from components.py
    # Plugin system (advanced)
    "PluginManager",  # Dynamic plugin management
    "PluginMetadata",  # Plugin metadata class
    "PluginInstance",  # Plugin instance wrapper
    "get_plugin_manager",  # Get plugin manager instance
    "load_and_start_plugins",  # Convenience function
    # State management
    "LifecycleState",  # Lifecycle state enum
]

# =================================================================
# USAGE EXAMPLES AND DOCUMENTATION
# =================================================================

"""
🚀 QUICK START EXAMPLES:

1. BASIC SERVICE (Most Common):
    from aiperf.lifecycle import AIPerfService, message_handler, CommandType, MessageType, ServiceType
    from aiperf.common.config import ServiceConfig

    class MyService(AIPerfService):
        def __init__(self, service_config):
            super().__init__(
                service_id="my_service",
                service_type=ServiceType.DATASET_MANAGER,
                service_config=service_config
            )

        async def initialize(self):
            await super().initialize()  # Always!
            self.data = []

        async def start(self):
            await super().start()  # Always!
            self.logger.info("Service ready!")

        @message_handler(MessageType.STATUS)
        async def handle_status(self, message):
            await self.publish(MessageType.HEARTBEAT, service_id=self.service_id)

        @command_handler(CommandType.PROFILE_START)
        async def handle_start(self, command):
            return {"status": "started"}

2. COMPLETE EXAMPLE WITH EVERYTHING:
    from aiperf.lifecycle import AIPerfService, message_handler, command_handler, background_task
    from aiperf.common.enums import MessageType, CommandType, ServiceType

    class DataProcessor(AIPerfService):
        def __init__(self, service_config):
            super().__init__(
                service_id="data_processor",
                service_type=ServiceType.DATASET_MANAGER,
                service_config=service_config
            )
            self.processed_count = 0

        async def initialize(self):
            await super().initialize()
            self.db = await connect_database()

        async def start(self):
            await super().start()
            self.logger.info("Data processor ready!")

        async def stop(self):
            await super().stop()
            await self.db.close()

        @message_handler(MessageType.DATASET_CONFIGURED_NOTIFICATION)
        async def handle_data_ready(self, message):
            self.logger.info("Dataset is ready for processing")

        @command_handler(CommandType.PROFILE_START)
        async def start_profiling(self, command):
            self.profiling_active = True
            return {"status": "profiling_started"}

        @background_task(interval=30.0)
        async def health_check(self):
            health = {"processed": self.processed_count, "status": "healthy"}
            await self.publish(MessageType.SERVICE_HEALTH, service_id=self.service_id)

3. RUNNING A SERVICE:
    import asyncio
    from aiperf.common.config import ServiceConfig
    from aiperf.common.enums import CommunicationBackend

    async def main():
        service_config = ServiceConfig(comm_backend=CommunicationBackend.ZMQ_TCP)

        service = MyService(service_config)
        await service.run_until_stopped()  # One line to run everything!

    if __name__ == "__main__":
        asyncio.run(main())

🎯 WHY THIS IS BETTER:

✅ SIMPLE: One class (AIPerfService) does everything
✅ REAL: Uses actual aiperf types and infrastructure
✅ TYPE-SAFE: Full IDE support and type checking
✅ PYTHONIC: Standard inheritance patterns with super()
✅ CLEAN: Focus on business logic, not infrastructure
✅ POWERFUL: Full access to aiperf ecosystem
✅ COMPATIBLE: Works with existing aiperf services
✅ FUTURE-PROOF: Built on real aiperf foundations

❌ OLD WAY: Complex mixins, hooks, auto-discovery, custom types
✅ NEW WAY: Simple inheritance, real types, clear patterns

This is the ULTIMATE AIPerf service development experience! 🚀
"""
