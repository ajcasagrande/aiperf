#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
# Example Data Processor Plugin
import asyncio

from aiperf.lifecycle import Service, background_task, command_handler, message_handler


class DataProcessorService(Service):
    """A data processing plugin that handles work queues."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.work_queue = []
        self.processed_items = 0
        self.processing = False

    async def on_init(self):
        await super().on_init()
        self.logger.info("Data processor plugin initialized!")

    @message_handler("PROCESS_DATA")
    async def handle_process_data(self, message):
        """Add data to processing queue."""
        data = message.content
        self.work_queue.append(data)
        self.logger.info(f"Added data to queue: {len(self.work_queue)} items pending")

        # Acknowledge receipt
        await self.publish_message(
            "DATA_QUEUED",
            {"data_id": data.get("id", "unknown"), "queue_size": len(self.work_queue)},
        )

    @command_handler("GET_QUEUE_STATUS")
    async def get_queue_status(self, command):
        """Get current queue status."""
        return {
            "queue_size": len(self.work_queue),
            "processed_items": self.processed_items,
            "processing": self.processing,
        }

    @background_task(interval=2.0)
    async def process_queue(self):
        """Process items from the work queue."""
        if not self.work_queue or self.processing:
            return

        self.processing = True

        try:
            # Process one item
            item = self.work_queue.pop(0)
            self.logger.info(f"Processing item: {item}")

            # Simulate processing time
            await asyncio.sleep(1.0)

            self.processed_items += 1

            # Notify completion
            await self.publish_message(
                "DATA_PROCESSED",
                {
                    "item": item,
                    "processed_count": self.processed_items,
                    "remaining": len(self.work_queue),
                },
            )

        finally:
            self.processing = False


# Plugin exports
PLUGIN_COMPONENTS = [DataProcessorService]

PLUGIN_METADATA = {
    "name": "Data Processor Plugin",
    "version": "1.0.0",
    "description": "Processes data items from a queue",
    "author": "AIPerf Team",
    "provides_services": ["data_processing", "queue_management"],
}
