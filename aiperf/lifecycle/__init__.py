# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
AIPerf Lifecycle - A Simple, Powerful Service Lifecycle Management System

This module provides a clean, pythonic approach to service lifecycle management,
message handling, and background task management. It's designed to be simple to use
while remaining powerful and flexible.

Key Features:
- Simple inheritance-based lifecycle management
- Automatic hook discovery (no configuration needed)
- Clean message handling patterns
- Easy background task management
- Type-safe and well-documented
- Easy to debug and understand

Basic Usage:
    from aiperf.lifecycle import LifecycleService, message_handler, background_task

    class MyService(LifecycleService):
        async def on_init(self):
            self.logger.info("Service initializing...")

        async def on_start(self):
            self.logger.info("Service starting...")

        @message_handler("USER_MESSAGE")
        async def handle_user_message(self, message):
            self.logger.info(f"Received: {message}")

        @background_task(interval=5.0)
        async def health_check(self):
            await self.check_system_health()
"""

from .base import LifecycleService, LifecycleState
from .decorators import background_task, command_handler, message_handler
from .messaging import Command, Message, MessageBus
from .service import AIPerf, ManagedLifecycleService
from .tasks import TaskManager

__all__ = [
    "LifecycleService",
    "LifecycleState",
    "message_handler",
    "background_task",
    "command_handler",
    "MessageBus",
    "Message",
    "Command",
    "TaskManager",
    "ManagedLifecycleService",
    "AIPerf",
]
