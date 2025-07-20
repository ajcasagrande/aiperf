# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive demonstration of the AIPerf Plugin System.

This script shows how to:
1. Set up the plugin manager
2. Create plugins dynamically
3. Load and manage plugins
4. Communicate between plugins
5. Handle plugin lifecycle
6. Query plugin status

The plugin system integrates seamlessly with the AIPerf lifecycle and
messaging systems, allowing plugins to communicate with each other and
the main application.
"""

import asyncio
import time
from pathlib import Path

from aiperf.lifecycle_code import (
    PluginManager,
    Service,
    background_task,
    command_handler,
    load_and_start_plugins,
    message_handler,
)


class MainApplication(Service):
    """
    Main application that coordinates with plugins.

    This demonstrates how the main application can interact with
    dynamically loaded plugins through the messaging system.
    """

    def __init__(self):
        super().__init__(component_id="main_app")
        self.plugin_responses = []
        self.data_sent = 0

    async def initialize(self):
        await super().initialize()
        self.logger.info("🚀 Main application initialized")

    async def start(self):
        await super().start()
        self.logger.info("🎯 Main application started - ready to work with plugins")

    @message_handler("HELLO_RESPONSE")
    async def handle_hello_response(self, message):
        """Handle responses from the hello world plugin."""
        response = message.content.get("response", "")
        count = message.content.get("count", 0)

        self.plugin_responses.append(response)
        self.logger.info(f"📨 Received plugin response: {response}")

    @message_handler("DATA_PROCESSED")
    async def handle_data_processed(self, message):
        """Handle notifications from the data processor plugin."""
        processed_count = message.content.get("processed_count", 0)
        remaining = message.content.get("remaining", 0)

        self.logger.info(
            f"📊 Data processed - Total: {processed_count}, Remaining: {remaining}"
        )

    @message_handler("PERIODIC_HELLO")
    async def handle_periodic_hello(self, message):
        """Handle periodic messages from plugins."""
        msg = message.content.get("message", "")
        self.logger.info(f"📡 Periodic plugin message: {msg}")

    @background_task(interval=8.0)
    async def send_data_to_plugins(self):
        """Periodically send data to plugins for processing."""
        self.data_sent += 1

        # Send hello to hello world plugin
        await self.publish_message(
            "HELLO",
            {"sender": "main_app", "message": f"Hello from main app #{self.data_sent}"},
        )

        # Send data to data processor plugin
        await self.publish_message(
            "PROCESS_DATA",
            {
                "id": f"data_{self.data_sent}",
                "type": "user_action",
                "payload": {"user_id": 123, "action": "login"},
                "timestamp": time.time(),
            },
        )

        self.logger.info(f"📤 Sent data #{self.data_sent} to plugins")

    @command_handler("GET_APP_STATUS")
    async def get_app_status(self, command):
        """Get status of the main application."""
        return {
            "status": "running",
            "data_sent": self.data_sent,
            "plugin_responses": len(self.plugin_responses),
            "latest_responses": self.plugin_responses[-3:]
            if self.plugin_responses
            else [],
        }


async def create_custom_plugin():
    """Create a custom plugin on the fly to demonstrate dynamic capabilities."""

    plugins_dir = Path("plugins")
    custom_plugin_dir = plugins_dir / "custom_monitor"
    custom_plugin_dir.mkdir(parents=True, exist_ok=True)

    custom_plugin_content = '''# Custom Monitor Plugin (Created Dynamically)
from aiperf.lifecycle import Service, message_handler, command_handler, background_task
import time
import random

class CustomMonitorService(Service):
    """A dynamically created monitoring plugin."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics = {"cpu": 0.0, "memory": 0.0, "network": 0.0}
        self.alert_count = 0

    async def initialize(self):
        await super().initialize()
        self.logger.info("🔍 Custom monitor plugin initialized!")

    @message_handler("DATA_PROCESSED")
    async def monitor_data_processing(self, message):
        """Monitor data processing events."""
        processed_count = message.content.get("processed_count", 0)

        if processed_count % 3 == 0:  # Alert every 3 processed items
            self.alert_count += 1
            await self.publish_message("MONITOR_ALERT", {
                "type": "processing_milestone",
                "message": f"Processed {processed_count} items!",
                "alert_number": self.alert_count,
                "timestamp": time.time()
            })

    @background_task(interval=6.0)
    async def collect_system_metrics(self):
        """Simulate collecting system metrics."""
        self.metrics["cpu"] = random.uniform(10, 90)
        self.metrics["memory"] = random.uniform(20, 80)
        self.metrics["network"] = random.uniform(1, 100)

        self.logger.info(f"📊 Metrics - CPU: {self.metrics['cpu']:.1f}%, "
                        f"Memory: {self.metrics['memory']:.1f}%, "
                        f"Network: {self.metrics['network']:.1f} Mbps")

        # Send alert if CPU is high
        if self.metrics["cpu"] > 75:
            await self.publish_message("MONITOR_ALERT", {
                "type": "high_cpu",
                "message": f"High CPU usage: {self.metrics['cpu']:.1f}%",
                "metrics": self.metrics,
                "timestamp": time.time()
            })

    @command_handler("GET_METRICS")
    async def get_metrics(self, command):
        """Get current system metrics."""
        return {
            "metrics": self.metrics,
            "alert_count": self.alert_count,
            "uptime": time.time()
        }

