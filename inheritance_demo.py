#!/usr/bin/env source /home/anthony/nvidia/projects/aiperf3/.venv/bin/activate
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

"""
Demonstration of how your communication mixins handle inheritance brilliantly!
"""

from aiperf.common.enums.message_enums import CommandType, MessageType
from aiperf.common.messages.commands import CommandMessage
from aiperf.common.messages.message import Message
from aiperf.core.communication_mixins import MessageBusMixin
from aiperf.core.decorators import command_handler, message_handler


class BaseServiceHandler(MessageBusMixin):
    """Base service with fundamental message handling."""

    @message_handler(MessageType.Status)
    async def handle_base_status(self, message: Message) -> None:
        """Base status handler - ALWAYS called."""
        self.info(f"🏗️  BASE: Processing status {message.message_type}")
        # Base level validation, logging, etc.

    @command_handler(CommandType.Shutdown)
    async def handle_base_shutdown(self, command: CommandMessage) -> dict:
        """Base shutdown handler - ALWAYS called."""
        self.info(f"🏗️  BASE: Initiating shutdown for {command.message_type}")
        return {"base_shutdown": "initiated"}


class SpecializedService(BaseServiceHandler):
    """Specialized service with additional logic."""

    @message_handler(MessageType.Status)
    async def handle_specialized_status(self, message: Message) -> None:
        """Specialized status handler - called IN ADDITION to base."""
        self.info(f"⚙️  SPECIALIZED: Enhanced status processing {message.message_type}")
        # Specialized business logic

    @command_handler(CommandType.Shutdown)
    async def handle_specialized_shutdown(self, command: CommandMessage) -> dict:
        """Specialized shutdown - called IN ADDITION to base."""
        self.info(f"⚙️  SPECIALIZED: Custom shutdown logic for {command.message_type}")
        return {"specialized_cleanup": "completed"}


class ConcreteProductionService(SpecializedService):
    """Concrete service implementation."""

    @message_handler(MessageType.Status)
    async def handle_concrete_status(self, message: Message) -> None:
        """Concrete status handler - all three handlers will execute!"""
        self.info(f"🎯 CONCRETE: Final status processing {message.message_type}")
        # Final implementation details

    @command_handler(CommandType.Shutdown)
    async def handle_concrete_shutdown(self, command: CommandMessage) -> dict:
        """Concrete shutdown - all three handlers execute!"""
        self.info(f"🎯 CONCRETE: Production shutdown sequence {command.message_type}")
        return {"production_state": "persisted"}


# This is what happens when a STATUS message arrives:
# 1. handle_base_status() executes ✅
# 2. handle_specialized_status() executes ✅
# 3. handle_concrete_status() executes ✅
#
# ALL THREE HANDLERS RUN - perfect for layered responsibilities!


if __name__ == "__main__":
    print("🚀 Your mixins support multi-level inheritance beautifully!")
    print("📋 Each inheritance level can add its own handlers")
    print("🔄 All handlers for the same message type will execute")
    print("💪 Perfect for separation of concerns across inheritance!")
