#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Demonstration of plugins using the legacy-compatible messaging system with decorators.

This demo shows how to create plugins that use both the legacy ZMQ infrastructure
and the simple message decorator patterns.
"""

import asyncio
import logging
import time
from typing import Any

from aiperf.common.config import ServiceConfig
from aiperf.common.enums import CommunicationBackend
from aiperf.lifecycle.decorators import command_handler, message_handler
from aiperf.lifecycle.messaging_legacy import Command, Message, MessageBus
from aiperf.lifecycle.plugins import PluginInstance, PluginMetadata

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LegacyMessagingBase:
    """
    Base class that provides legacy messaging capabilities to plugins.

    This integrates the legacy messaging system with the decorator pattern
    used by the lifecycle system.
    """

    def __init__(
        self,
        service_id: str,
        service_config: ServiceConfig | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.service_id = service_id
        self.service_config = service_config or ServiceConfig()
        self.message_bus = MessageBus(logger=logger, service_config=self.service_config)

        # Discover message and command handlers from decorators
        self._message_handlers: dict[str, list] = {}
        self._command_handlers: dict[str, list] = {}
        self._discover_handlers()

    def _discover_handlers(self) -> None:
        """Discover message and command handlers from decorators."""
        for name in dir(self):
            method = getattr(self, name)
            if not callable(method):
                continue

            # Message handlers
            if hasattr(method, "_message_types"):
                for msg_type in method._message_types:
                    self._message_handlers.setdefault(msg_type, []).append(method)

            # Command handlers
            if hasattr(method, "_command_types"):
                for cmd_type in method._command_types:
                    self._command_handlers.setdefault(cmd_type, []).append(method)

    async def start_messaging(self) -> None:
        """Start the messaging system and set up subscriptions."""
        await self.message_bus.start()

        # Register for targeted messages
        self.message_bus.register_service(
            self.service_id, self._handle_targeted_message
        )

        # Subscribe to message types
        for message_type, handlers in self._message_handlers.items():
            if handlers:
                self.message_bus.subscribe(message_type, self._handle_broadcast_message)

        # Subscribe to command types
        for command_type, handlers in self._command_handlers.items():
            if handlers:
                self.message_bus.subscribe(command_type, self._handle_command_message)

        logger.info(f"Plugin {self.service_id} messaging started")

    async def stop_messaging(self) -> None:
        """Stop the messaging system."""
        await self.message_bus.stop()
        logger.info(f"Plugin {self.service_id} messaging stopped")

    async def _handle_targeted_message(self, message: Message) -> None:
        """Handle messages targeted specifically to this plugin."""
        # Check if we have handlers for this message type
        handlers = self._message_handlers.get(message.type, [])
        handlers.extend(self._command_handlers.get(message.type, []))

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Error in targeted handler {handler.__name__}: {e}")

    async def _handle_broadcast_message(self, message: Message) -> None:
        """Handle broadcast messages."""
        handlers = self._message_handlers.get(message.type, [])

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Error in broadcast handler {handler.__name__}: {e}")

    async def _handle_command_message(self, message: Message) -> None:
        """Handle command messages and send responses if needed."""
        handlers = self._command_handlers.get(message.type, [])

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(message)
                else:
                    result = handler(message)

                # Send response if the message expects one
                if result is not None and message.sender_id:
                    await self.message_bus.send_response(message, result)

            except Exception as e:
                logger.error(f"Error in command handler {handler.__name__}: {e}")
                # Send error response
                if message.sender_id:
                    await self.message_bus.send_response(
                        message, {"error": str(e), "handler": handler.__name__}
                    )

    # Convenience methods for sending messages
    async def publish_message(
        self, message_type: str, content: Any = None, target_id: str | None = None
    ) -> None:
        """Publish a message."""
        message = Message(
            type=message_type,
            content=content,
            sender_id=self.service_id,
            target_id=target_id,
        )
        await self.message_bus.publish(message)

    async def send_command(
        self,
        command_type: str,
        target_id: str,
        content: Any = None,
        timeout: float = 30.0,
    ) -> Any:
        """Send a command and wait for response."""
        command = Command(
            type=command_type,
            content=content,
            sender_id=self.service_id,
            target_id=target_id,
            timeout=timeout,
        )
        return await self.message_bus.send_command(command)


class DataProcessorPlugin(LegacyMessagingBase):
    """
    Example plugin that processes data using legacy messaging and decorators.

    This plugin demonstrates:
    - Message handling with decorators
    - Command handling with responses
    - Integration with legacy ZMQ infrastructure
    - Plugin lifecycle management
    """

    def __init__(self, service_config: ServiceConfig | None = None, **kwargs):
        super().__init__(
            service_id="data_processor_plugin", service_config=service_config, **kwargs
        )
        self.processed_count = 0
        self.start_time = time.time()
        self.data_cache: list[dict] = []

    async def start(self) -> None:
        """Start the plugin."""
        await self.start_messaging()
        logger.info("DataProcessorPlugin started and ready")

    async def stop(self) -> None:
        """Stop the plugin."""
        await self.stop_messaging()
        logger.info("DataProcessorPlugin stopped")

    @message_handler("DATA_INCOMING", "RAW_DATA")
    async def handle_data_incoming(self, message: Message) -> None:
        """Handle incoming data for processing."""
        logger.info(f"Processing incoming data: {message.content}")

        # Simulate data processing
        processed_data = {
            "original": message.content,
            "processed_at": time.time(),
            "processed_by": self.service_id,
            "sequence": self.processed_count,
        }

        self.processed_count += 1
        self.data_cache.append(processed_data)

        # Keep only last 100 items
        if len(self.data_cache) > 100:
            self.data_cache = self.data_cache[-100:]

        # Publish processed data
        await self.publish_message("DATA_PROCESSED", processed_data)

        # Send acknowledgment to sender if specified
        if message.sender_id:
            await self.publish_message(
                "DATA_ACK",
                {"sequence": self.processed_count - 1, "status": "processed"},
                target_id=message.sender_id,
            )

    @command_handler("GET_STATUS")
    async def get_status(self, message: Message) -> dict:
        """Handle status requests and return current plugin status."""
        uptime = time.time() - self.start_time
        status = {
            "service_id": self.service_id,
            "status": "healthy",
            "uptime_seconds": uptime,
            "processed_count": self.processed_count,
            "cache_size": len(self.data_cache),
            "last_processed": self.data_cache[-1] if self.data_cache else None,
        }
        logger.info(f"Status requested by {message.sender_id}: {status}")
        return status

    @command_handler("GET_DATA")
    async def get_data(self, message: Message) -> dict:
        """Handle data retrieval requests."""
        request = message.content or {}
        limit = request.get("limit", 10)
        offset = request.get("offset", 0)

        # Return requested data slice
        data_slice = self.data_cache[offset : offset + limit]

        result = {
            "data": data_slice,
            "total_count": len(self.data_cache),
            "limit": limit,
            "offset": offset,
            "requested_by": message.sender_id,
        }

        logger.info(f"Data requested by {message.sender_id}: {len(data_slice)} items")
        return result


class MonitoringPlugin(LegacyMessagingBase):
    """
    Example monitoring plugin that watches system activity.

    This plugin demonstrates:
    - Monitoring other plugins/services
    - Cross-plugin communication
    - Activity logging
    """

    def __init__(self, service_config: ServiceConfig | None = None, **kwargs):
        super().__init__(
            service_id="monitoring_plugin", service_config=service_config, **kwargs
        )
        self.activity_log: list[dict] = []
        self.monitoring_active = False

    async def start(self) -> None:
        """Start the monitoring plugin."""
        await self.start_messaging()
        self.monitoring_active = True
        logger.info("MonitoringPlugin started and monitoring")

    async def stop(self) -> None:
        """Stop the monitoring plugin."""
        self.monitoring_active = False
        await self.stop_messaging()
        logger.info("MonitoringPlugin stopped")

    @message_handler("DATA_PROCESSED", "DATA_ACK")
    async def monitor_activity(self, message: Message) -> None:
        """Monitor data processing activity."""
        activity = {
            "timestamp": time.time(),
            "type": message.type,
            "sender": message.sender_id,
            "content": message.content,
        }

        self.activity_log.append(activity)

        # Keep only last 50 activities
        if len(self.activity_log) > 50:
            self.activity_log = self.activity_log[-50:]

        logger.info(f"Monitored activity: {message.type} from {message.sender_id}")

    @command_handler("GET_ACTIVITY_LOG")
    async def get_activity_log(self, message: Message) -> dict:
        """Return the activity log."""
        request = message.content or {}
        limit = request.get("limit", 20)

        return {
            "activities": self.activity_log[-limit:],
            "total_activities": len(self.activity_log),
            "monitoring_active": self.monitoring_active,
        }

    @command_handler("GET_SYSTEM_HEALTH")
    async def get_system_health(self, message: Message) -> dict:
        """Check health of known services."""
        health_checks = {}

        # Check data processor
        try:
            status = await self.send_command(
                "GET_STATUS", "data_processor_plugin", timeout=5.0
            )
            health_checks["data_processor"] = {
                "status": "healthy",
                "details": status,
            }
        except asyncio.TimeoutError:
            health_checks["data_processor"] = {
                "status": "unhealthy",
                "error": "Timeout on status check",
            }
        except Exception as e:
            health_checks["data_processor"] = {
                "status": "error",
                "error": str(e),
            }

        return {
            "overall_health": "healthy"
            if all(check["status"] == "healthy" for check in health_checks.values())
            else "degraded",
            "service_checks": health_checks,
            "check_time": time.time(),
        }


# Plugin factory functions
def create_data_processor_plugin(
    service_config: ServiceConfig | None = None,
) -> PluginInstance:
    """Factory function to create a DataProcessorPlugin instance."""
    plugin = DataProcessorPlugin(service_config=service_config)

    metadata = PluginMetadata(
        name="data_processor",
        version="1.0.0",
        description="Processes incoming data using legacy messaging",
        author="AIPerf Team",
    )

    return PluginInstance(plugin=plugin, metadata=metadata)


def create_monitoring_plugin(
    service_config: ServiceConfig | None = None,
) -> PluginInstance:
    """Factory function to create a MonitoringPlugin instance."""
    plugin = MonitoringPlugin(service_config=service_config)

    metadata = PluginMetadata(
        name="monitoring",
        version="1.0.0",
        description="Monitors system activity using legacy messaging",
        author="AIPerf Team",
    )

    return PluginInstance(plugin=plugin, metadata=metadata)


async def demo_legacy_plugins():
    """Run a demo showing plugins working with legacy messaging."""
    logger.info("=== Legacy Messaging Plugin Demo ===")

    # Create service configuration
    service_config = ServiceConfig(comm_backend=CommunicationBackend.ZMQ_TCP)

    # Create plugin instances
    data_processor = create_data_processor_plugin(service_config)
    monitoring = create_monitoring_plugin(service_config)

    # Create demo message bus
    demo_bus = MessageBus(service_config=service_config)

    plugins = [data_processor, monitoring]

    try:
        logger.info("--- Starting plugins ---")
        # Start all plugins
        for plugin_instance in plugins:
            await plugin_instance.plugin.start()

        # Start demo bus
        await demo_bus.start()

        # Wait for plugins to initialize
        await asyncio.sleep(1.0)

        logger.info("\n--- Demo: Basic messaging ---")
        # Send some data for processing
        test_data = ["item1", "item2", "item3"]

        for item in test_data:
            await demo_bus.publish(
                Message(
                    type="DATA_INCOMING",
                    content=item,
                    sender_id="demo_orchestrator",
                )
            )

        # Wait for processing
        await asyncio.sleep(2.0)

        logger.info("\n--- Demo: Command/Response ---")
        # Get status from data processor
        status_command = Command(
            type="GET_STATUS",
            sender_id="demo_orchestrator",
            target_id="data_processor_plugin",
            timeout=5.0,
        )

        try:
            status = await demo_bus.send_command(status_command)
            logger.info(f"Data processor status: {status}")
        except asyncio.TimeoutError:
            logger.error("Status command timed out")

        logger.info("\n--- Demo: Cross-plugin communication ---")
        # Monitoring plugin checks data processor health
        health_command = Command(
            type="GET_SYSTEM_HEALTH",
            sender_id="demo_orchestrator",
            target_id="monitoring_plugin",
            timeout=10.0,
        )

        try:
            health = await demo_bus.send_command(health_command)
            logger.info(f"System health: {health.get('overall_health')}")
        except asyncio.TimeoutError:
            logger.error("Health check timed out")

        logger.info("\n--- Demo: Activity monitoring ---")
        # Get activity log
        activity_command = Command(
            type="GET_ACTIVITY_LOG",
            content={"limit": 10},
            sender_id="demo_orchestrator",
            target_id="monitoring_plugin",
            timeout=5.0,
        )

        try:
            activity = await demo_bus.send_command(activity_command)
            logger.info(f"Recent activities: {len(activity.get('activities', []))}")
            for act in activity.get("activities", [])[-3:]:  # Show last 3
                logger.info(f"  - {act['type']} from {act['sender']}")
        except asyncio.TimeoutError:
            logger.error("Activity log command timed out")

        logger.info("\n=== Demo Complete ===")

    finally:
        logger.info("--- Cleaning up ---")
        # Stop all plugins
        for plugin_instance in plugins:
            await plugin_instance.plugin.stop()

        await demo_bus.stop()
        logger.info("Demo cleanup complete")


if __name__ == "__main__":
    asyncio.run(demo_legacy_plugins())
