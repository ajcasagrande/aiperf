#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""
Complete example of ZMQ DEALER/ROUTER proxy for many-to-many targeted commands.

This example shows:
1. Setting up the proxy
2. Multiple services (ROUTER) handling different commands
3. Multiple clients (DEALER) sending targeted commands
4. Broadcasting, unicasting, and service-type targeting
"""

import asyncio
import logging
from typing import Any

import zmq.asyncio
from pydantic import BaseModel, Field

from aiperf.common.comms.zmq import (
    ZMQDealerRequestClient,
    ZMQDealerRouterProxy,
    ZMQRouterReplyClient,
)
from aiperf.common.config.zmq_config import ZMQTCPProxyConfig
from aiperf.common.enums import (
    CommandResponseStatus,
    CommandType,
    MessageType,
    ServiceType,
)
from aiperf.common.messages import CommandMessage, CommandResponseMessage, Message
from aiperf.common.models import ErrorDetails

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CommandResponseData(BaseModel):
    """Data model for command responses"""

    status: str = Field(..., description="Status of the command execution")


class TestService:
    """Example service that handles targeted commands"""

    def __init__(self, service_id: str, service_type: ServiceType):
        self.service_id = service_id
        self.service_type = service_type
        self.context = zmq.asyncio.Context.instance()
        self.stop_event = asyncio.Event()

        # ROUTER client connects to proxy backend
        self.router_client = ZMQRouterReplyClient(
            context=self.context,
            address="tcp://localhost:5662",  # Proxy backend
            bind=False,  # CONNECT to proxy
        )

    async def initialize(self):
        """Initialize the service and register handlers"""
        await self.router_client.initialize()

        # Register command handler
        self.router_client.register_request_handler(
            service_id=self.service_id,
            message_type=MessageType.COMMAND,
            handler=self._handle_command,
        )

        logger.info(f"Service {self.service_id} ({self.service_type}) initialized")

    async def _handle_command(self, message: CommandMessage) -> Message | None:
        """Handle incoming commands with targeting logic"""

        # Check if command is targeted at this service
        if message.target_service_id and message.target_service_id != self.service_id:
            return None  # Ignore - not for us

        if (
            message.target_service_type
            and message.target_service_type != self.service_type
        ):
            return None  # Ignore - not for our service type

        logger.info(f"Service {self.service_id} handling command: {message.command}")

        try:
            if message.command == CommandType.PROFILE_START:
                await self._start_profiling()
                return CommandResponseMessage(
                    service_id=self.service_id,
                    command=message.command,
                    command_id=message.command_id,
                    status=CommandResponseStatus.SUCCESS,
                    data=CommandResponseData(status="profiling_started"),
                )

            elif message.command == CommandType.PROFILE_STOP:
                await self._stop_profiling()
                return CommandResponseMessage(
                    service_id=self.service_id,
                    command=message.command,
                    command_id=message.command_id,
                    status=CommandResponseStatus.SUCCESS,
                    data=CommandResponseData(status="profiling_stopped"),
                )

            elif message.command == CommandType.SHUTDOWN:
                logger.info(f"Service {self.service_id} shutting down")
                self.stop_event.set()
                return CommandResponseMessage(
                    service_id=self.service_id,
                    command=message.command,
                    command_id=message.command_id,
                    status=CommandResponseStatus.SUCCESS,
                    data=CommandResponseData(status="shutting_down"),
                )

            else:
                raise ValueError(f"Unknown command: {message.command}")

        except Exception as e:
            logger.error(f"Service {self.service_id} error handling command: {e}")
            return CommandResponseMessage(
                service_id=self.service_id,
                command=message.command,
                command_id=message.command_id,
                status=CommandResponseStatus.FAILURE,
                error=ErrorDetails.from_exception(e),
            )

    async def _start_profiling(self):
        """Simulate starting profiling work"""
        await asyncio.sleep(0.1)  # Simulate work
        logger.info(f"Service {self.service_id} started profiling")

    async def _stop_profiling(self):
        """Simulate stopping profiling work"""
        await asyncio.sleep(0.1)  # Simulate work
        logger.info(f"Service {self.service_id} stopped profiling")

    async def run(self):
        """Run the service until stop is requested"""
        await self.stop_event.wait()

    async def shutdown(self):
        """Shutdown the service"""
        await self.router_client.shutdown()


class CommandController:
    """Example client that sends targeted commands"""

    def __init__(self, controller_id: str):
        self.controller_id = controller_id
        self.context = zmq.asyncio.Context.instance()

        # DEALER client connects to proxy frontend
        self.dealer_client = ZMQDealerRequestClient(
            context=self.context,
            address="tcp://localhost:5661",  # Proxy frontend
            bind=False,  # CONNECT to proxy
        )

    async def initialize(self):
        """Initialize the controller"""
        await self.dealer_client.initialize()
        logger.info(f"Controller {self.controller_id} initialized")

    async def send_targeted_command(
        self,
        command: CommandType,
        target_service_id: str | None = None,
        target_service_type: ServiceType | None = None,
        data: Any = None,
    ) -> Message:
        """Send a targeted command to specific service(s)"""

        command_message = CommandMessage(
            service_id=self.controller_id,
            command=command,
            target_service_id=target_service_id,
            target_service_type=target_service_type,
            data=data,
        )

        logger.info(
            f"Sending {command} to service_id={target_service_id}, service_type={target_service_type}"
        )

        try:
            response = await self.dealer_client.request(
                message=command_message, timeout=5.0
            )
            logger.info(f"Received response: {response}")
            return response
        except asyncio.TimeoutError:
            logger.error(f"Timeout waiting for response to command {command}")
            raise

    async def broadcast_command(self, command: CommandType) -> None:
        """Broadcast command to all services (no specific targeting)"""
        logger.info(f"Broadcasting {command} to all services")

        # For broadcast, we use async (fire-and-forget style)
        await self.dealer_client.request_async(
            message=CommandMessage(
                service_id=self.controller_id,
                command=command,
                target_service_id=None,  # No specific target
                target_service_type=None,
            ),
            callback=self._handle_broadcast_response,
        )

    async def _handle_broadcast_response(self, response: Message):
        """Handle responses from broadcast commands"""
        if isinstance(response, CommandResponseMessage):
            logger.info(
                f"Broadcast response from {response.service_id}: {response.status}"
            )

    async def shutdown(self):
        """Shutdown the controller"""
        await self.dealer_client.shutdown()


async def run_proxy():
    """Run the DEALER/ROUTER proxy"""
    proxy_config = ZMQTCPProxyConfig(
        host="localhost",
        frontend_port=5661,  # DEALER clients connect here
        backend_port=5662,  # ROUTER services connect here
    )

    proxy = ZMQDealerRouterProxy.from_config(proxy_config)
    logger.info("Starting DEALER/ROUTER proxy...")

    try:
        await proxy.run()
    except asyncio.CancelledError:
        logger.info("Proxy stopped")
    finally:
        await proxy.stop()


async def main():
    """Main example demonstrating many-to-many targeted commands"""

    # Start the proxy
    proxy_task = asyncio.create_task(run_proxy())
    await asyncio.sleep(1)  # Give proxy time to start

    # Create multiple services of different types
    services = [
        TestService("worker-1", ServiceType.WORKER),
        TestService("worker-2", ServiceType.WORKER),
        TestService("dataset-mgr-1", ServiceType.DATASET_MANAGER),
        TestService("records-mgr-1", ServiceType.RECORDS_MANAGER),
    ]

    # Initialize all services
    for service in services:
        await service.initialize()

    # Start services running
    service_tasks = [asyncio.create_task(service.run()) for service in services]

    await asyncio.sleep(1)  # Give services time to register

    # Create command controllers
    controller1 = CommandController("controller-1")
    controller2 = CommandController("controller-2")

    await controller1.initialize()
    await controller2.initialize()

    try:
        # Example 1: Target specific service by ID
        logger.info("\n=== Example 1: Target specific service by ID ===")
        response = await controller1.send_targeted_command(
            command=CommandType.PROFILE_START, target_service_id="worker-1"
        )

        # Example 2: Target all services of a specific type
        logger.info("\n=== Example 2: Target all WORKER services ===")
        response = await controller1.send_targeted_command(
            command=CommandType.PROFILE_START, target_service_type=ServiceType.WORKER
        )

        # Example 3: Broadcast to all services
        logger.info("\n=== Example 3: Broadcast to all services ===")
        await controller2.broadcast_command(CommandType.PROFILE_STOP)
        await asyncio.sleep(2)  # Wait for responses

        # Example 4: Multiple controllers sending parallel commands
        logger.info("\n=== Example 4: Parallel commands from multiple controllers ===")
        tasks = [
            controller1.send_targeted_command(
                command=CommandType.PROFILE_START, target_service_id="worker-1"
            ),
            controller2.send_targeted_command(
                command=CommandType.PROFILE_START, target_service_id="worker-2"
            ),
            controller1.send_targeted_command(
                command=CommandType.PROFILE_START, target_service_id="dataset-mgr-1"
            ),
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)
        for i, response in enumerate(responses):
            logger.info(f"Parallel response {i}: {response}")

        # Example 5: Shutdown specific services
        logger.info("\n=== Example 5: Shutdown specific services ===")
        await controller1.send_targeted_command(
            command=CommandType.SHUTDOWN, target_service_id="worker-1"
        )

        await controller1.send_targeted_command(
            command=CommandType.SHUTDOWN, target_service_id="worker-2"
        )

        await asyncio.sleep(1)  # Give services time to shutdown

    except Exception as e:
        logger.error(f"Error in main example: {e}")

    finally:
        # Cleanup
        logger.info("Cleaning up...")

        # Shutdown remaining services
        for service in services:
            if not service.stop_event.is_set():
                await controller1.send_targeted_command(
                    command=CommandType.SHUTDOWN, target_service_id=service.service_id
                )

        # Wait for services to stop
        await asyncio.gather(*service_tasks, return_exceptions=True)

        # Shutdown controllers
        await controller1.shutdown()
        await controller2.shutdown()

        # Stop proxy
        proxy_task.cancel()
        await asyncio.gather(proxy_task, return_exceptions=True)

        logger.info("Example completed!")


if __name__ == "__main__":
    asyncio.run(main())
