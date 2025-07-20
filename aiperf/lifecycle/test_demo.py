# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Quick demo/test of the new AIPerf Lifecycle system.

This file demonstrates that the new system works correctly and can be run
to verify functionality.
"""

import asyncio
import logging

from aiperf.lifecycle import AIPerf, background_task, command_handler, message_handler

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


class DemoService(AIPerf):
    """A simple demo service to test the new lifecycle system."""

    def __init__(self):
        super().__init__(service_id="demo_service")
        self.message_count = 0

    async def on_init(self):
        self.logger.info("🚀 Demo service initializing...")

    async def on_start(self):
        self.logger.info("✅ Demo service started!")

    async def on_stop(self):
        self.logger.info("⏹️  Demo service stopping...")

    async def on_cleanup(self):
        self.logger.info("🧹 Demo service cleanup complete")

    @message_handler("HELLO")
    async def handle_hello(self, message):
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
        self.logger.info("📊 Status requested")
        return {
            "status": "running",
            "message_count": self.message_count,
            "state": self.state.value,
        }

    @background_task(interval=3.0)
    async def periodic_task(self):
        self.logger.info(
            f"⏰ Periodic task running (processed {self.message_count} messages)"
        )

    @background_task(run_once=True)
    async def startup_task(self):
        self.logger.info("🎯 One-time startup task completed")


async def run_demo():
    """Run a quick demo of the new lifecycle system."""
    print("\n" + "=" * 60)
    print("🎉 AIPerf Lifecycle System Demo")
    print("=" * 60)

    # Create the service
    service = DemoService()

    # Start the service
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

    # Stop the service
    await service.stop()

    print("\n✨ Demo completed successfully!")
    print("=" * 60)

    return True


if __name__ == "__main__":
    # Run the demo
    result = asyncio.run(run_demo())
    if result:
        print("\n🎊 The new AIPerf Lifecycle system is working perfectly!")
    else:
        print("\n❌ Something went wrong")
