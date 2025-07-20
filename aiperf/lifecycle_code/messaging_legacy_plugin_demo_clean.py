#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Clean demonstration of legacy messaging plugins using the simplified base class.

This demo shows how much simpler plugin development becomes with the new
LegacyPlugin base class that abstracts away all the messaging complexities.

Key improvements:
- Clean inheritance with standard start()/stop() methods
- Automatic decorator discovery and registration
- Simple publish() and send_command() methods
- No manual messaging setup required
- Focus on business logic, not infrastructure
"""

import asyncio
import logging
import time

from aiperf.common.config import ServiceConfig
from aiperf.common.enums import CommunicationBackend
from aiperf.lifecycle.decorators import command_handler, message_handler
from aiperf.lifecycle.legacy_plugin_base import LegacyPlugin
from aiperf.lifecycle.messaging_legacy import Command, Message, MessageBus
from aiperf.lifecycle.plugins import PluginInstance, PluginMetadata

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleDataProcessor(LegacyPlugin):
    """
    Ultra-simple data processor showing the clean base class.

    Notice how clean this is:
    - Just inherit from LegacyPlugin
    - Use decorators for handlers
    - Call super() in start/stop
    - Focus on your logic, not infrastructure
    """

    def __init__(self, service_config: ServiceConfig | None = None, **kwargs):
        super().__init__(
            service_id="simple_data_processor", service_config=service_config, **kwargs
        )
        self.items_processed = 0
        self.recent_items: list[str] = []

    async def start(self) -> None:
        """Start the processor - just call super() and add your logic!"""
        await super().start()  # Handles all messaging setup

        # Your initialization here
        self.items_processed = 0
        self.recent_items.clear()
        self.logger.info("🔧 Simple data processor ready!")

    async def stop(self) -> None:
        """Stop the processor - add your cleanup, then call super()!"""
        # Your cleanup here
        self.logger.info(
            f"🛑 Processor stopping - handled {self.items_processed} items"
        )

        await super().stop()  # Handles all messaging cleanup

    @message_handler("PROCESS_ITEM")
    async def handle_item(self, message: Message) -> None:
        """Process an item - simple decorator, no setup needed!"""
        item = message.content
        self.logger.info(f"📦 Processing item: {item}")

        # Do your processing
        self.items_processed += 1
        self.recent_items.append(str(item))

        # Keep only last 10 items
        if len(self.recent_items) > 10:
            self.recent_items = self.recent_items[-10:]

        # Publish result - simple method call!
        await self.publish(
            "ITEM_PROCESSED",
            {
                "item": item,
                "sequence": self.items_processed,
                "timestamp": time.time(),
            },
        )

    @command_handler("GET_STATS")
    async def get_stats(self, message: Message) -> dict:
        """Get processor statistics - return response directly!"""
        return {
            "total_processed": self.items_processed,
            "recent_items": self.recent_items,
            "status": "healthy",
            "uptime": time.time(),
        }


class SimpleMonitor(LegacyPlugin):
    """
    Ultra-simple monitor showing cross-plugin communication.

    This demonstrates how easy it is to:
    - Monitor other plugins
    - Send commands to other plugins
    - Handle multiple message types
    """

    def __init__(self, service_config: ServiceConfig | None = None, **kwargs):
        super().__init__(
            service_id="simple_monitor", service_config=service_config, **kwargs
        )
        self.events_seen = 0
        self.last_health_check = None

    async def start(self) -> None:
        """Start monitoring - super() handles everything!"""
        await super().start()  # All messaging setup done!

        # Your initialization
        self.events_seen = 0
        self.logger.info("👀 Simple monitor watching system!")

    async def stop(self) -> None:
        """Stop monitoring - cleanup then call super()!"""
        # Your cleanup
        self.logger.info(f"🔍 Monitor stopping - saw {self.events_seen} events")

        await super().stop()  # All messaging cleanup done!

    @message_handler("ITEM_PROCESSED")
    async def track_processing(self, message: Message) -> None:
        """Track processing events - just use the decorator!"""
        self.events_seen += 1
        item_data = message.content

        self.logger.info(
            f"📊 Tracked processing of item {item_data.get('sequence', '?')}"
        )

    @command_handler("CHECK_SYSTEM_HEALTH")
    async def check_health(self, message: Message) -> dict:
        """Check health of other components - simple command sending!"""
        try:
            # Send command to data processor - one line!
            stats = await self.send_command(
                "GET_STATS", "simple_data_processor", timeout=5.0
            )

            health = {
                "overall_status": "healthy",
                "data_processor": {
                    "status": "healthy",
                    "stats": stats,
                },
                "monitor": {
                    "events_tracked": self.events_seen,
                    "status": "healthy",
                },
                "check_time": time.time(),
            }

            self.last_health_check = health
            return health

        except asyncio.TimeoutError:
            return {
                "overall_status": "degraded",
                "data_processor": {"status": "timeout"},
                "check_time": time.time(),
            }
        except Exception as e:
            return {
                "overall_status": "error",
                "error": str(e),
                "check_time": time.time(),
            }

    @command_handler("GET_MONITOR_STATUS")
    async def get_status(self, message: Message) -> dict:
        """Get monitor status."""
        return {
            "events_seen": self.events_seen,
            "last_health_check": self.last_health_check,
            "status": "active",
        }


# Plugin factory functions (fixed to use correct PluginInstance constructor)
def create_data_processor_plugin(
    service_config: ServiceConfig | None = None,
) -> PluginInstance:
    """Factory to create a data processor plugin."""
    component = SimpleDataProcessor(service_config=service_config)

    metadata = PluginMetadata(
        name="simple_data_processor",
        version="1.0.0",
        description="Simple data processor using clean legacy messaging",
        author="AIPerf Team",
    )

    return PluginInstance(
        name="simple_data_processor",
        component=component,
        metadata=metadata,
        module_path=__file__,
    )


def create_monitor_plugin(
    service_config: ServiceConfig | None = None,
) -> PluginInstance:
    """Factory to create a monitor plugin."""
    component = SimpleMonitor(service_config=service_config)

    metadata = PluginMetadata(
        name="simple_monitor",
        version="1.0.0",
        description="Simple monitor using clean legacy messaging",
        author="AIPerf Team",
    )

    return PluginInstance(
        name="simple_monitor",
        component=component,
        metadata=metadata,
        module_path=__file__,
    )


class DemoOrchestrator:
    """Demo orchestrator that shows the plugins working together."""

    def __init__(self):
        self.service_config = ServiceConfig(comm_backend=CommunicationBackend.ZMQ_TCP)
        self.plugins: list[PluginInstance] = []
        self.demo_bus = MessageBus(service_config=self.service_config)

    async def run_demo(self) -> None:
        """Run the complete clean plugin demo."""
        logger.info("🎭 === Clean Legacy Plugin Demo ===")
        logger.info(
            "This demo shows how simple plugins become with the new base class!"
        )

        try:
            await self._setup_plugins()
            await self._demo_scenarios()
        finally:
            await self._cleanup()

    async def _setup_plugins(self) -> None:
        """Set up plugins using the correct PluginInstance structure."""
        logger.info("🔧 --- Setting up plugins ---")

        # Create plugin instances (fixed constructors)
        data_processor = create_data_processor_plugin(self.service_config)
        monitor = create_monitor_plugin(self.service_config)

        self.plugins = [data_processor, monitor]

        # Start all plugins - notice how clean this is!
        for plugin_instance in self.plugins:
            await plugin_instance.component.start()  # Fixed: use .component

        # Start demo message bus
        await self.demo_bus.start()

        # Wait for initialization
        await asyncio.sleep(1.0)

        logger.info("✅ All plugins started successfully!")

    async def _demo_scenarios(self) -> None:
        """Run various demo scenarios."""

        # Scenario 1: Basic message processing
        logger.info("\n📦 --- Scenario 1: Basic Processing ---")

        test_items = ["apple", "banana", "cherry", "date"]
        for item in test_items:
            await self.demo_bus.publish(
                Message(
                    type="PROCESS_ITEM",
                    content=item,
                    sender_id="demo_orchestrator",
                )
            )
            await asyncio.sleep(0.5)  # Space out the items

        logger.info(f"Sent {len(test_items)} items for processing")

        # Wait for processing
        await asyncio.sleep(2.0)

        # Scenario 2: Query plugin status
        logger.info("\n📊 --- Scenario 2: Status Queries ---")

        # Get data processor stats
        try:
            stats_command = Command(
                type="GET_STATS",
                sender_id="demo_orchestrator",
                target_id="simple_data_processor",
                timeout=5.0,
            )

            stats = await self.demo_bus.send_command(stats_command)
            logger.info(f"📈 Data processor stats: {stats}")

        except asyncio.TimeoutError:
            logger.error("❌ Stats query timed out")

        # Scenario 3: Health check via monitor
        logger.info("\n🏥 --- Scenario 3: Health Monitoring ---")

        try:
            health_command = Command(
                type="CHECK_SYSTEM_HEALTH",
                sender_id="demo_orchestrator",
                target_id="simple_monitor",
                timeout=10.0,
            )

            health = await self.demo_bus.send_command(health_command)
            logger.info(f"💚 System health: {health.get('overall_status', 'unknown')}")
            logger.info(
                f"🔍 Data processor status: {health.get('data_processor', {}).get('status', 'unknown')}"
            )

        except asyncio.TimeoutError:
            logger.error("❌ Health check timed out")

        # Scenario 4: Monitor status
        logger.info("\n👀 --- Scenario 4: Monitor Status ---")

        try:
            monitor_command = Command(
                type="GET_MONITOR_STATUS",
                sender_id="demo_orchestrator",
                target_id="simple_monitor",
                timeout=5.0,
            )

            monitor_status = await self.demo_bus.send_command(monitor_command)
            logger.info(
                f"👁️ Monitor tracked: {monitor_status.get('events_seen', 0)} events"
            )

        except asyncio.TimeoutError:
            logger.error("❌ Monitor status query timed out")

        logger.info("\n🎉 --- All scenarios completed! ---")

    async def _cleanup(self) -> None:
        """Clean up all resources."""
        logger.info("\n🧹 --- Cleaning up ---")

        # Stop all plugins
        for plugin_instance in self.plugins:
            await plugin_instance.component.stop()  # Fixed: use .component

        # Stop demo bus
        await self.demo_bus.stop()

        logger.info("✨ Demo cleanup complete")


async def demo_comparison():
    """Show the difference between old and new approaches."""
    logger.info("\n🔄 === Old vs New Comparison ===")

    logger.info("""
📝 OLD WAY (Complex):
   class MyPlugin(LegacyMessagingBase):
       async def start(self):
           await self.start_messaging()  # Manual call
           # Your logic

       async def _handle_targeted_message(self, message):
           # Complex message routing

       async def _setup_message_handling(self):
           # Manual subscription setup

🚀 NEW WAY (Simple):
   class MyPlugin(LegacyPlugin):
       async def start(self):
           await super().start()  # Standard inheritance!
           # Your logic - that's it!

       @message_handler("DATA")
       async def handle_data(self, message):
           # Just use decorators - everything else automatic!

✨ Benefits:
   • Standard start()/stop() inheritance chains
   • No manual messaging method calls
   • Automatic decorator discovery
   • Focus on business logic, not infrastructure
   • Clean, intuitive API
   • Less code, fewer bugs!
""")


async def main():
    """Run the complete demonstration."""
    # Show the comparison first
    await demo_comparison()

    # Run the actual demo
    demo = DemoOrchestrator()
    await demo.run_demo()


if __name__ == "__main__":
    asyncio.run(main())
