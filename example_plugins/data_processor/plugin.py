# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Data Processor Plugin - Comprehensive Example

This plugin demonstrates all the capabilities of the AIPerf plugin system:
- Full lifecycle management
- Message handling with inheritance support
- Background tasks
- Command handling
- Configuration management
- Error handling
- Real aiperf integration
"""

import asyncio
import time
from typing import Any

from aiperf.common.enums.message_enums import CommandType, MessageType
from aiperf.core.decorators import background_task, command_handler, message_handler
from aiperf.core.plugins import BasePlugin


class DataProcessorPlugin(BasePlugin):
    """
    Advanced data processing plugin that showcases the full power
    of the AIPerf plugin system built on your amazing mixins.
    """

    # Plugin metadata
    plugin_name = "data_processor"
    plugin_version = "2.1.0"
    plugin_description = (
        "Advanced data processing with analytics and real-time monitoring"
    )
    plugin_author = "AIPerf Team"
    plugin_dependencies = []  # No dependencies for this example
    plugin_requires_services = ["event_bus"]
    plugin_provides_services = ["data_processing", "analytics"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Plugin state
        self.data_queue: list[dict] = []
        self.processed_items: list[dict] = []
        self.processing_stats = {
            "total_received": 0,
            "total_processed": 0,
            "total_errors": 0,
            "average_processing_time": 0.0,
            "last_batch_time": 0.0,
            "queue_max_size": 0,
        }

        # Configuration (with defaults)
        self.batch_size = 10
        self.max_queue_size = 1000
        self.processing_delay = 0.1
        self.enable_analytics = True

    async def _initialize(self) -> None:
        """Initialize the data processor plugin."""
        await super()._initialize()

        # Load configuration from plugin_config
        self.batch_size = self.plugin_config.get("batch_size", 10)
        self.max_queue_size = self.plugin_config.get("max_queue_size", 1000)
        self.processing_delay = self.plugin_config.get("processing_delay", 0.1)
        self.enable_analytics = self.plugin_config.get("enable_analytics", True)

        self.info("Data processor initialized:")
        self.info(f"  - Batch size: {self.batch_size}")
        self.info(f"  - Max queue size: {self.max_queue_size}")
        self.info(f"  - Processing delay: {self.processing_delay}s")
        self.info(f"  - Analytics enabled: {self.enable_analytics}")

    async def _start(self) -> None:
        """Start the data processor plugin."""
        await super()._start()
        self.info("Data processor plugin started and ready to process data!")

    async def _stop(self) -> None:
        """Stop the data processor plugin and cleanup."""
        await super()._stop()

        # Process any remaining items in queue
        if self.data_queue:
            self.info(
                f"Processing {len(self.data_queue)} remaining items before shutdown..."
            )
            await self._process_batch(force=True)

        self.info("Data processor plugin stopped")

    # =================================================================
    # Message Handlers - Using your amazing mixin inheritance support
    # =================================================================

    @message_handler(MessageType.DATA_UPDATE)
    async def handle_data_update(self, message: Any) -> None:
        """
        Handle incoming data updates.

        This demonstrates how plugins can handle messages just like regular
        services, with full inheritance support.
        """
        try:
            data = getattr(message, "data", message)

            # Add to queue
            queue_item = {
                "data": data,
                "timestamp": time.time(),
                "message_id": getattr(message, "message_id", f"msg_{time.time()}"),
                "source": getattr(message, "service_id", "unknown"),
            }

            if len(self.data_queue) >= self.max_queue_size:
                self.warning(
                    f"Queue full ({self.max_queue_size}), dropping oldest item"
                )
                self.data_queue.pop(0)

            self.data_queue.append(queue_item)
            self.processing_stats["total_received"] += 1
            self.processing_stats["queue_max_size"] = max(
                self.processing_stats["queue_max_size"], len(self.data_queue)
            )

            self.debug(f"Added data to queue (queue size: {len(self.data_queue)})")

            # Process batch if queue is full
            if len(self.data_queue) >= self.batch_size:
                await self._process_batch()

        except Exception as e:
            self.processing_stats["total_errors"] += 1
            self.exception(f"Error handling data update: {e}")

    @message_handler(MessageType.Heartbeat, MessageType.Status)
    async def handle_system_messages(self, message: Any) -> None:
        """
        Handle system messages for monitoring.

        This shows how multiple message types can be handled by one method,
        and how plugins can participate in system monitoring.
        """
        message_type = getattr(message, "message_type", "unknown")
        service_id = getattr(message, "service_id", "unknown")

        self.debug(f"Received {message_type} from {service_id}")

        # If analytics enabled, track system health
        if self.enable_analytics and message_type == MessageType.Heartbeat:
            # Could aggregate system health data here
            pass

    # =================================================================
    # Command Handlers - Full command/response support
    # =================================================================

    @command_handler(CommandType.GET_STATUS)
    async def get_processing_status(self, command: Any) -> dict:
        """
        Handle status requests.

        This demonstrates how plugins can respond to commands just like
        regular services, returning structured data.
        """
        return {
            "plugin": self.plugin_name,
            "version": self.plugin_version,
            "state": self.plugin_state,
            "queue_size": len(self.data_queue),
            "processed_items": len(self.processed_items),
            "statistics": self.processing_stats.copy(),
            "configuration": {
                "batch_size": self.batch_size,
                "max_queue_size": self.max_queue_size,
                "processing_delay": self.processing_delay,
                "enable_analytics": self.enable_analytics,
            },
        }

    @command_handler(CommandType.ProfileStart)
    async def start_profiling(self, command: Any) -> dict:
        """Handle profiling start command."""
        self.info("Starting enhanced profiling mode")
        self.enable_analytics = True

        # Reset statistics for clean profiling
        self.processing_stats.update(
            {
                "total_received": 0,
                "total_processed": 0,
                "total_errors": 0,
                "average_processing_time": 0.0,
            }
        )

        return {
            "status": "profiling_started",
            "plugin": self.plugin_name,
            "timestamp": time.time(),
        }

    @command_handler(CommandType.ProfileStop)
    async def stop_profiling(self, command: Any) -> dict:
        """Handle profiling stop command."""
        self.info("Stopping profiling mode")

        # Generate final report
        report = {
            "status": "profiling_stopped",
            "plugin": self.plugin_name,
            "timestamp": time.time(),
            "final_statistics": self.processing_stats.copy(),
            "processed_items": len(self.processed_items),
            "queue_size": len(self.data_queue),
        }

        return report

    # =================================================================
    # Background Tasks - Using your amazing decorator system
    # =================================================================

    @background_task(interval=5.0)
    async def process_pending_data(self) -> None:
        """
        Process any pending data every 5 seconds.

        This demonstrates how background tasks work seamlessly in plugins,
        using the same decorator system as regular services.
        """
        if self.data_queue:
            self.debug(f"Background processor: {len(self.data_queue)} items pending")
            await self._process_batch()

    @background_task(interval=30.0)
    async def report_statistics(self) -> None:
        """
        Report processing statistics every 30 seconds.

        This shows how plugins can publish status information using
        the real aiperf message infrastructure.
        """
        if self.processing_stats["total_received"] > 0:
            self.info(
                f"Data processor stats: "
                f"received={self.processing_stats['total_received']}, "
                f"processed={self.processing_stats['total_processed']}, "
                f"errors={self.processing_stats['total_errors']}, "
                f"queue={len(self.data_queue)}"
            )

            # Publish statistics using real aiperf messaging
            try:
                await self.publish(
                    MessageType.Status,
                    {
                        "plugin": self.plugin_name,
                        "statistics": self.processing_stats.copy(),
                        "queue_size": len(self.data_queue),
                        "timestamp": time.time(),
                    },
                )
            except Exception as e:
                self.exception(f"Failed to publish statistics: {e}")

    @background_task(interval=60.0)
    async def cleanup_old_data(self) -> None:
        """
        Cleanup old processed data every minute.

        This demonstrates resource management in background tasks.
        """
        # Keep only the last 100 processed items
        if len(self.processed_items) > 100:
            removed_count = len(self.processed_items) - 100
            self.processed_items = self.processed_items[-100:]
            self.debug(f"Cleaned up {removed_count} old processed items")

    # =================================================================
    # Private Implementation Methods
    # =================================================================

    async def _process_batch(self, force: bool = False) -> None:
        """
        Process a batch of data items.

        Args:
            force: If True, process all items regardless of batch size
        """
        if not self.data_queue:
            return

        # Determine batch size
        if force:
            batch = self.data_queue.copy()
            self.data_queue.clear()
        else:
            batch = self.data_queue[: self.batch_size]
            self.data_queue = self.data_queue[self.batch_size :]

        if not batch:
            return

        start_time = time.time()

        try:
            self.debug(f"Processing batch of {len(batch)} items...")

            # Simulate processing work
            await asyncio.sleep(self.processing_delay)

            # Process each item
            processed_batch = []
            for item in batch:
                try:
                    processed_item = await self._process_single_item(item)
                    processed_batch.append(processed_item)
                except Exception as e:
                    self.exception(f"Error processing item: {e}")
                    self.processing_stats["total_errors"] += 1

            # Update statistics
            processing_time = time.time() - start_time
            self.processing_stats["total_processed"] += len(processed_batch)
            self.processing_stats["last_batch_time"] = processing_time

            # Update average processing time
            if self.processing_stats["total_processed"] > 0:
                total_time = (
                    self.processing_stats["average_processing_time"]
                    * (self.processing_stats["total_processed"] - len(processed_batch))
                    + processing_time
                )
                self.processing_stats["average_processing_time"] = (
                    total_time / self.processing_stats["total_processed"]
                )

            # Store processed items
            self.processed_items.extend(processed_batch)

            self.info(
                f"Successfully processed batch: {len(processed_batch)} items "
                f"in {processing_time:.3f}s"
            )

            # Publish processing results if analytics enabled
            if self.enable_analytics:
                try:
                    await self.publish(
                        MessageType.DATA_PROCESSED,
                        {
                            "plugin": self.plugin_name,
                            "batch_size": len(processed_batch),
                            "processing_time": processing_time,
                            "total_processed": self.processing_stats["total_processed"],
                            "timestamp": time.time(),
                        },
                    )
                except Exception as e:
                    self.exception(f"Failed to publish processing results: {e}")

        except Exception as e:
            self.processing_stats["total_errors"] += 1
            self.exception(f"Error processing batch: {e}")

    async def _process_single_item(self, item: dict) -> dict:
        """
        Process a single data item.

        Args:
            item: Data item to process

        Returns:
            Processed item with additional metadata
        """
        # Simulate item processing
        processed_item = {
            "original": item,
            "processed_at": time.time(),
            "plugin": self.plugin_name,
            "processing_duration": item["timestamp"] - time.time()
            if "timestamp" in item
            else 0,
            "result": {
                "status": "processed",
                "data_size": len(str(item.get("data", ""))),
                "source": item.get("source", "unknown"),
            },
        }

        return processed_item
