#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
# Custom Monitor Plugin (Created Dynamically)
import random
import time

from aiperf.lifecycle import Service, background_task, command_handler, message_handler


class CustomMonitorService(Service):
    """A dynamically created monitoring plugin."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.metrics = {"cpu": 0.0, "memory": 0.0, "network": 0.0}
        self.alert_count = 0

    async def on_init(self):
        await super().on_init()
        self.logger.info("🔍 Custom monitor plugin initialized!")

    @message_handler("DATA_PROCESSED")
    async def monitor_data_processing(self, message):
        """Monitor data processing events."""
        processed_count = message.content.get("processed_count", 0)

        if processed_count % 3 == 0:  # Alert every 3 processed items
            self.alert_count += 1
            await self.publish_message(
                "MONITOR_ALERT",
                {
                    "type": "processing_milestone",
                    "message": f"Processed {processed_count} items!",
                    "alert_number": self.alert_count,
                    "timestamp": time.time(),
                },
            )

    @background_task(interval=6.0)
    async def collect_system_metrics(self):
        """Simulate collecting system metrics."""
        self.metrics["cpu"] = random.uniform(10, 90)
        self.metrics["memory"] = random.uniform(20, 80)
        self.metrics["network"] = random.uniform(1, 100)

        self.logger.info(
            f"📊 Metrics - CPU: {self.metrics['cpu']:.1f}%, "
            f"Memory: {self.metrics['memory']:.1f}%, "
            f"Network: {self.metrics['network']:.1f} Mbps"
        )

        # Send alert if CPU is high
        if self.metrics["cpu"] > 75:
            await self.publish_message(
                "MONITOR_ALERT",
                {
                    "type": "high_cpu",
                    "message": f"High CPU usage: {self.metrics['cpu']:.1f}%",
                    "metrics": self.metrics,
                    "timestamp": time.time(),
                },
            )

    @command_handler("GET_METRICS")
    async def get_metrics(self, command):
        """Get current system metrics."""
        return {
            "metrics": self.metrics,
            "alert_count": self.alert_count,
            "uptime": time.time(),
        }


# Plugin exports
PLUGIN_COMPONENTS = [CustomMonitorService]

PLUGIN_METADATA = {
    "name": "Custom Monitor Plugin",
    "version": "1.0.0",
    "description": "Dynamically created monitoring plugin",
    "author": "Demo System",
    "provides_services": ["system_monitoring", "alerting"],
}
