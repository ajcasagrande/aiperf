#!/usr/bin/env python3
#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
"""
Demo script showcasing the new MessageBusMixin with decorators.

This script demonstrates:
- Message handling with @message_handler decorator
- Command handling with @command_handler decorator
- Background tasks with @background_task decorator
- Lifecycle management
- Error handling
"""

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from pydantic import BaseModel, Field

# Import communication dependencies for mocking
from aiperf.common.comms.base_comms import BaseCommunication

# Import message types and enums
from aiperf.common.enums import CommandType, MessageType
from aiperf.common.messages.commands import CommandMessage
from aiperf.common.messages.message import Message

# Import the core components
from aiperf.core.communication_mixins import MessageBusMixin
from aiperf.core.decorators import background_task, command_handler, message_handler


class DemoData(BaseModel):
    """Demo data model for testing."""

    message: str = Field(description="Demo message")
    timestamp: float = Field(default_factory=time.time, description="Timestamp")
    counter: int = Field(default=0, description="Message counter")


class DemoStatusMessage(Message):
    """Demo status message."""

    message_type: MessageType = MessageType.Status
    service_id: str = Field(description="Service ID")
    data: DemoData = Field(description="Status data")


class DemoHeartbeatMessage(Message):
    """Demo heartbeat message."""

    message_type: MessageType = MessageType.Heartbeat
    service_id: str = Field(description="Service ID")
    timestamp: float = Field(
        default_factory=time.time, description="Heartbeat timestamp"
    )


class DemoCommandMessage(CommandMessage):
    """Demo command message."""

    message_type: CommandType = CommandType.ProfileStart
    data: DemoData | None = None


