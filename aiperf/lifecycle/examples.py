# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive examples of the new AIPerf Lifecycle system.

This module demonstrates the simplified inheritance-based approach where:
- Lifecycle methods use simple inheritance with super() calls
- Only message handlers, command handlers, and background tasks use decorators
"""

import asyncio
import random
import time

from aiperf.lifecycle import (
    AIPerf,
    Command,
    Message,
    background_task,
    command_handler,
    message_handler,
)

# =============================================================================
# Example 1: Simple Service with Lifecycle Management
# =============================================================================


class SimpleDataService(AIPerf):
    """
    A simple data processing service.

    This demonstrates the new simplified approach:
    - Lifecycle methods use simple inheritance (just call super())
    - No decorators needed for lifecycle methods
    - Clean, readable inheritance pattern
    """

    def __init__(self):
        super().__init__(service_id="data_service")
        self.data: list[str] = []
        self.processed_count = 0

    async def initialize(self):
        """Override and call super() - simple inheritance!"""
        await super().initialize()  # Always call super()
        self.logger.info("Initializing data service...")
        # Simulate database connection
        await asyncio.sleep(0.1)
        self.logger.info("Database connected!")

    async def start(self):
        """Override and call super() - simple inheritance!"""
        await super().start()  # Always call super()
        self.logger.info("Data service is now running!")

    async def stop(self):
        """Override and call super() - simple inheritance!"""
        await super().stop()  # Always call super()
        self.logger.info(
            f"Stopping data service. Processed {self.processed_count} items."
        )
        self.logger.info("Cleaning up data service resources...")
        self.data.clear()


# =============================================================================
# Example 2: Message Handling Made Simple
# =============================================================================


class MessageHandlingService(AIPerf):
    """
    Service that demonstrates simple message handling.

    Lifecycle methods use inheritance, message handlers use decorators.
    """

    def __init__(self):
        super().__init__(service_id="message_service")
        self.received_messages: list[dict] = []

    async def initialize(self):
        """Simple inheritance - just call super()"""
        await super().initialize()
        self.logger.info("Message handling service initializing...")

    async def start(self):
        """Simple inheritance - just call super()"""
        await super().start()
        self._start_time = time.time()
        self.logger.info("Message handling service started!")

    # Message handlers still use decorators - that's the dynamic part!
    @message_handler("USER_DATA")
    async def handle_user_data(self, message: Message):
        """Handle user data messages."""
        self.logger.info(f"Received user data: {message.content}")
        self.received_messages.append(
            {
                "type": message.type,
                "content": message.content,
                "timestamp": message.timestamp,
                "sender": message.sender_id,
            }
        )

        # Send acknowledgment
        await self.publish_message(
            "DATA_ACK", {"original_id": message.id, "processed_at": time.time()}
        )

    @message_handler("SYSTEM_STATUS", "HEALTH_CHECK")
    async def handle_system_messages(self, message: Message):
        """Handle multiple message types with one handler."""
        self.logger.info(f"Received system message: {message.type}")

        if message.type == "HEALTH_CHECK":
            await self.publish_message(
                "HEALTH_RESPONSE",
                {
                    "status": "healthy",
                    "service_id": self.service_id,
                    "uptime": time.time() - self._start_time
                    if hasattr(self, "_start_time")
                    else 0,
                },
            )


# =============================================================================
# Example 3: Command/Response Patterns
# =============================================================================


class StatisticsService(AIPerf):
    """
    Service that handles commands and returns responses.

    Shows the clean separation:
    - Lifecycle: simple inheritance
    - Commands: decorators for dynamic behavior
    """

    def __init__(self):
        super().__init__(service_id="stats_service")
        self.stats = {
            "requests_handled": 0,
            "errors_count": 0,
            "start_time": time.time(),
        }

    async def initialize(self):
        """Simple inheritance pattern"""
        await super().initialize()
        self.logger.info("Statistics service initializing...")

    async def start(self):
        """Simple inheritance pattern"""
        await super().start()
        self.logger.info("Statistics service ready!")

    # Command handlers use decorators - dynamic behavior
    @command_handler("GET_STATS")
    async def get_statistics(self, command: Command):
        """Return current statistics."""
        self.stats["requests_handled"] += 1
        return {
            "stats": self.stats.copy(),
            "uptime_seconds": time.time() - self.stats["start_time"],
        }

    @command_handler("RESET_STATS")
    async def reset_statistics(self, command: Command):
        """Reset statistics counters."""
        old_stats = self.stats.copy()
        self.stats.update({"requests_handled": 0, "errors_count": 0})
        return {"message": "Statistics reset", "previous_stats": old_stats}

    @command_handler("HEALTH_CHECK")
    async def health_check(self, command: Command):
        """Perform health check."""
        return {
            "status": "healthy",
            "service_id": self.service_id,
            "state": self.state.value,
            "timestamp": time.time(),
        }


# =============================================================================
# Example 4: Background Tasks Made Easy
# =============================================================================


class BackgroundTaskService(AIPerf):
    """
    Service demonstrating background task patterns.

    Background tasks start automatically when service starts.
    Lifecycle methods use simple inheritance.
    """

    def __init__(self):
        super().__init__(service_id="task_service")
        self.work_queue: list[str] = []
        self.processed_items = 0
        self.health_status = "excellent"

    async def initialize(self):
        """Simple inheritance - setup data"""
        await super().initialize()  # Always call super()
        self.work_queue = [f"task_{i}" for i in range(100)]
        self.logger.info(f"Initialized with {len(self.work_queue)} work items")

    async def start(self):
        """Simple inheritance - background tasks start automatically"""
        await super().start()  # Always call super() - this starts background tasks!
        self.logger.info("Background task service is running!")

    async def stop(self):
        """Simple inheritance - background tasks stop automatically"""
        await super().stop()  # Always call super() - this stops background tasks!
        self.logger.info("Background task service stopped!")

    # Background tasks use decorators - started/stopped automatically
    @background_task(interval=2.0)
    async def process_work_queue(self):
        """Process work items every 2 seconds."""
        if self.work_queue:
            item = self.work_queue.pop(0)
            self.processed_items += 1
            self.logger.info(f"Processed {item} (total: {self.processed_items})")

            # Simulate some work
            await asyncio.sleep(0.1)

            # Publish progress update
            await self.publish_message(
                "WORK_PROGRESS",
                {"processed": self.processed_items, "remaining": len(self.work_queue)},
            )

    @background_task(interval=5.0)
    async def health_monitor(self):
        """Monitor service health every 5 seconds."""
        # Simulate health check logic
        load = random.uniform(0.1, 1.0)

        if load > 0.8:
            self.health_status = "degraded"
        elif load > 0.5:
            self.health_status = "fair"
        else:
            self.health_status = "excellent"

        self.logger.debug(f"Health check: {self.health_status} (load: {load:.2f})")

        await self.publish_message(
            "HEALTH_UPDATE",
            {
                "service_id": self.service_id,
                "status": self.health_status,
                "load": load,
                "timestamp": time.time(),
            },
        )

    @background_task(interval=lambda: random.uniform(1, 3))
    async def random_maintenance(self):
        """Run maintenance at random intervals."""
        maintenance_type = random.choice(
            ["cache_cleanup", "log_rotation", "memory_check"]
        )
        self.logger.info(f"Running maintenance: {maintenance_type}")

        # Simulate maintenance work
        await asyncio.sleep(0.05)

    # This task runs once at startup
    @background_task(run_once=True)
    async def startup_initialization(self):
        """One-time startup task."""
        self.logger.info("Running one-time startup initialization...")
        await asyncio.sleep(0.2)  # Simulate initialization work
        self.logger.info("Startup initialization complete!")


# =============================================================================
# Example 5: Complete Real-World Service
# =============================================================================


class DataProcessorService(AIPerf):
    """
    A complete, real-world example combining all features.

    This service:
    - Processes incoming data
    - Handles commands for status and control
    - Runs background tasks for maintenance
    - Publishes progress updates
    - Manages its own state and resources
    """

    def __init__(self):
        super().__init__(service_id="data_processor")
        self.buffer: list[dict] = []
        self.processed_count = 0
        self.error_count = 0
        self.batch_size = 10
        self.processing_enabled = True

    async def initialize(self):
        """Initialize the data processor."""
        self.logger.info("Initializing data processor...")
        # Simulate connecting to external services
        await asyncio.sleep(0.1)
        self.logger.info("Connected to external data sources")

    async def start(self):
        """Service started notification."""
        self.logger.info("Data processor is now active and processing data!")
        await self.publish_message(
            "SERVICE_STARTED",
            {
                "service_id": self.service_id,
                "capabilities": [
                    "data_processing",
                    "batch_operations",
                    "real_time_stats",
                ],
            },
        )

    # =============================================================================
    # Message Handlers
    # =============================================================================

    @message_handler("RAW_DATA")
    async def handle_raw_data(self, message: Message):
        """Process incoming raw data."""
        if not self.processing_enabled:
            self.logger.debug("Processing disabled, ignoring data")
            return

        try:
            data = message.content
            # Add some processing metadata
            processed_data = {
                "original": data,
                "processed_at": time.time(),
                "processor_id": self.service_id,
                "batch_id": len(self.buffer),
            }

            self.buffer.append(processed_data)
            self.logger.debug(f"Added data to buffer (size: {len(self.buffer)})")

            # Process batch if it's full
            if len(self.buffer) >= self.batch_size:
                await self._process_batch()

        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error processing data: {e}")

    @message_handler("FLUSH_BUFFER")
    async def handle_flush_request(self, message: Message):
        """Force process current buffer."""
        if self.buffer:
            self.logger.info(f"Flushing buffer with {len(self.buffer)} items")
            await self._process_batch()
        else:
            self.logger.info("Buffer is empty, nothing to flush")

    # =============================================================================
    # Command Handlers
    # =============================================================================

    @command_handler("GET_STATUS")
    async def get_detailed_status(self, command: Command):
        """Return detailed service status."""
        return {
            "service_id": self.service_id,
            "state": self.state.value,
            "processing_enabled": self.processing_enabled,
            "buffer_size": len(self.buffer),
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "batch_size": self.batch_size,
            "uptime": time.time() - getattr(self, "_start_time", time.time()),
            "tasks": self.get_task_status(),
        }

    @command_handler("CONFIGURE")
    async def configure_service(self, command: Command):
        """Configure service parameters."""
        config = command.content or {}

        if "batch_size" in config:
            old_size = self.batch_size
            self.batch_size = max(1, int(config["batch_size"]))
            self.logger.info(f"Batch size changed from {old_size} to {self.batch_size}")

        if "processing_enabled" in config:
            self.processing_enabled = bool(config["processing_enabled"])
            status = "enabled" if self.processing_enabled else "disabled"
            self.logger.info(f"Processing {status}")

        return {
            "message": "Configuration updated",
            "new_config": {
                "batch_size": self.batch_size,
                "processing_enabled": self.processing_enabled,
            },
        }

    @command_handler("RESET")
    async def reset_service(self, command: Command):
        """Reset service state."""
        old_stats = {
            "buffer_size": len(self.buffer),
            "processed_count": self.processed_count,
            "error_count": self.error_count,
        }

        self.buffer.clear()
        self.processed_count = 0
        self.error_count = 0

        self.logger.info("Service state reset")
        return {"message": "Service reset successfully", "previous_state": old_stats}

    # =============================================================================
    # Background Tasks
    # =============================================================================

    @background_task(interval=10.0)
    async def periodic_stats_report(self):
        """Report statistics every 10 seconds."""
        stats = {
            "service_id": self.service_id,
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "buffer_size": len(self.buffer),
            "timestamp": time.time(),
        }

        await self.publish_message("STATS_REPORT", stats)
        self.logger.info(
            f"Stats: processed={self.processed_count}, errors={self.error_count}, buffer={len(self.buffer)}"
        )

    @background_task(interval=30.0)
    async def buffer_timeout_check(self):
        """Process partial batches that have been waiting too long."""
        if self.buffer and len(self.buffer) < self.batch_size:
            # Check if oldest item is more than 30 seconds old
            oldest_time = min(
                item.get("processed_at", time.time()) for item in self.buffer
            )
            if time.time() - oldest_time > 30:
                self.logger.info("Processing partial batch due to timeout")
                await self._process_batch()

    @background_task(interval=60.0)
    async def maintenance_task(self):
        """Periodic maintenance every minute."""
        self.logger.debug("Running periodic maintenance...")

        # Simulate maintenance work
        await asyncio.sleep(0.1)

        # Example: publish maintenance completion
        await self.publish_message(
            "MAINTENANCE_COMPLETE",
            {
                "service_id": self.service_id,
                "timestamp": time.time(),
                "actions": ["cache_cleanup", "log_rotation"],
            },
        )

    # =============================================================================
    # Helper Methods
    # =============================================================================

    async def _process_batch(self):
        """Process a batch of data."""
        if not self.buffer:
            return

        batch = self.buffer.copy()
        self.buffer.clear()

        try:
            # Simulate batch processing
            await asyncio.sleep(0.05)  # Simulate processing time

            self.processed_count += len(batch)

            # Publish batch completion
            await self.publish_message(
                "BATCH_PROCESSED",
                {
                    "batch_size": len(batch),
                    "total_processed": self.processed_count,
                    "processor_id": self.service_id,
                    "timestamp": time.time(),
                },
            )

            self.logger.info(
                f"Processed batch of {len(batch)} items (total: {self.processed_count})"
            )

        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error processing batch: {e}")
            # Put data back in buffer for retry
            self.buffer.extend(batch)


# =============================================================================
# Example Usage and Demo
# =============================================================================


async def demo_simple_service():
    """Demonstrate basic service lifecycle."""
    print("\n=== Simple Service Demo ===")

    service = SimpleDataService()

    # Start the service
    await service.initialize()
    await service.start()

    # Let it run for a bit
    await asyncio.sleep(1)

    # Stop the service
    await service.stop()

    print("Simple service demo complete!")


async def demo_messaging():
    """Demonstrate message handling between services."""
    print("\n=== Messaging Demo ===")

    # Create services
    message_service = MessageHandlingService()
    stats_service = StatisticsService()

    # Start services
    await message_service.initialize()
    await message_service.start()
    await stats_service.initialize()
    await stats_service.start()

    # Send some messages
    await message_service.publish_message(
        "USER_DATA", {"user_id": 123, "action": "login"}
    )
    await message_service.publish_message("HEALTH_CHECK", {})

    # Send some commands
    stats = await message_service.send_command("GET_STATS", stats_service.service_id)
    print(f"Stats response: {stats}")

    health = await message_service.send_command(
        "HEALTH_CHECK", stats_service.service_id
    )
    print(f"Health response: {health}")

    # Let messages process
    await asyncio.sleep(0.5)

    # Stop services
    await message_service.stop()
    await stats_service.stop()

    print("Messaging demo complete!")


async def demo_background_tasks():
    """Demonstrate background task management."""
    print("\n=== Background Tasks Demo ===")

    service = BackgroundTaskService()

    # Start the service (this starts all background tasks)
    await service.initialize()
    await service.start()

    # Let it run for a bit to see background tasks working
    print("Letting background tasks run for 10 seconds...")
    await asyncio.sleep(10)

    # Check task status
    status = service.get_task_status()
    print(f"Task status: {status}")

    # Stop the service (this stops all background tasks)
    await service.stop()

    print("Background tasks demo complete!")


async def demo_complete_service():
    """Demonstrate the complete real-world service."""
    print("\n=== Complete Service Demo ===")

    processor = DataProcessorService()

    # Start the service
    await processor.initialize()
    await processor.start()

    # Send some data to process
    for i in range(25):
        await processor.publish_message(
            "RAW_DATA",
            {
                "id": i,
                "data": f"sample_data_{i}",
                "priority": random.choice(["low", "medium", "high"]),
            },
        )
        await asyncio.sleep(0.1)  # Small delay between messages

    # Send some commands
    status = await processor.send_command("GET_STATUS", processor.service_id)
    print(f"Service status: {status}")

    # Configure the service
    config_response = await processor.send_command(
        "CONFIGURE", processor.service_id, {"batch_size": 5, "processing_enabled": True}
    )
    print(f"Configuration response: {config_response}")

    # Flush remaining buffer
    await processor.publish_message("FLUSH_BUFFER", {})

    # Let it run a bit more
    await asyncio.sleep(5)

    # Get final status
    final_status = await processor.send_command("GET_STATUS", processor.service_id)
    print(f"Final status: {final_status}")

    # Stop the service
    await processor.stop()

    print("Complete service demo finished!")


async def run_all_demos():
    """Run all demonstration examples."""
    print("🚀 AIPerf Lifecycle System Demonstrations")
    print("==========================================")

    await demo_simple_service()
    await demo_messaging()
    await demo_background_tasks()
    await demo_complete_service()

    print("\n🎉 All demos completed successfully!")
    print("\nKey Benefits of the New System:")
    print("✅ Simple inheritance-based design")
    print("✅ No complex mixins or configuration")
    print("✅ Automatic message and task management")
    print("✅ Clean, readable code")
    print("✅ Easy to debug and understand")
    print("✅ Powerful but simple to use")


if __name__ == "__main__":
    # Run the demonstrations
    asyncio.run(run_all_demos())
