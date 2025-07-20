#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Ultimate AIPerf Lifecycle Demo - The New Way

This demo showcases the ULTIMATE user-friendly AIPerf service development experience
using REAL aiperf types and infrastructure while being dramatically simpler.

🎯 What this demo shows:
- ONE class (AIPerfService) that does everything you need
- REAL aiperf types: MessageType, CommandType, Message, CommandMessage
- REAL ZMQ communication via actual aiperf infrastructure
- Clean initialize()/start()/stop() inheritance with super() calls
- Automatic @message_handler/@command_handler discovery
- Type-safe messaging with full IDE support
- Simple publish()/send_command() API methods

🚀 Run this demo:
    python -m aiperf.lifecycle.ultimate_demo

This demo creates two services that communicate using REAL aiperf infrastructure:
1. DataProcessor - Processes data and responds to commands
2. Monitor - Monitors system health and communicates with other services

Both services use the ultimate AIPerfService base class and show how simple
AIPerf service development can be!
"""

import asyncio
import logging
import time
from typing import Any

from aiperf.common.config import ServiceConfig

# Import REAL aiperf types for full type safety
from aiperf.common.enums import (
    CommandType,
    CommunicationBackend,
    MessageType,
    ServiceType,
)
from aiperf.common.messages import CommandMessage, Message

# Import the ULTIMATE API - everything you need!
from aiperf.lifecycle import (
    AIPerfService,
    MessageBus,
    background_task,
    command_handler,
    message_handler,
)

# Setup logging to see the magic happen
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class UltimateDataProcessor(AIPerfService):
    """
    Ultimate data processor showing the new simple approach.

    This service demonstrates:
    - Clean inheritance with standard initialize()/start()/stop()
    - Real aiperf message types (MessageType, CommandType)
    - Automatic decorator discovery and registration
    - Type-safe message and command handling
    - Simple publish() and send_command() methods
    - Real ZMQ communication via aiperf infrastructure

    Notice how SIMPLE this is compared to the old complex mixin approach!
    """

    def __init__(self, service_config: ServiceConfig, **kwargs):
        super().__init__(
            service_id="ultimate_data_processor",
            service_type=ServiceType.DATASET_MANAGER,  # Real ServiceType enum!
            service_config=service_config,
            **kwargs,
        )

        # Business logic state
        self.processed_count = 0
        self.data_cache: list[dict] = []
        self.processing_active = False

    # =================================================================
    # Clean Lifecycle - Standard Python inheritance with super()
    # =================================================================

    async def initialize(self) -> None:
        """Initialize the data processor - just call super() and add your logic!"""
        await super().initialize()  # Handles all aiperf infrastructure setup!

        # Your business logic initialization
        self.processed_count = 0
        self.data_cache.clear()
        self.processing_active = False

        self.logger.info("🔧 Ultimate data processor initialized and ready!")

    async def start(self) -> None:
        """Start the data processor - just call super() and add your logic!"""
        await super().start()  # Handles all messaging and task startup!

        # Your business logic startup
        self.processing_active = True

        self.logger.info("🚀 Ultimate data processor started and processing!")

    async def stop(self) -> None:
        """Stop the data processor - just call super() and add your cleanup!"""
        # Your business logic cleanup
        self.processing_active = False
        self.logger.info(
            f"🛑 Data processor stopping - processed {self.processed_count} items"
        )

        await super().stop()  # Handles all infrastructure cleanup!

    # =================================================================
    # Real aiperf Message Handling - Type Safe!
    # =================================================================

    @message_handler(MessageType.DATASET_CONFIGURED_NOTIFICATION)
    async def handle_dataset_ready(self, message: Message) -> None:
        """Handle real aiperf dataset notification - fully type safe!"""
        self.logger.info("📋 Dataset is ready for processing!")

        # Publish real aiperf status update
        await self.publish(
            MessageType.STATUS,
            service_id=self.service_id,
            service_type=self.service_type,
        )

    @message_handler(MessageType.STATUS)
    async def handle_status_updates(self, message: Message) -> None:
        """Handle real aiperf status messages from other services."""
        sender = getattr(message, "service_id", "unknown")
        self.logger.info(f"📊 Received status update from {sender}")

    # =================================================================
    # Real aiperf Command Handling - Type Safe with Responses!
    # =================================================================

    @command_handler(CommandType.PROFILE_START)
    async def handle_profile_start(self, command: CommandMessage) -> dict[str, Any]:
        """Handle real aiperf profile start command - returns response automatically!"""
        self.logger.info("🎯 Starting profiling session")

        # Business logic
        self.processing_active = True
        start_time = time.time()

        # Return response data - automatically sent back to requester!
        return {
            "status": "profiling_started",
            "processor_id": self.service_id,
            "start_time": start_time,
            "active": self.processing_active,
        }

    @command_handler(CommandType.PROFILE_STOP)
    async def handle_profile_stop(self, command: CommandMessage) -> dict[str, Any]:
        """Handle real aiperf profile stop command."""
        self.logger.info("⏹️ Stopping profiling session")

        # Business logic
        self.processing_active = False
        stop_time = time.time()

        return {
            "status": "profiling_stopped",
            "processor_id": self.service_id,
            "stop_time": stop_time,
            "total_processed": self.processed_count,
        }

    @command_handler(CommandType.PROFILE_CONFIGURE)
    async def handle_configure(self, command: CommandMessage) -> dict[str, Any]:
        """Handle real aiperf configuration command."""
        config_data = command.data or {}
        self.logger.info(f"⚙️ Configuring processor with: {config_data}")

        return {
            "status": "configured",
            "processor_id": self.service_id,
            "config_applied": config_data,
        }

    # =================================================================
    # Automatic Background Tasks - No Complex Management!
    # =================================================================

    @background_task(interval=10.0)
    async def process_data(self) -> None:
        """Simulate data processing - runs automatically every 10 seconds!"""
        if not self.processing_active:
            return

        # Simulate processing some data
        processed_item = {
            "id": self.processed_count,
            "data": f"processed_item_{self.processed_count}",
            "timestamp": time.time(),
            "processor": self.service_id,
        }

        self.processed_count += 1
        self.data_cache.append(processed_item)

        # Keep only last 50 items
        if len(self.data_cache) > 50:
            self.data_cache = self.data_cache[-50:]

        self.logger.info(f"📦 Processed item #{self.processed_count}")

    @background_task(interval=30.0)
    async def send_heartbeat(self) -> None:
        """Send periodic heartbeat - runs automatically every 30 seconds!"""
        await self.publish(
            MessageType.HEARTBEAT,
            service_id=self.service_id,
            service_type=self.service_type,
        )
        self.logger.debug("💓 Heartbeat sent")


class UltimateMonitor(AIPerfService):
    """
    Ultimate monitor showing cross-service communication.

    This service demonstrates:
    - Monitoring other services using real aiperf commands
    - Cross-service communication with type safety
    - Real command/response patterns
    - Simple service coordination
    """

    def __init__(self, service_config: ServiceConfig, **kwargs):
        super().__init__(
            service_id="ultimate_monitor",
            service_type=ServiceType.SYSTEM_CONTROLLER,  # Real ServiceType enum!
            service_config=service_config,
            **kwargs,
        )

        self.monitored_services: set[str] = set()
        self.last_health_check: dict[str, Any] | None = None

    # =================================================================
    # Clean Lifecycle - Standard Python inheritance
    # =================================================================

    async def initialize(self) -> None:
        """Initialize the monitor."""
        await super().initialize()  # All infrastructure handled!

        self.monitored_services.clear()
        self.last_health_check = None

        self.logger.info("👀 Ultimate monitor initialized and watching!")

    async def start(self) -> None:
        """Start monitoring."""
        await super().start()  # All infrastructure handled!

        self.logger.info("🔍 Ultimate monitor started and monitoring system!")

    async def stop(self) -> None:
        """Stop monitoring."""
        self.logger.info(
            f"🔍 Monitor stopping - tracked {len(self.monitored_services)} services"
        )

        await super().stop()  # All infrastructure handled!

    # =================================================================
    # Real aiperf Message Monitoring - Type Safe!
    # =================================================================

    @message_handler(MessageType.HEARTBEAT)
    async def track_heartbeats(self, message: Message) -> None:
        """Track heartbeats from other services."""
        sender = getattr(message, "service_id", "unknown")
        self.monitored_services.add(sender)
        self.logger.debug(f"💓 Heartbeat from {sender}")

    @message_handler(MessageType.STATUS)
    async def track_status_updates(self, message: Message) -> None:
        """Track status updates from other services."""
        sender = getattr(message, "service_id", "unknown")
        self.monitored_services.add(sender)
        self.logger.info(f"📊 Status update from {sender}")

    # =================================================================
    # Cross-Service Communication - Real aiperf Commands!
    # =================================================================

    @command_handler(CommandType.PROFILE_START)
    async def handle_system_profile_start(
        self, command: CommandMessage
    ) -> dict[str, Any]:
        """Handle system-wide profile start by coordinating with other services."""
        self.logger.info("🎯 Starting system-wide profiling")

        health_results = {}

        # Check health of data processor using REAL aiperf command!
        try:
            response = await self.send_command(
                CommandType.PROFILE_START,
                target_service_id="ultimate_data_processor",
                timeout=10.0,
            )
            health_results["data_processor"] = {
                "status": "healthy",
                "response": response,
            }
            self.logger.info("✅ Data processor started profiling successfully")

        except asyncio.TimeoutError:
            health_results["data_processor"] = {
                "status": "timeout",
                "error": "Command timed out",
            }
            self.logger.error("❌ Data processor profile start timed out")
        except Exception as e:
            health_results["data_processor"] = {"status": "error", "error": str(e)}
            self.logger.error(f"❌ Data processor profile start failed: {e}")

        self.last_health_check = health_results

        return {
            "status": "system_profile_started",
            "monitor_id": self.service_id,
            "services_checked": health_results,
            "timestamp": time.time(),
        }

    # =================================================================
    # Automatic System Health Monitoring
    # =================================================================

    @background_task(interval=60.0)
    async def system_health_check(self) -> None:
        """Perform system health check - runs automatically every 60 seconds!"""
        if not self.monitored_services:
            self.logger.info("🔍 No services to monitor yet")
            return

        self.logger.info(
            f"🔍 Performing health check on {len(self.monitored_services)} services"
        )

        # For demo purposes, just check the data processor
        if "ultimate_data_processor" in self.monitored_services:
            try:
                # Send real aiperf command to check configuration
                response = await self.send_command(
                    CommandType.PROFILE_CONFIGURE,
                    target_service_id="ultimate_data_processor",
                    data={"health_check": True},
                    timeout=5.0,
                )
                self.logger.info(f"✅ Data processor health: {response}")

            except Exception as e:
                self.logger.error(f"❌ Data processor health check failed: {e}")


class DemoOrchestrator:
    """Orchestrates the ultimate demo showing real aiperf integration."""

    def __init__(self):
        # Create REAL aiperf service configuration
        self.service_config = ServiceConfig(
            comm_backend=CommunicationBackend.ZMQ_TCP  # Real ZMQ communication!
        )

    async def run_ultimate_demo(self) -> None:
        """Run the ultimate AIPerf lifecycle demo."""
        logger.info("🎭 === ULTIMATE AIPERF LIFECYCLE DEMO ===")
        logger.info("Showcasing the NEW simple way to build AIPerf services!")

        # Create services using the ULTIMATE API
        data_processor = UltimateDataProcessor(self.service_config)
        monitor = UltimateMonitor(self.service_config)

        try:
            logger.info("\n🔧 --- Initializing Services ---")

            # Initialize services - notice how clean this is!
            await data_processor.initialize()
            await monitor.initialize()

            logger.info("\n🚀 --- Starting Services ---")

            # Start services - everything happens automatically!
            await data_processor.start()
            await monitor.start()

            # Wait for services to settle
            await asyncio.sleep(2.0)

            logger.info("\n🎯 --- Demo: Command/Response Patterns ---")

            # Create a demo message bus for orchestration
            demo_bus = MessageBus(service_config=self.service_config)
            await demo_bus.start()

            # Send real aiperf commands to services
            logger.info("Sending PROFILE_START command to data processor...")

            start_response = await demo_bus.send_command(
                CommandType.PROFILE_START,
                target_service_id="ultimate_data_processor",
                service_id="demo_orchestrator",
                timeout=10.0,
            )
            logger.info(f"✅ Profile start response: {start_response}")

            # Wait for some processing
            await asyncio.sleep(5.0)

            logger.info("Sending PROFILE_CONFIGURE command...")

            config_response = await demo_bus.send_command(
                CommandType.PROFILE_CONFIGURE,
                target_service_id="ultimate_data_processor",
                data={"batch_size": 100, "timeout": 30},
                service_id="demo_orchestrator",
                timeout=10.0,
            )
            logger.info(f"✅ Configure response: {config_response}")

            logger.info("\n🔍 --- Demo: Cross-Service Communication ---")

            # Monitor coordinates system-wide profiling
            monitor_response = await demo_bus.send_command(
                CommandType.PROFILE_START,
                target_service_id="ultimate_monitor",
                service_id="demo_orchestrator",
                timeout=15.0,
            )
            logger.info(f"✅ Monitor coordination response: {monitor_response}")

            logger.info("\n⏱️ --- Demo: Background Tasks in Action ---")
            logger.info("Watching automatic background tasks for 15 seconds...")

            # Let background tasks run and show their magic
            await asyncio.sleep(15.0)

            logger.info("\n⏹️ --- Demo: Clean Shutdown ---")

            # Stop everything gracefully
            await demo_bus.send_command(
                CommandType.PROFILE_STOP,
                target_service_id="ultimate_data_processor",
                service_id="demo_orchestrator",
                timeout=10.0,
            )

            await demo_bus.stop()

            logger.info("\n🎉 === DEMO COMPLETE ===")
            logger.info(
                "This showed the ULTIMATE AIPerf service development experience!"
            )
            logger.info("✅ Real aiperf types and infrastructure")
            logger.info("✅ Clean inheritance with super() calls")
            logger.info("✅ Automatic decorator discovery")
            logger.info("✅ Type-safe messaging")
            logger.info("✅ Simple API methods")
            logger.info("✅ Zero complexity - just business logic!")

        finally:
            logger.info("\n🧹 --- Cleaning Up ---")

            # Clean shutdown - notice how simple this is!
            await data_processor.stop()
            await monitor.stop()

            logger.info("✨ Demo cleanup complete")


async def main():
    """Run the ultimate demo."""
    demo = DemoOrchestrator()
    await demo.run_ultimate_demo()


if __name__ == "__main__":
    asyncio.run(main())
