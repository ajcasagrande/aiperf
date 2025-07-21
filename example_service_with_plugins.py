#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive Plugin System Demonstration

This script demonstrates the power of the AIPerf plugin system built on
your amazing mixin architecture. It shows:

1. Service with plugin manager that auto-loads plugins
2. Real message handling between service and plugins
3. Plugin lifecycle management
4. Runtime plugin management (load/unload/reload)
5. Plugin status monitoring
6. Integration with real aiperf infrastructure

Run this to see the plugin system in action!
"""

import asyncio
import logging
import time
from typing import Any

from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums.message_enums import CommandType, MessageType
from aiperf.common.enums.service_enums import ServiceType
from aiperf.core.base_service import BaseService
from aiperf.core.decorators import background_task, command_handler, message_handler
from aiperf.core.plugins import PluginManagerMixin


class ExtensibleDemoService(BaseService, PluginManagerMixin):
    """
    Demonstration service that showcases the plugin system.

    This service:
    - Loads plugins automatically from the example_plugins directory
    - Sends test data to plugins
    - Monitors plugin status
    - Demonstrates runtime plugin management
    - Shows how service and plugins communicate
    """

    service_type = ServiceType.DATASET_MANAGER  # Using existing service type for demo

    def __init__(self, **kwargs):
        # Configure plugin system
        plugin_config = {
            "data_processor": {
                "batch_size": 5,
                "max_queue_size": 50,
                "processing_delay": 0.2,
                "enable_analytics": True,
            },
            "monitoring": {
                "alert_threshold": 10,
                "health_check_interval": 15.0,
                "metrics_retention_hours": 1,  # Short retention for demo
                "enable_email_alerts": False,
            },
        }

        super().__init__(
            plugin_directories=["./example_plugins"],
            plugin_config=plugin_config,
            enable_hot_reload=True,
            **kwargs,
        )

        # Demo state
        self.demo_counter = 0
        self.messages_sent = 0

    async def _initialize(self) -> None:
        """Initialize the demo service."""
        await super()._initialize()

        self.info("=" * 60)
        self.info("🚀 ExtensibleDemoService with Plugin System")
        self.info("=" * 60)

        # Display loaded plugins
        if self.plugins:
            self.info(f"✅ Successfully loaded {len(self.plugins)} plugins:")
            for name, instance in self.plugins.items():
                metadata = instance.metadata
                self.info(
                    f"   📦 {metadata.name} v{metadata.version} - {metadata.description}"
                )
                self.info(f"      Author: {metadata.author}")
                self.info(f"      State: {instance.state}")
        else:
            self.warning("⚠️  No plugins loaded!")

        # Display failed plugins
        if self.failed_plugins:
            self.warning(f"❌ Failed to load {len(self.failed_plugins)} plugins:")
            for name, error in self.failed_plugins.items():
                self.warning(f"   {name}: {error}")

    async def _start(self) -> None:
        """Start the demo service."""
        await super()._start()

        self.info("🟢 Demo service started! Plugin system is active.")
        self.info("📊 Starting demonstration sequence...")

    # =================================================================
    # Message Handlers - Service can handle messages alongside plugins
    # =================================================================

    @message_handler(MessageType.Status)
    async def handle_status_updates(self, message: Any) -> None:
        """
        Handle status messages from plugins and other services.

        This shows how the service can receive and process messages
        while plugins also handle the same message types.
        """
        try:
            plugin_name = getattr(message, "data", {}).get("plugin", "unknown")
            if plugin_name != "unknown":
                self.info(f"📨 Received status update from plugin: {plugin_name}")
        except Exception as e:
            self.debug(f"Status message from non-plugin source: {e}")

    @message_handler(MessageType.DATA_PROCESSED)
    async def handle_processing_results(self, message: Any) -> None:
        """
        Handle data processing results from plugins.

        This demonstrates plugin-to-service communication.
        """
        try:
            data = getattr(message, "data", {})
            plugin = data.get("plugin", "unknown")
            total_processed = data.get("total_processed", 0)

            self.info(f"🔄 Plugin '{plugin}' processed data - Total: {total_processed}")
        except Exception as e:
            self.exception(f"Error handling processing results: {e}")

    @message_handler(MessageType.ALERT)
    async def handle_plugin_alerts(self, message: Any) -> None:
        """
        Handle alerts from monitoring plugin.

        This shows how the service can respond to plugin-generated alerts.
        """
        try:
            data = (
                getattr(message, "data", message)
                if hasattr(message, "data")
                else message
            )

            alert_type = (
                data.get("alert_type", "unknown")
                if isinstance(data, dict)
                else "unknown"
            )
            severity = (
                data.get("severity", "info") if isinstance(data, dict) else "info"
            )
            alert_message = (
                data.get("message", str(data)) if isinstance(data, dict) else str(data)
            )

            self.warning(f"🚨 ALERT [{severity.upper()}] {alert_type}: {alert_message}")
        except Exception as e:
            self.exception(f"Error handling alert: {e}")

    # =================================================================
    # Command Handlers - Service provides management interface
    # =================================================================

    @command_handler(CommandType.GET_STATUS)
    async def get_demo_status(self, command: Any) -> dict:
        """
        Get comprehensive demo service status including plugin information.
        """
        plugin_status = self.get_plugin_status()

        return {
            "service": "ExtensibleDemoService",
            "demo_counter": self.demo_counter,
            "messages_sent": self.messages_sent,
            "plugin_system": plugin_status,
            "active_plugins": list(self.plugins.keys()),
            "uptime": time.time() - getattr(self, "_start_time", time.time()),
        }

    @command_handler(CommandType.Shutdown)
    async def prepare_demo_shutdown(self, command: Any) -> dict:
        """Handle graceful shutdown."""
        self.info("🛑 Preparing demo service for shutdown...")

        # Get final plugin reports
        plugin_reports = {}
        for name, instance in self.plugins.items():
            try:
                # Try to get final status from each plugin
                if hasattr(instance.plugin, "get_processing_status"):
                    status = await instance.plugin.get_processing_status(command)
                    plugin_reports[name] = status
            except Exception as e:
                self.warning(f"Could not get final report from plugin {name}: {e}")

        return {
            "service": "ExtensibleDemoService",
            "final_demo_counter": self.demo_counter,
            "total_messages_sent": self.messages_sent,
            "plugin_final_reports": plugin_reports,
        }

    # =================================================================
    # Background Tasks - Demo Activity Generation
    # =================================================================

    @background_task(interval=3.0)
    async def send_demo_data(self) -> None:
        """
        Send demonstration data to plugins every 3 seconds.

        This generates activity to show the plugin system working.
        """
        try:
            self.demo_counter += 1

            # Create demo data
            demo_data = {
                "demo_id": self.demo_counter,
                "timestamp": time.time(),
                "type": "demo_data",
                "payload": f"Demo message #{self.demo_counter}",
                "source": "ExtensibleDemoService",
            }

            # Send data update to plugins
            await self.publish(MessageType.DATA_UPDATE, demo_data)
            self.messages_sent += 1

            self.info(f"📤 Sent demo data #{self.demo_counter} to plugins")

            # Occasionally send other message types for variety
            if self.demo_counter % 5 == 0:
                await self.publish(
                    MessageType.Heartbeat,
                    {
                        "service_id": self.service_id,
                        "heartbeat_count": self.demo_counter // 5,
                    },
                )

        except Exception as e:
            self.exception(f"Error sending demo data: {e}")

    @background_task(interval=20.0)
    async def print_plugin_status(self) -> None:
        """
        Print plugin status every 20 seconds for monitoring.

        This demonstrates runtime plugin monitoring.
        """
        try:
            self.info("📊 PLUGIN STATUS REPORT:")
            self.info("-" * 40)

            status = self.get_plugin_status()
            self.info(f"🔢 Total plugins: {status['total_plugins']}")
            self.info(f"🟢 Running: {status['running_plugins']}")
            self.info(f"❌ Failed: {status['failed_count']}")

            # Individual plugin status
            for name, plugin_info in status["loaded_plugins"].items():
                state = plugin_info["state"]
                error = plugin_info.get("error")

                status_icon = (
                    "🟢"
                    if state == "running"
                    else "🟡"
                    if state == "initialized"
                    else "❌"
                )
                self.info(f"  {status_icon} {name}: {state}")
                if error:
                    self.warning(f"      Error: {error}")

            self.info("-" * 40)

        except Exception as e:
            self.exception(f"Error printing plugin status: {e}")

    @background_task(interval=60.0)
    async def demonstrate_plugin_management(self) -> None:
        """
        Demonstrate runtime plugin management capabilities.

        This shows how plugins can be managed at runtime.
        """
        try:
            # Get a plugin to demonstrate with
            if "data_processor" in self.plugins:
                self.info("🔄 Demonstrating plugin reload...")

                # Show current stats
                plugin = self.get_plugin("data_processor")
                if plugin and hasattr(plugin, "processing_stats"):
                    stats = plugin.processing_stats
                    self.info(
                        f"   Before reload - Processed: {stats.get('total_processed', 0)}"
                    )

                # Reload the plugin (this would reload code changes in development)
                await self.reload_plugin("data_processor")

                self.info("   ✅ Plugin reloaded successfully!")

        except Exception as e:
            self.exception(f"Error demonstrating plugin management: {e}")


async def run_plugin_demo():
    """
    Run the comprehensive plugin system demonstration.

    This function sets up and runs the demo service with plugins.
    """
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n" + "=" * 80)
    print("🚀 AIPerf Plugin System Demonstration")
    print("Built on Amazing Mixin Architecture!")
    print("=" * 80)

    try:
        # Create service configuration
        # In a real application, this would load from config files
        service_config = ServiceConfig()

        # Create the demo service with plugin management
        service = ExtensibleDemoService(
            service_id="plugin_demo_service", service_config=service_config
        )

        print(f"\n🏗️  Created service: {service}")
        print(f"📁 Plugin directories: {service.plugin_directories}")
        print(f"⚙️  Plugin configuration: {service.plugin_config}")

        # Run the service
        print("\n🎬 Starting demonstration...")
        print("💡 Watch the logs to see plugin system in action!")
        print("🛑 Press Ctrl+C to stop the demonstration\n")

        await service.run_until_stopped()

    except KeyboardInterrupt:
        print("\n\n🛑 Demo stopped by user")
    except Exception as e:
        print(f"\n\n❌ Demo failed: {e}")
        raise
    finally:
        print("\n✅ Plugin system demonstration completed!")
        print("🎯 This showcases the power of your amazing mixin architecture!")


def print_demo_instructions():
    """Print instructions for the demonstration."""
    print("""