# Plugin exports
PLUGIN_COMPONENTS = [CustomMonitorService]

PLUGIN_METADATA = {
    "name": "Custom Monitor Plugin",
    "version": "1.0.0",
    "description": "Dynamically created monitoring plugin",
    "author": "Demo System",
    "provides_services": ["system_monitoring", "alerting"]
}
'''

    (custom_plugin_dir / "plugin.py").write_text(custom_plugin_content)
    print(f"✅ Created custom plugin at {custom_plugin_dir}")


async def demonstrate_plugin_system():
    """Complete demonstration of the plugin system."""
    print("🎭 AIPerf Plugin System Demonstration")
    print("=" * 60)

    # Create a custom plugin dynamically
    await create_custom_plugin()

    # Method 1: Use the convenience function
    print("\n1️⃣ Starting plugins with convenience function...")
    plugin_manager = await load_and_start_plugins("plugins", auto_reload=False)

    # Start the main application
    main_app = MainApplication()
    await main_app.initialize()
    await main_app.start()

    print("✅ All components started!")

    # Query plugin status
    print("\n2️⃣ Querying plugin status...")
    plugins_list = await plugin_manager.send_command(
        "LIST_PLUGINS", plugin_manager.service_id
    )
    print(f"📋 Loaded {plugins_list['total_plugins']} plugins:")

    for plugin in plugins_list["plugins"]:
        print(f"   • {plugin['name']} ({plugin['type']}) - {plugin['state']}")
        print(f"     Description: {plugin['metadata']['description']}")

    # Get detailed status of a specific plugin
    print("\n3️⃣ Getting detailed plugin status...")
    for plugin in plugins_list["plugins"]:
        if "hello_world" in plugin["name"].lower():
            status = await plugin_manager.send_command(
                "GET_PLUGIN_STATUS",
                plugin_manager.service_id,
                {"plugin_name": plugin["name"]},
            )
            print(f"📊 Detailed status for {plugin['name']}:")
            print(f"   Type: {status['type']}")
            print(f"   State: {status['state']}")
            print(f"   Service ID: {status['component_info']['service_id']}")
            break

    # Let the system run and demonstrate inter-plugin communication
    print("\n4️⃣ Running system - watching inter-plugin communication...")
    print("   (Main app will send data to plugins, plugins will respond)")

    # Set up monitoring for plugin messages
    monitor_messages = []

    @message_handler("MONITOR_ALERT")
    async def handle_monitor_alert(message):
        alert_type = message.content.get("type", "unknown")
        alert_msg = message.content.get("message", "")
        monitor_messages.append(f"{alert_type}: {alert_msg}")
        print(f"🚨 Monitor Alert - {alert_type}: {alert_msg}")

    # Add the handler to main app (normally you'd do this with decorators)
    main_app._message_handlers.setdefault("MONITOR_ALERT", []).append(
        handle_monitor_alert
    )

    # Let the system run for a while
    print("⏳ Running for 20 seconds...")
    await asyncio.sleep(20)

    # Query final status
    print("\n5️⃣ Final status check...")
    app_status = await main_app.send_command("GET_APP_STATUS", main_app.service_id)
    print("📊 Main app status:")
    print(f"   Data sent: {app_status['data_sent']}")
    print(f"   Plugin responses: {app_status['plugin_responses']}")

    # Get metrics from custom monitor plugin
    for plugin in plugins_list["plugins"]:
        if "custom_monitor" in plugin["name"].lower():
            try:
                metrics = await main_app.send_command("GET_METRICS", plugin["name"])
                print("📊 Custom monitor metrics:")
                print(f"   CPU: {metrics['metrics']['cpu']:.1f}%")
                print(f"   Memory: {metrics['metrics']['memory']:.1f}%")
                print(f"   Alerts: {metrics['alert_count']}")
            except Exception as e:
                print(f"   Could not get metrics: {e}")
            break

    print(f"\n🚨 Monitor alerts received: {len(monitor_messages)}")
    for alert in monitor_messages[-3:]:  # Show last 3 alerts
        print(f"   • {alert}")

    # Test plugin reload
    print("\n6️⃣ Testing plugin reload...")
    reload_result = await plugin_manager.send_command(
        "RELOAD_PLUGINS", plugin_manager.service_id
    )
    print(f"🔄 Reload result: {reload_result['message']}")
    print(
        f"   Loaded: {reload_result['loaded_plugins']}, Failed: {reload_result['failed_plugins']}"
    )

    # Stop everything
    print("\n7️⃣ Stopping all components...")
    await main_app.stop()
    await plugin_manager.stop()

    print("\n" + "=" * 60)
    print("🎉 Plugin system demonstration completed!")

    print("\n🎯 Key Features Demonstrated:")
    print("   ✅ Dynamic plugin discovery and loading")
    print("   ✅ Automatic lifecycle management for plugins")
    print("   ✅ Inter-plugin communication via messaging")
    print("   ✅ Plugin status monitoring and querying")
    print("   ✅ Hot reloading of plugins")
    print("   ✅ Error isolation and handling")
    print("   ✅ Integration with main application")


async def demonstrate_manual_plugin_management():
    """Demonstrate manual plugin management for more control."""
    print("\n🔧 Manual Plugin Management Demo")
    print("-" * 40)

    # Create plugin manager manually
    plugin_manager = PluginManager(plugins_dir="plugins", auto_reload=True)

    print("📋 Manual plugin manager lifecycle:")

    # Initialize
    await plugin_manager.initialize()
    print("   ✅ Plugin manager initialized")

    # Start (this discovers and starts plugins)
    await plugin_manager.start()
    print("   🚀 Plugin manager started - plugins discovered and loaded")

    # List plugins
    plugins = await plugin_manager.send_command(
        "LIST_PLUGINS", plugin_manager.service_id
    )
    print(f"   📊 Found {plugins['total_plugins']} plugins")

    # Let auto-reload monitor for a bit
    print("   👀 Auto-reload monitoring active...")
    await asyncio.sleep(5)

    # Stop
    await plugin_manager.stop()
    print("   🛑 Plugin manager stopped - all plugins stopped")

    print("✅ Manual management demo complete!")


if __name__ == "__main__":
    # Run the main demonstration
    asyncio.run(demonstrate_plugin_system())

    # Show manual management approach
    asyncio.run(demonstrate_manual_plugin_management())
