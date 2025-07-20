# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive examples of the composable AIPerf lifecycle components.

This demonstrates how to use each component independently and in combination,
showing the flexibility and power of the composable design.
"""

import asyncio
import time

from aiperf.lifecycle import (
    BackgroundTasks,
    Lifecycle,
    LifecycleWithMessaging,
    LifecycleWithTasks,
    Messaging,
    Service,
    background_task,
    command_handler,
    message_handler,
)

# =============================================================================
# Example 1: Just Background Tasks (No lifecycle, no messaging)
# =============================================================================


class DataProcessor(BackgroundTasks):
    """
    A utility class that just needs background tasks.

    Use case: Processing queued data without full service overhead.
    """

    def __init__(self):
        super().__init__()
        self.data_queue: list[str] = []
        self.processed_count = 0

    def add_data(self, data: str):
        """Add data to process."""
        self.data_queue.append(data)

    @background_task(interval=2.0)
    async def process_data(self):
        """Process queued data every 2 seconds."""
        if self.data_queue:
            item = self.data_queue.pop(0)
            self.processed_count += 1
            print(f"Processed: {item} (total: {self.processed_count})")

    @background_task(interval=10.0)
    async def cleanup(self):
        """Periodic cleanup."""
        print(f"Cleanup: {len(self.data_queue)} items remaining")


async def demo_background_tasks_only():
    """Demo using just background tasks."""
    print("\n=== Background Tasks Only Demo ===")

    processor = DataProcessor()

    # Add some data
    for i in range(5):
        processor.add_data(f"item_{i}")

    # Start tasks manually
    await processor.start_tasks()
    print("Background tasks started...")

    # Let it run for a bit
    await asyncio.sleep(8)

    # Stop tasks manually
    await processor.stop_tasks()
    print("Background tasks stopped")


# =============================================================================
# Example 2: Just Messaging (No lifecycle, no tasks)
# =============================================================================


class EventHandler(Messaging):
    """
    A utility class that just handles messages/commands.

    Use case: Event processing without full service infrastructure.
    """

    def __init__(self):
        super().__init__(service_id="event_handler")
        self.events_received = 0
        self.status = "active"

    @message_handler("USER_EVENT")
    async def handle_user_event(self, message):
        """Handle user events."""
        self.events_received += 1
        print(f"Handled user event: {message.content} (total: {self.events_received})")

        # Send acknowledgment
        await self.publish_message(
            "EVENT_ACK",
            {"original_event": message.content, "processed_at": time.time()},
        )

    @command_handler("GET_STATS")
    async def get_stats(self, command):
        """Return handler statistics."""
        return {
            "events_received": self.events_received,
            "status": self.status,
            "uptime": time.time(),
        }

    @command_handler("SET_STATUS")
    async def set_status(self, command):
        """Update handler status."""
        self.status = command.content.get("status", "active")
        return {"status": self.status}


async def demo_messaging_only():
    """Demo using just messaging."""
    print("\n=== Messaging Only Demo ===")

    handler = EventHandler()

    # Start messaging manually
    await handler.start_messaging()
    print("Messaging started...")

    # Send some events
    await handler.publish_message("USER_EVENT", {"user_id": 123, "action": "login"})
    await handler.publish_message("USER_EVENT", {"user_id": 456, "action": "logout"})

    # Send commands
    stats = await handler.send_command("GET_STATS", handler.service_id)
    print(f"Stats: {stats}")

    await handler.send_command(
        "SET_STATUS", handler.service_id, {"status": "maintenance"}
    )

    # Brief pause for processing
    await asyncio.sleep(0.5)

    # Stop messaging manually
    await handler.stop_messaging()
    print("Messaging stopped")


# =============================================================================
# Example 3: Just Lifecycle (No messaging, no tasks)
# =============================================================================


class DatabaseConnection(Lifecycle):
    """
    A utility class that just needs lifecycle management.

    Use case: Resource management without messaging or background tasks.
    """

    def __init__(self):
        super().__init__(component_id="database")
        self.connection = None
        self.is_connected = False

    async def on_init(self):
        """Initialize database connection."""
        await super().on_init()
        print("Connecting to database...")
        await asyncio.sleep(0.1)  # Simulate connection time
        self.connection = "mock_db_connection"
        self.is_connected = True
        print("Database connected!")

    async def on_start(self):
        """Start database operations."""
        await super().on_start()
        print("Database ready for operations")

    async def on_stop(self):
        """Stop and cleanup database."""
        await super().on_stop()
        print("Closing database connection...")
        self.connection = None
        self.is_connected = False
        print("Database disconnected")

    async def query(self, sql: str):
        """Execute a database query."""
        if not self.is_connected:
            raise RuntimeError("Database not connected")
        print(f"Executing query: {sql}")
        return f"result_for_{sql}"


async def demo_lifecycle_only():
    """Demo using just lifecycle."""
    print("\n=== Lifecycle Only Demo ===")

    db = DatabaseConnection()

    # Full lifecycle
    await db.initialize()
    await db.start()

    # Use the component
    result = await db.query("SELECT * FROM users")
    print(f"Query result: {result}")

    await db.stop()


# =============================================================================
# Example 4: Lifecycle + Tasks (No messaging)
# =============================================================================


class MonitoringService(LifecycleWithTasks):
    """
    A service that needs lifecycle and background tasks but no messaging.

    Use case: System monitoring without external communication.
    """

    def __init__(self):
        super().__init__(component_id="monitor")
        self.metrics: dict[str, float] = {}
        self.alert_count = 0

    async def on_init(self):
        """Initialize monitoring."""
        await super().on_init()
        print("Initializing monitoring system...")
        self.metrics = {"cpu": 0.0, "memory": 0.0, "disk": 0.0}

    async def on_start(self):
        """Start monitoring (automatically starts background tasks)."""
        await super().on_start()
        print("Monitoring service is active!")

    async def on_stop(self):
        """Stop monitoring (automatically stops background tasks)."""
        await super().on_stop()
        print("Monitoring stopped. Final metrics:", self.metrics)

    @background_task(interval=3.0)
    async def collect_metrics(self):
        """Collect system metrics every 3 seconds."""
        import random

        self.metrics["cpu"] = random.uniform(10, 90)
        self.metrics["memory"] = random.uniform(20, 80)
        self.metrics["disk"] = random.uniform(5, 95)
        print(
            f"Metrics: CPU={self.metrics['cpu']:.1f}%, "
            f"Memory={self.metrics['memory']:.1f}%, "
            f"Disk={self.metrics['disk']:.1f}%"
        )

    @background_task(interval=5.0)
    async def check_alerts(self):
        """Check for alerts every 5 seconds."""
        if self.metrics["cpu"] > 80:
            self.alert_count += 1
            print(
                f"⚠️  HIGH CPU ALERT! {self.metrics['cpu']:.1f}% (Alert #{self.alert_count})"
            )


async def demo_lifecycle_with_tasks():
    """Demo using lifecycle + tasks."""
    print("\n=== Lifecycle + Tasks Demo ===")

    monitor = MonitoringService()

    # Start service (lifecycle + tasks)
    await monitor.initialize()
    await monitor.start()

    # Let it monitor for a while
    await asyncio.sleep(12)

    # Stop service (lifecycle + tasks)
    await monitor.stop()


# =============================================================================
# Example 5: Lifecycle + Messaging (No tasks)
# =============================================================================


class ConfigurationService(LifecycleWithMessaging):
    """
    A service that needs lifecycle and messaging but no background tasks.

    Use case: Configuration management with request/response patterns.
    """

    def __init__(self):
        super().__init__(component_id="config_service")
        self.config: dict[str, str] = {}

    async def on_init(self):
        """Initialize configuration service."""
        await super().on_init()
        print("Loading configuration...")
        self.config = {
            "database_url": "localhost:5432",
            "cache_size": "1000",
            "debug_mode": "false",
        }
        print(f"Loaded {len(self.config)} configuration items")

    async def on_start(self):
        """Start configuration service (automatically starts messaging)."""
        await super().on_start()
        print("Configuration service ready for requests!")

    async def on_stop(self):
        """Stop configuration service (automatically stops messaging)."""
        await super().on_stop()
        print("Configuration service stopped")

    @message_handler("CONFIG_CHANGED")
    async def handle_config_change(self, message):
        """Handle configuration change notifications."""
        key = message.content.get("key")
        value = message.content.get("value")
        if key:
            old_value = self.config.get(key)
            self.config[key] = value
            print(f"Config updated: {key} = {value} (was: {old_value})")

            # Notify others of the change
            await self.publish_message(
                "CONFIG_UPDATED",
                {"key": key, "old_value": old_value, "new_value": value},
            )

    @command_handler("GET_CONFIG")
    async def get_config(self, command):
        """Get configuration value(s)."""
        key = command.content.get("key") if command.content else None
        if key:
            return {"key": key, "value": self.config.get(key)}
        else:
            return {"config": self.config}

    @command_handler("SET_CONFIG")
    async def set_config(self, command):
        """Set configuration value."""
        key = command.content.get("key")
        value = command.content.get("value")
        if key:
            old_value = self.config.get(key)
            self.config[key] = value
            return {"key": key, "old_value": old_value, "new_value": value}
        else:
            return {"error": "key and value required"}


async def demo_lifecycle_with_messaging():
    """Demo using lifecycle + messaging."""
    print("\n=== Lifecycle + Messaging Demo ===")

    config_service = ConfigurationService()

    # Start service (lifecycle + messaging)
    await config_service.initialize()
    await config_service.start()

    # Test messaging
    await config_service.publish_message(
        "CONFIG_CHANGED", {"key": "debug_mode", "value": "true"}
    )

    # Test commands
    config = await config_service.send_command("GET_CONFIG", config_service.service_id)
    print(f"Current config: {config}")

    result = await config_service.send_command(
        "SET_CONFIG", config_service.service_id, {"key": "cache_size", "value": "2000"}
    )
    print(f"Config update result: {result}")

    await asyncio.sleep(1)  # Let messages process

    # Stop service
    await config_service.stop()


# =============================================================================
# Example 6: Everything (Lifecycle + Tasks + Messaging)
# =============================================================================


class FullDataService(Service):
    """
    A full-featured service with lifecycle, tasks, and messaging.

    This demonstrates the complete Service class with all features.
    """

    def __init__(self):
        super().__init__(component_id="data_service")
        self.data_store: dict[str, str] = {}
        self.processed_count = 0
        self.start_time = time.time()

    async def on_init(self):
        """Initialize the full service."""
        await super().on_init()
        print("Initializing full data service...")
        print("✓ Database connections established")
        print("✓ Cache initialized")
        print("✓ Security configured")

    async def on_start(self):
        """Start the full service (messaging + tasks automatically start)."""
        await super().on_start()
        self.start_time = time.time()
        print("🚀 Full data service is ready!")

    async def on_stop(self):
        """Stop the full service (messaging + tasks automatically stop)."""
        await super().on_stop()
        uptime = time.time() - self.start_time
        print(
            f"📊 Service stopped after {uptime:.1f}s, processed {self.processed_count} items"
        )

    # Messaging handlers
    @message_handler("STORE_DATA")
    async def handle_store_data(self, message):
        """Store data from messages."""
        data = message.content
        key = data.get("key")
        value = data.get("value")

        if key and value:
            self.data_store[key] = value
            self.processed_count += 1
            print(f"📥 Stored: {key} = {value} (total items: {len(self.data_store)})")

            # Acknowledge storage
            await self.publish_message(
                "DATA_STORED",
                {
                    "key": key,
                    "timestamp": time.time(),
                    "total_items": len(self.data_store),
                },
            )

    @command_handler("GET_DATA")
    async def get_data(self, command):
        """Retrieve stored data."""
        key = command.content.get("key") if command.content else None
        if key:
            return {"key": key, "value": self.data_store.get(key)}
        else:
            return {"data": self.data_store}

    @command_handler("GET_STATS")
    async def get_stats(self, command):
        """Get service statistics."""
        return {
            "uptime": time.time() - self.start_time,
            "items_stored": len(self.data_store),
            "items_processed": self.processed_count,
            "status": "running",
        }

    @command_handler("CLEAR_DATA")
    async def clear_data(self, command):
        """Clear all stored data."""
        count = len(self.data_store)
        self.data_store.clear()
        return {"cleared_items": count}

    # Background tasks
    @background_task(interval=8.0)
    async def periodic_stats(self):
        """Report stats every 8 seconds."""
        uptime = time.time() - self.start_time
        print(
            f"📊 Stats - Uptime: {uptime:.1f}s, Items: {len(self.data_store)}, "
            f"Processed: {self.processed_count}"
        )

    @background_task(interval=15.0)
    async def cleanup_old_data(self):
        """Cleanup old data every 15 seconds."""
        if len(self.data_store) > 10:  # Keep only last 10 items
            # Simple cleanup: remove oldest entries
            items = list(self.data_store.items())
            items_to_keep = items[-10:]  # Keep last 10
            self.data_store = dict(items_to_keep)
            print(f"🧹 Cleanup: reduced to {len(self.data_store)} items")

    @background_task(run_once=True)
    async def startup_check(self):
        """One-time startup verification."""
        await asyncio.sleep(1)  # Simulate startup check
        print("✅ Startup verification complete - all systems nominal")


async def demo_full_service():
    """Demo using the full service with everything."""
    print("\n=== Full Service Demo (Everything) ===")

    service = FullDataService()

    # Start full service
    await service.initialize()
    await service.start()

    # Test messaging
    await service.publish_message("STORE_DATA", {"key": "user1", "value": "alice"})
    await service.publish_message("STORE_DATA", {"key": "user2", "value": "bob"})
    await service.publish_message("STORE_DATA", {"key": "user3", "value": "charlie"})

    # Test commands
    data = await service.send_command("GET_DATA", service.service_id)
    print(f"All data: {data}")

    user_data = await service.send_command(
        "GET_DATA", service.service_id, {"key": "user1"}
    )
    print(f"User data: {user_data}")

    stats = await service.send_command("GET_STATS", service.service_id)
    print(f"Service stats: {stats}")

    # Let background tasks run
    print("Letting service run with background tasks...")
    await asyncio.sleep(20)

    # Add more data to test cleanup
    for i in range(15):
        await service.publish_message(
            "STORE_DATA", {"key": f"bulk_{i}", "value": f"data_{i}"}
        )

    await asyncio.sleep(5)

    # Final stats
    final_stats = await service.send_command("GET_STATS", service.service_id)
    print(f"Final stats: {final_stats}")

    # Stop service
    await service.stop()


# =============================================================================
# Demo Runner
# =============================================================================


async def run_all_component_demos():
    """Run all component demonstrations."""
    print("🎭 AIPerf Composable Components Demonstration")
    print("=" * 60)

    # Run each demo
    await demo_background_tasks_only()
    await demo_messaging_only()
    await demo_lifecycle_only()
    await demo_lifecycle_with_tasks()
    await demo_lifecycle_with_messaging()
    await demo_full_service()

    print("\n" + "=" * 60)
    print("🎉 All component demos completed!")
    print("\n🎯 Key Benefits of Composable Design:")
    print("   ✅ Use exactly what you need - no bloat")
    print("   ✅ Clean single inheritance - easy to understand")
    print("   ✅ Mix and match capabilities as needed")
    print("   ✅ Each component has clear responsibilities")
    print("   ✅ Easy to test components independently")
    print("   ✅ Pythonic design patterns throughout")


if __name__ == "__main__":
    asyncio.run(run_all_component_demos())