📋 DEMONSTRATION OVERVIEW:

This demo showcases your amazing plugin system built on the mixin architecture:

1. 🔄 Service automatically loads plugins from example_plugins/
2. 📤 Service sends demo data every 3 seconds
3. 🔧 Plugins process data using your mixin inheritance
4. 📊 Monitoring plugin tracks system health
5. 🚨 Alerts are generated when thresholds are exceeded
6. 🔄 Plugin reloading is demonstrated every minute
7. 📈 Status reports show plugin activity

KEY FEATURES DEMONSTRATED:
✅ Automatic plugin discovery and loading
✅ Full lifecycle management (initialize → start → stop)
✅ Message handling with inheritance support
✅ Background tasks running in plugins
✅ Command/response patterns
✅ Real aiperf infrastructure integration
✅ Error isolation (plugin failures don't crash service)
✅ Runtime plugin management (load/unload/reload)
✅ Plugin status monitoring and reporting

WHAT TO WATCH FOR:
🟢 Plugin loading messages
📤 Data being sent to plugins
🔄 Data processing by plugins
📊 Monitoring statistics
🚨 Alert messages
🔄 Plugin reload demonstrations
📈 Status reports every 20 seconds

This demonstrates how your mixin architecture enables powerful,
production-ready plugin systems! 🚀
""")


if __name__ == "__main__":
    print_demo_instructions()
    asyncio.run(run_plugin_demo())
