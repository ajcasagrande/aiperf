# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Clean base plugin classes for legacy messaging integration.

This module provides simplified base classes that abstract away the complexities
of integrating legacy ZMQ messaging with modern decorator patterns.

The key improvement is using standard start()/stop() methods that can be
properly chained through super() inheritance instead of requiring manual
method calls.
"""

import asyncio
import logging
from typing import Any

from aiperf.common.config import ServiceConfig
from aiperf.lifecycle.decorators import command_handler, message_handler
from aiperf.lifecycle.messaging_legacy import Command, Message, MessageBus


class LegacyPlugin:
    """
    Ultra-clean base class for plugins using legacy messaging.

    This class abstracts away all the ZMQ and messaging complexities,
    providing a simple interface with standard start()/stop() methods
    that work properly with inheritance chains.

    Features:
    - Automatic decorator discovery and registration
    - Real ZMQ communication via legacy infrastructure
    - Standard lifecycle methods (start/stop) with super() chaining
    - Simple publish/command methods
    - Automatic error handling and logging

    Usage:
        class MyPlugin(LegacyPlugin):
            def __init__(self, service_config=None, **kwargs):
                super().__init__(service_id="my_plugin", service_config=service_config, **kwargs)

            async def start(self):
                await super().start()  # Always call super()!
                # Your initialization here

            @message_handler("DATA")
            async def handle_data(self, message):
                # Handle messages with decorators
                pass

            @command_handler("STATUS")
            async def get_status(self, message):
                # Handle commands and return responses
                return {"status": "healthy"}
    """

    def __init__(
        self,
        service_id: str,
        service_config: ServiceConfig | None = None,
        logger: logging.Logger | None = None,
        **kwargs,
    ):
        # Call super() in case someone uses multiple inheritance
        super().__init__(**kwargs)

        self.service_id = service_id
        self.service_config = service_config or ServiceConfig()
        self.logger = logger or logging.getLogger(f"plugin.{service_id}")

        # Initialize messaging infrastructure
        self.message_bus = MessageBus(
            logger=self.logger, service_config=self.service_config
        )

        # State tracking
        self._started = False
        self._message_handlers: dict[str, list] = {}
        self._command_handlers: dict[str, list] = {}

        # Discover decorated handlers
        self._discover_handlers()

    def _discover_handlers(self) -> None:
        """Discover message and command handlers from decorators."""
        for name in dir(self):
            method = getattr(self, name)
            if not callable(method):
                continue

            # Message handlers (@message_handler)
            if hasattr(method, "_message_types"):
                for msg_type in method._message_types:
                    self._message_handlers.setdefault(msg_type, []).append(method)

            # Command handlers (@command_handler)
            if hasattr(method, "_command_types"):
                for cmd_type in method._command_types:
                    self._command_handlers.setdefault(cmd_type, []).append(method)

    async def start(self) -> None:
        """
        Start the plugin and its messaging.

        This is the standard lifecycle method that should be overridden
        by subclasses. Always call super().start() first!
        """
        if self._started:
            return

        # Start messaging infrastructure
        await self.message_bus.start()

        # Register for targeted messages
        self.message_bus.register_service(
            self.service_id, self._handle_targeted_message
        )

        # Subscribe to broadcast messages
        for message_type, handlers in self._message_handlers.items():
            if handlers:
                self.message_bus.subscribe(message_type, self._handle_broadcast_message)

        # Subscribe to commands
        for command_type, handlers in self._command_handlers.items():
            if handlers:
                self.message_bus.subscribe(command_type, self._handle_command_message)

        self._started = True
        self.logger.info(f"Plugin {self.service_id} started")

    async def stop(self) -> None:
        """
        Stop the plugin and cleanup messaging.

        This is the standard lifecycle method that should be overridden
        by subclasses. Always call super().stop() at the end!
        """
        if not self._started:
            return

        # Unregister from messaging
        self.message_bus.unregister_service(self.service_id)

        # Stop messaging infrastructure
        await self.message_bus.stop()

        self._started = False
        self.logger.info(f"Plugin {self.service_id} stopped")

    # =================================================================
    # Message Handling (Private)
    # =================================================================

    async def _handle_targeted_message(self, message: Message) -> None:
        """Handle messages targeted specifically to this plugin."""
        handlers = self._message_handlers.get(message.type, [])
        handlers.extend(self._command_handlers.get(message.type, []))

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                self.logger.error(f"Error in targeted handler {handler.__name__}: {e}")

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
                self.logger.error(f"Error in broadcast handler {handler.__name__}: {e}")

    async def _handle_command_message(self, message: Message) -> None:
        """Handle command messages and send responses."""
        handlers = self._command_handlers.get(message.type, [])

        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    result = await handler(message)
                else:
                    result = handler(message)

                # Send response if the message expects one and we have a result
                if result is not None and message.sender_id:
                    await self.message_bus.send_response(message, result)

            except Exception as e:
                self.logger.error(f"Error in command handler {handler.__name__}: {e}")
                # Send error response
                if message.sender_id:
                    await self.message_bus.send_response(
                        message, {"error": str(e), "handler": handler.__name__}
                    )

    # =================================================================
    # Convenience Methods (Public API)
    # =================================================================

    async def publish(
        self, message_type: str, content: Any = None, target_id: str | None = None
    ) -> None:
        """
        Publish a message.

        Args:
            message_type: Type of message to send
            content: Message content/payload
            target_id: Optional target service ID (None for broadcast)
        """
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
        """
        Send a command and wait for response.

        Args:
            command_type: Type of command to send
            target_id: Target service ID
            content: Optional command content
            timeout: Response timeout in seconds

        Returns:
            Response content

        Raises:
            asyncio.TimeoutError: If no response received within timeout
        """
        command = Command(
            type=command_type,
            content=content,
            sender_id=self.service_id,
            target_id=target_id,
            timeout=timeout,
        )
        return await self.message_bus.send_command(command)

    # =================================================================
    # Status and Info
    # =================================================================

    @property
    def is_started(self) -> bool:
        """Check if the plugin is started."""
        return self._started

    def get_handler_info(self) -> dict:
        """Get information about registered handlers."""
        return {
            "message_handlers": {
                msg_type: [h.__name__ for h in handlers]
                for msg_type, handlers in self._message_handlers.items()
            },
            "command_handlers": {
                cmd_type: [h.__name__ for h in handlers]
                for cmd_type, handlers in self._command_handlers.items()
            },
        }


class DataProcessor(LegacyPlugin):
    """
    Example data processing plugin that demonstrates clean inheritance.

    This shows how simple it is to create plugins with the new base class:
    - Just inherit from LegacyPlugin
    - Use decorators for message handling
    - Override start() and stop() with super() calls
    - Focus on your business logic, not infrastructure
    """

    def __init__(self, service_config: ServiceConfig | None = None, **kwargs):
        super().__init__(
            service_id="data_processor", service_config=service_config, **kwargs
        )
        self.processed_count = 0
        self.data_cache: list[dict] = []

    async def start(self) -> None:
        """Start the data processor."""
        await super().start()  # Always call super() first!

        # Your initialization logic here
        self.processed_count = 0
        self.data_cache.clear()
        self.logger.info("Data processor ready for processing")

    async def stop(self) -> None:
        """Stop the data processor."""
        # Your cleanup logic here
        self.logger.info(
            f"Data processor stopping - processed {self.processed_count} items"
        )

        await super().stop()  # Always call super() last!

    @message_handler("DATA_INCOMING", "RAW_DATA")
    async def handle_data(self, message: Message) -> None:
        """Process incoming data."""
        data = message.content
        self.logger.info(f"Processing data: {data}")

        # Process the data
        processed = {
            "original": data,
            "processed_at": asyncio.get_event_loop().time(),
            "processed_by": self.service_id,
            "sequence": self.processed_count,
        }

        self.processed_count += 1
        self.data_cache.append(processed)

        # Keep only last 100 items
        if len(self.data_cache) > 100:
            self.data_cache = self.data_cache[-100:]

        # Publish result
        await self.publish("DATA_PROCESSED", processed)

        # Send acknowledgment to sender
        if message.sender_id:
            await self.publish(
                "DATA_ACK",
                {"sequence": self.processed_count - 1, "status": "processed"},
                target_id=message.sender_id,
            )

    @command_handler("GET_STATUS")
    async def get_status(self, message: Message) -> dict:
        """Get processor status."""
        return {
            "service_id": self.service_id,
            "processed_count": self.processed_count,
            "cache_size": len(self.data_cache),
            "status": "healthy" if self.is_started else "stopped",
        }

    @command_handler("GET_DATA")
    async def get_data(self, message: Message) -> dict:
        """Get processed data."""
        request = message.content or {}
        limit = min(request.get("limit", 10), 50)  # Max 50 items

        return {
            "data": self.data_cache[-limit:] if self.data_cache else [],
            "total_count": len(self.data_cache),
            "limit": limit,
        }

    @command_handler("CLEAR_CACHE")
    async def clear_cache(self, message: Message) -> dict:
        """Clear the data cache."""
        old_size = len(self.data_cache)
        self.data_cache.clear()

        return {
            "cleared_items": old_size,
            "new_size": 0,
            "timestamp": asyncio.get_event_loop().time(),
        }


class Monitor(LegacyPlugin):
    """
    Example monitoring plugin showing cross-plugin communication.

    This demonstrates:
    - Monitoring other plugins
    - Cross-plugin commands
    - Activity logging
    - System health checks
    """

    def __init__(self, service_config: ServiceConfig | None = None, **kwargs):
        super().__init__(service_id="monitor", service_config=service_config, **kwargs)
        self.activity_log: list[dict] = []

    async def start(self) -> None:
        """Start the monitor."""
        await super().start()  # Always call super() first!

        # Monitor initialization
        self.activity_log.clear()
        self.logger.info("Monitor started - watching system activity")

    async def stop(self) -> None:
        """Stop the monitor."""
        # Monitor cleanup
        self.logger.info(
            f"Monitor stopping - logged {len(self.activity_log)} activities"
        )

        await super().stop()  # Always call super() last!

    @message_handler("DATA_PROCESSED", "DATA_ACK")
    async def monitor_activity(self, message: Message) -> None:
        """Monitor processing activity."""
        activity = {
            "timestamp": asyncio.get_event_loop().time(),
            "type": message.type,
            "sender": message.sender_id,
            "content": message.content,
        }

        self.activity_log.append(activity)

        # Keep only last 100 activities
        if len(self.activity_log) > 100:
            self.activity_log = self.activity_log[-100:]

        self.logger.debug(f"Logged activity: {message.type} from {message.sender_id}")

    @command_handler("GET_ACTIVITY")
    async def get_activity(self, message: Message) -> dict:
        """Get recent activity."""
        request = message.content or {}
        limit = min(request.get("limit", 20), 100)  # Max 100 items

        return {
            "activities": self.activity_log[-limit:],
            "total_count": len(self.activity_log),
            "limit": limit,
        }

    @command_handler("CHECK_HEALTH")
    async def check_health(self, message: Message) -> dict:
        """Check health of other services."""
        health_checks = {}

        # Check data processor
        try:
            status = await self.send_command(
                "GET_STATUS", "data_processor", timeout=5.0
            )
            health_checks["data_processor"] = {
                "status": "healthy",
                "details": status,
            }
        except asyncio.TimeoutError:
            health_checks["data_processor"] = {
                "status": "timeout",
                "error": "Status check timed out",
            }
        except Exception as e:
            health_checks["data_processor"] = {
                "status": "error",
                "error": str(e),
            }

        overall_health = (
            "healthy"
            if all(check["status"] == "healthy" for check in health_checks.values())
            else "degraded"
        )

        return {
            "overall_health": overall_health,
            "services": health_checks,
            "check_time": asyncio.get_event_loop().time(),
        }
