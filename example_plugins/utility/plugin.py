# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Utility Plugin - Simple Example

This plugin demonstrates a lightweight utility that provides helper
functionality to the system. It shows how simple plugins can be
while still using the full power of the mixin architecture.
"""

import time
from typing import Any

from aiperf.common.enums.message_enums import CommandType, MessageType
from aiperf.core.decorators import background_task, command_handler, message_handler
from aiperf.core.plugins import BasePlugin


class UtilityPlugin(BasePlugin):
    """
    Simple utility plugin that provides system information and helper functions.

    This demonstrates how lightweight plugins can be while still leveraging
    the full mixin architecture capabilities.
    """

    # Plugin metadata
    plugin_name = "utility"
    plugin_version = "1.0.0"
    plugin_description = "System utilities and helper functions"
    plugin_author = "AIPerf Team"
    plugin_dependencies = []
    plugin_requires_services = []
    plugin_provides_services = ["system_info", "utilities"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Simple state tracking
        self.start_time = time.time()
        self.message_count = 0
        self.command_count = 0

        # System information cache
        self.system_info = {}

    async def _initialize(self) -> None:
        """Initialize the utility plugin."""
        await super()._initialize()

        # Gather system information
        self.system_info = {
            "plugin_start_time": self.start_time,
            "python_version": "3.x",  # Would get actual version in real implementation
            "plugin_framework": "AIPerf Mixin Architecture",
            "capabilities": [
                "system_monitoring",
                "message_counting",
                "uptime_tracking",
            ],
        }

        self.info("Utility plugin initialized - ready to provide system utilities")

    async def _start(self) -> None:
        """Start the utility plugin."""
        await super()._start()
        self.info("Utility plugin started - utilities available")

    # =================================================================
    # Message Handlers - Count and log system activity
    # =================================================================

    @message_handler(MessageType.DATA_UPDATE, MessageType.STATUS, MessageType.HEARTBEAT)
    async def count_system_messages(self, message: Any) -> None:
        """
        Count various types of system messages.

        This shows how a simple plugin can monitor system activity
        without complex processing.
        """
        self.message_count += 1
        message_type = getattr(message, "message_type", "unknown")

        # Every 10th message, log a summary
        if self.message_count % 10 == 0:
            uptime = time.time() - self.start_time
            self.info(
                f"📊 Utility stats: {self.message_count} messages in {uptime:.1f}s"
            )

    # =================================================================
    # Command Handlers - Provide utility functions
    # =================================================================

    @command_handler(CommandType.GET_STATUS)
    async def get_utility_status(self, command: Any) -> dict:
        """
        Provide system utility information.

        This demonstrates how plugins can provide useful system information.
        """
        self.command_count += 1
        current_time = time.time()
        uptime = current_time - self.start_time

        return {
            "plugin": self.plugin_name,
            "system_info": self.system_info.copy(),
            "runtime_stats": {
                "uptime_seconds": uptime,
                "messages_processed": self.message_count,
                "commands_processed": self.command_count,
                "messages_per_second": self.message_count / uptime if uptime > 0 else 0,
            },
            "timestamp": current_time,
        }

    @command_handler(CommandType.PROFILE_START, CommandType.PROFILE_STOP)
    async def handle_profiling_commands(self, command: Any) -> dict:
        """
        Handle profiling commands with utility support.

        This shows how plugins can support system-wide operations.
        """
        command_type = getattr(command, "message_type", "unknown")

        if command_type == CommandType.PROFILE_START:
            self.info("🎯 Utility plugin: Profiling started - resetting counters")
            # Reset counters for clean profiling
            self.message_count = 0
            self.command_count = 0
            self.start_time = time.time()

            return {
                "utility_status": "profiling_started",
                "counters_reset": True,
                "timestamp": time.time(),
            }

        elif command_type == CommandType.PROFILE_STOP:
            uptime = time.time() - self.start_time
            self.info("🏁 Utility plugin: Profiling stopped - generating report")

            return {
                "utility_status": "profiling_stopped",
                "final_stats": {
                    "profiling_duration": uptime,
                    "messages_during_profiling": self.message_count,
                    "commands_during_profiling": self.command_count,
                    "average_message_rate": self.message_count / uptime
                    if uptime > 0
                    else 0,
                },
                "timestamp": time.time(),
            }

    # =================================================================
    # Background Tasks - Simple maintenance
    # =================================================================

    @background_task(interval=45.0)
    async def publish_system_summary(self) -> None:
        """
        Publish periodic system summary.

        This demonstrates how even simple plugins can contribute
        to system monitoring and observability.
        """
        try:
            uptime = time.time() - self.start_time

            summary = {
                "plugin": self.plugin_name,
                "summary_type": "system_utility",
                "uptime": uptime,
                "message_count": self.message_count,
                "message_rate": self.message_count / uptime if uptime > 0 else 0,
                "plugin_health": "healthy",
                "timestamp": time.time(),
            }

            # Publish summary using the mixin messaging capabilities
            await self.publish(MessageType.STATUS, summary)

            self.debug(
                f"Published system summary: {self.message_count} messages in {uptime:.1f}s"
            )

        except Exception as e:
            self.exception(f"Error publishing system summary: {e}")

    @background_task(interval=120.0)  # Every 2 minutes
    async def log_uptime_milestone(self) -> None:
        """
        Log uptime milestones.

        Simple background task that demonstrates periodic operations.
        """
        uptime = time.time() - self.start_time

        # Log milestones
        if uptime > 60:  # After 1 minute
            minutes = int(uptime // 60)
            self.info(f"⏱️  Utility plugin uptime milestone: {minutes} minute(s)")

            # Every 5 minutes, provide a more detailed report
            if minutes % 5 == 0:
                avg_rate = self.message_count / uptime if uptime > 0 else 0
                self.info("📈 Extended uptime report:")
                self.info(f"   - Runtime: {minutes} minutes")
                self.info(f"   - Messages processed: {self.message_count}")
                self.info(f"   - Average rate: {avg_rate:.2f} msg/sec")
                self.info(f"   - Commands handled: {self.command_count}")

    # =================================================================
    # Helper Methods (could be used by other plugins or services)
    # =================================================================

    def get_uptime(self) -> float:
        """Get plugin uptime in seconds."""
        return time.time() - self.start_time

    def get_message_rate(self) -> float:
        """Get average message processing rate."""
        uptime = self.get_uptime()
        return self.message_count / uptime if uptime > 0 else 0

    def format_uptime(self) -> str:
        """Get formatted uptime string."""
        uptime = self.get_uptime()

        if uptime < 60:
            return f"{uptime:.1f} seconds"
        elif uptime < 3600:
            return f"{uptime / 60:.1f} minutes"
        else:
            hours = int(uptime // 3600)
            minutes = int((uptime % 3600) // 60)
            return f"{hours}h {minutes}m"