class DemoService(MessageBusMixin):
    """Demo service showcasing MessageBusMixin functionality."""

    def __init__(self, service_id: str = "demo-service", **kwargs):
        # Create mock communication for demo
        mock_comms = self._create_mock_communication()
        super().__init__(comms=mock_comms, id=service_id, **kwargs)

        # Demo state
        self.message_count = 0
        self.heartbeat_count = 0
        self.command_count = 0
        self.task_iterations = 0
        self.is_running = False

        # Set service_type to avoid linter issues
        self.service_type = "demo"

    def _create_mock_communication(self) -> BaseCommunication:
        """Create a mock communication instance for demo purposes."""
        mock_comms = MagicMock(spec=BaseCommunication)

        # Mock clients
        mock_sub_client = AsyncMock()
        mock_pub_client = AsyncMock()

        # Set up client creation methods
        mock_comms.create_sub_client.return_value = mock_sub_client
        mock_comms.create_pub_client.return_value = mock_pub_client

        # Mock initialization methods
        mock_comms.initialize = AsyncMock()
        mock_comms.shutdown = AsyncMock()

        return mock_comms

    # =================================================================
    # Message Handlers using @message_handler decorator
    # =================================================================

    @message_handler(MessageType.Status)
    async def handle_status_message(self, message: DemoStatusMessage) -> None:
        """Handle status messages."""
        self.message_count += 1
        self.info(
            f"Received status message #{self.message_count}: {message.data.message}"
        )

        # Simulate some processing
        await asyncio.sleep(0.1)

        # You could publish a response here
        # await self.publish(some_response_message)

    @message_handler(MessageType.Heartbeat)
    async def handle_heartbeat(self, message: DemoHeartbeatMessage) -> None:
        """Handle heartbeat messages."""
        self.heartbeat_count += 1
        self.debug(f"Heartbeat #{self.heartbeat_count} received at {message.timestamp}")

    @message_handler(MessageType.Status, MessageType.Heartbeat)
    async def handle_multiple_types(self, message: Message) -> None:
        """Handler for multiple message types - this demonstrates decorator flexibility."""
        if message.message_type == MessageType.Status:
            self.debug("Multi-handler: Processing status message")
        elif message.message_type == MessageType.Heartbeat:
            self.debug("Multi-handler: Processing heartbeat message")

    # =================================================================
    # Command Handlers using @command_handler decorator
    # =================================================================

    @command_handler(CommandType.ProfileStart)
    async def handle_profile_start(self, command: DemoCommandMessage) -> dict[str, Any]:
        """Handle profile start commands."""
        self.command_count += 1
        self.info(f"Starting profile #{self.command_count}")

        # Simulate profile startup
        await asyncio.sleep(0.2)
        self.is_running = True

        # Return response data
        return {
            "status": "started",
            "profile_id": f"profile_{self.command_count}",
            "timestamp": time.time(),
            "message": "Profile started successfully",
        }

    @command_handler(CommandType.ProfileStop)
    async def handle_profile_stop(self, command: CommandMessage) -> dict[str, Any]:
        """Handle profile stop commands."""
        self.info("Stopping profile")

        # Simulate profile shutdown
        await asyncio.sleep(0.1)
        self.is_running = False

        return {
            "status": "stopped",
            "timestamp": time.time(),
            "message": "Profile stopped successfully",
        }

    @command_handler(CommandType.Shutdown)
    async def handle_shutdown(self, command: CommandMessage) -> dict[str, Any]:
        """Handle shutdown commands."""
        self.warning("Shutdown command received")

        # Simulate cleanup
        await asyncio.sleep(0.1)

        # Request stop after handling this command
        asyncio.create_task(self._delayed_stop())

        return {
            "status": "shutting_down",
            "timestamp": time.time(),
            "message": "Shutdown initiated",
        }

    async def _delayed_stop(self) -> None:
        """Helper to stop the service after a delay."""
        await asyncio.sleep(0.5)
        await self.stop()

    # =================================================================
    # Background Tasks using @background_task decorator
    # =================================================================

    @background_task(interval=2.0)
    async def periodic_status_check(self) -> None:
        """Periodic status check task."""
        self.task_iterations += 1
        self.debug(f"Background task iteration #{self.task_iterations}")

        # Simulate publishing a status update
        status_message = DemoStatusMessage(
            service_id=self.id,
            data=DemoData(
                message=f"Periodic update #{self.task_iterations}",
                counter=self.task_iterations,
            ),
        )

        # In a real scenario, you would publish this
        self.debug(f"Would publish: {status_message.data.message}")

    @background_task(interval=5.0, start_immediately=False)
    async def periodic_heartbeat(self) -> None:
        """Periodic heartbeat task."""
        heartbeat = DemoHeartbeatMessage(service_id=self.id, timestamp=time.time())

        self.debug(f"Would publish heartbeat at {heartbeat.timestamp}")

    # =================================================================
    # Demo Methods
    # =================================================================

    async def simulate_messages(self) -> None:
        """Simulate receiving messages for demo purposes."""
        self.info("Starting message simulation...")

        # Simulate status messages
        for i in range(3):
            status_msg = DemoStatusMessage(
                service_id=f"sender-{i}",
                data=DemoData(message=f"Status update {i + 1}", counter=i + 1),
            )
            await self.handle_status_message(status_msg)
            await asyncio.sleep(0.5)

        # Simulate heartbeats
        for i in range(2):
            heartbeat_msg = DemoHeartbeatMessage(
                service_id=f"sender-{i}", timestamp=time.time()
            )
            await self.handle_heartbeat(heartbeat_msg)
            await asyncio.sleep(0.3)

        # Simulate commands
        start_cmd = DemoCommandMessage(
            service_id="controller",
            request_id="req-001",
            data=DemoData(message="Start profiling now"),
        )
        response = await self.handle_profile_start(start_cmd)
        self.info(f"Command response: {response}")

        await asyncio.sleep(1.0)

        stop_cmd = CommandMessage(
            message_type=CommandType.ProfileStop,
            service_id="controller",
            request_id="req-002",
        )
        response = await self.handle_profile_stop(stop_cmd)
        self.info(f"Stop response: {response}")

    def print_stats(self) -> None:
        """Print demo statistics."""
        self.info("=== Demo Statistics ===")
        self.info(f"Messages processed: {self.message_count}")
        self.info(f"Heartbeats received: {self.heartbeat_count}")
        self.info(f"Commands executed: {self.command_count}")
        self.info(f"Background task iterations: {self.task_iterations}")
        self.info(f"Service running: {self.is_running}")
        self.info("=====================")


async def main():
    """Main demo function."""
    print("🚀 Starting MessageBusMixin Demo")
    print("=================================")

    # Create demo service
    demo_service = DemoService(service_id="demo-001")

    try:
        # Initialize the service
        print("📡 Initializing service...")
        await demo_service.initialize()

        # Start the service
        print("▶️  Starting service...")
        await demo_service.start()

        # Run the demo simulation
        print("🎭 Running message simulation...")
        await demo_service.simulate_messages()

        # Let background tasks run for a bit
        print("⏰ Letting background tasks run...")
        await asyncio.sleep(3.0)

        # Print statistics
        demo_service.print_stats()

        # Test error handling
        print("🧪 Testing error handling...")
        try:
            # Simulate a command that might fail
            error_cmd = CommandMessage(
                message_type=CommandType.ProfileStart,
                service_id="error-test",
                request_id="error-001",
            )
            # This would normally be handled by the message bus
            print("Error handling test completed (no actual error in demo)")
        except Exception as e:
            print(f"Caught expected error: {e}")

        print("✅ Demo completed successfully!")

    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback

        traceback.print_exc()

    finally:
        # Clean shutdown
        print("🛑 Shutting down service...")
        try:
            await demo_service.stop()
        except Exception as e:
            print(f"Error during shutdown: {e}")

    print("👋 Demo finished!")


if __name__ == "__main__":
    # Set up proper logging
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Run the demo
    asyncio.run(main())
