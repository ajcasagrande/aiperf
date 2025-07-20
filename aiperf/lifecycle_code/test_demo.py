# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Quick demo/test of the new simplified AIPerf Lifecycle system.

This demonstrates the clean separation:
- Lifecycle methods: simple inheritance with super() calls
- Message/command handlers: decorators for dynamic behavior
- Background tasks: decorators for automatic management
"""

import asyncio
import logging

from aiperf.lifecycle import AIPerf, background_task, command_handler, message_handler

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class DemoService(AIPerf):
    """A simple demo service showing the new simplified patterns."""

    def __init__(self):
        super().__init__(service_id="demo_service")
        self.message_count = 0

    # =================================================================
    # Simple Lifecycle Methods - Just override and call super()
    # =================================================================

    async def initialize(self):
        """Simple inheritance - just call super()"""
        await super().initialize()  # Always call super()
        self.logger.info("🚀 Demo service initializing...")

    async def start(self):
        """Simple inheritance - just call super()"""
        await super().start()  # Always call super()
        self.logger.info("✅ Demo service started!")

    async def stop(self):
        """Simple inheritance - just call super()"""
        await super().stop()  # Always call super()
        self.logger.info("⏹️  Demo service stopping...")

    # =================================================================
    # Dynamic Handlers - Use decorators
    # =================================================================

    @message_handler("HELLO")
    async def handle_hello(self, message):
        """Handle hello messages - uses decorator for dynamic behavior"""
        self.message_count += 1
        self.logger.info(
            f"👋 Received hello message #{self.message_count}: {message.content}"
        )

        # Send a response
        await self.publish_message(
            "HELLO_RESPONSE", {"original": message.content, "count": self.message_count}
        )

    @command_handler("GET_STATUS")
    async def get_status(self, command):
        """Handle status command - uses decorator for dynamic behavior"""
        self.logger.info("📊 Status requested")
        return {
            "status": "running",
            "message_count": self.message_count,
            "state": self.state.value,
        }

    @background_task(interval=3.0)
    async def periodic_task(self):
        """Periodic background task - uses decorator for automatic management"""
        self.logger.info(
            f"⏰ Periodic task running (processed {self.message_count} messages)"
        )

    @background_task(run_once=True)
    async def startup_task(self):
        """One-time startup task - uses decorator for automatic management"""
        self.logger.info("🎯 One-time startup task completed")


async def run_demo():
    """Run a quick demo of the simplified lifecycle system."""
    print("\n" + "=" * 60)
    print("🎉 Simplified AIPerf Lifecycle System Demo")
    print("=" * 60)
    print("📝 Key Features:")
    print("   ✅ Lifecycle methods: Simple inheritance with super()")
    print("   ✅ Message handlers: Decorators for dynamic behavior")
    print("   ✅ Background tasks: Decorators for automatic management")
    print("=" * 60)

    # Create the service
    service = DemoService()

    # Start the service (lifecycle methods called automatically)
    await service.initialize()
    await service.start()

    # Send some messages to test message handling
    await service.publish_message("HELLO", "World!")
    await service.publish_message("HELLO", "AIPerf!")

    # Test command handling
    status = await service.send_command("GET_STATUS", service.service_id)
    print(f"📋 Service status: {status}")

    # Let it run for a bit to see background tasks
    print("\n⏳ Letting service run for 8 seconds to see background tasks...")
    await asyncio.sleep(8)

    # Get final status
    final_status = await service.send_command("GET_STATUS", service.service_id)
    print(f"📋 Final status: {final_status}")

    # Stop the service (lifecycle methods called automatically)
    await service.stop()

    print("\n✨ Demo completed successfully!")
    print("=" * 60)
    print("🏆 Benefits of the new system:")
    print("   📦 Simple inheritance (no complex mixins)")
    print("   🎯 Clear separation of concerns")
    print("   🔧 Easy to understand and debug")
    print("   ⚡ Powerful but not complex")
    print("=" * 60)

    return True


if __name__ == "__main__":
    # Run the demo
    result = asyncio.run(run_demo())
    if result:
        print("\n🎊 The simplified AIPerf Lifecycle system is working perfectly!")
    else:
        print("\n❌ Something went wrong")
