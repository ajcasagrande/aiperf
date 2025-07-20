#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
# Example Hello World Plugin
from aiperf.lifecycle import Service, background_task, message_handler


class HelloWorldService(Service):
    """A simple example plugin that responds to greetings."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.greeting_count = 0

    async def on_init(self):
        await super().on_init()
        self.logger.info("Hello World plugin initialized!")

    async def on_start(self):
        await super().on_start()
        self.logger.info("Hello World plugin started!")

    @message_handler("HELLO")
    async def handle_hello(self, message):
        """Respond to hello messages."""
        self.greeting_count += 1
        sender = message.sender_id or "unknown"

        response = f"Hello {sender}! This is greeting #{self.greeting_count}"
        await self.publish_message(
            "HELLO_RESPONSE", {"response": response, "count": self.greeting_count}
        )

        self.logger.info(f"Responded to hello from {sender}")

    @background_task(interval=30.0)
    async def periodic_greeting(self):
        """Send periodic greetings."""
        await self.publish_message(
            "PERIODIC_HELLO",
            {
                "message": f"Hello from plugin! Count: {self.greeting_count}",
                "timestamp": __import__("time").time(),
            },
        )


# Plugin exports
PLUGIN_COMPONENTS = [HelloWorldService]

PLUGIN_METADATA = {
    "name": "Hello World Plugin",
    "version": "1.0.0",
    "description": "A simple example plugin for testing",
    "author": "AIPerf Team",
    "provides_services": ["greeting", "hello_response"],
}
