# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
import sys
import uuid
from typing import cast

from aiperf.backend.factory import BackendClientFactory
from aiperf.backend.openai_client import OpenAIBackendClientConfig
from aiperf.common.comms.client_enums import (
    ClientType,
    PullClientType,
    PushClientType,
    ReqClientType,
)
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.enums import BackendClientType, DataTopic, ServiceType, Topic
from aiperf.common.hooks import on_cleanup, on_init, on_run, on_start, on_stop
from aiperf.common.interfaces import BackendClientProtocol
from aiperf.common.models import (
    ConversationRequestPayload,
    ConversationResponseMessage,
    CreditReturnPayload,
)
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.common.service.base_service import BaseService


class Worker(BaseService):
    """Worker is primarily responsible for converting the data into the appropriate
    format for the interface being used by the server. Also responsible for managing
    the conversation between turns.
    """

    def __init__(
        self, service_config: ServiceConfig, service_id: str | None = None
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing worker")

        # Backend client will be initialized in _initialize
        self.backend_client: BackendClientProtocol | None = None

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER

    @property
    def required_clients(self) -> list[ClientType]:
        """The communication clients required by the service."""
        return [
            *(super().required_clients or []),
            PullClientType.CREDIT_DROP,
            PushClientType.CREDIT_RETURN,
            ReqClientType.CONVERSATION_DATA,
        ]

    @on_init
    async def _initialize(self) -> None:
        """Initialize worker-specific components."""
        self.logger.debug("Initializing worker")

        # Get API key from environment variable or use a default for testing
        api_key = os.environ.get("OPENAI_API_KEY", "sk-fakeai-1234567890abcdef")

        # Create OpenAI client configuration
        openai_client_config = OpenAIBackendClientConfig(
            api_key=api_key,
            url="http://127.0.0.1:8000/v1",  # Default OpenAI API endpoint
            model="gpt-3.5-turbo",  # Default model
        )

        # Initialize the OpenAI client
        self.backend_client = BackendClientFactory.create_instance(
            BackendClientType.OPENAI, config=openai_client_config
        )
        self.logger.debug("Backend client initialized")

    @on_run
    async def _run(self) -> None:
        """Automatically start the worker in the run method."""
        await self.start()

    @on_start
    async def _start(self) -> None:
        """Start the worker."""
        self.logger.debug("Starting worker")
        # Subscribe to the credit drop topic
        await self.comms.pull(
            topic=Topic.CREDIT_DROP,
            callback=self._process_credit_drop,
        )

    @on_stop
    async def _stop(self) -> None:
        """Stop the worker."""
        self.logger.debug("Stopping worker")

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up worker-specific components."""
        self.logger.debug("Cleaning up worker")

    async def _process_credit_drop(self, message) -> None:
        """Process a credit drop response.

        Args:
            message: The message received from the credit drop
        """
        self.logger.debug(f"Processing credit drop: {message}")

        credit_amount = 0
        try:
            # Extract the credit drop message payload
            if hasattr(message, "payload") and hasattr(message.payload, "amount"):
                credit_amount = message.payload.amount
                self.logger.debug(f"Received {credit_amount} credit(s)")

                # Make a call to OpenAI API for each credit
                for _ in range(credit_amount):
                    await self._call_backend_api()
                    # await asyncio.sleep(0.1)  # Small delay between calls
            else:
                self.logger.warning(
                    f"Received credit drop message without amount: {message}"
                )

        except Exception as e:
            self.logger.error(f"Error processing credit drop: {e}")

        finally:
            # Always return the credits
            self.logger.debug("Returning credits")
            await self.comms.push(
                topic=Topic.CREDIT_RETURN,
                message=self.create_message(
                    payload=CreditReturnPayload(amount=credit_amount),
                ),
            )

    async def _call_backend_api(self) -> None:
        """Make a call to the backend API."""
        try:
            self.logger.debug("Calling backend API")

            if not self.backend_client:
                self.logger.warning("Backend client not initialized, skipping API call")
                return

            # retrieve the prompt from the dataset
            response = await self.comms.request(
                topic=DataTopic.CONVERSATION,
                message=self.create_message(
                    payload=ConversationRequestPayload(
                        conversation_id="123",
                    ),
                ),
            )
            messages = cast(
                ConversationResponseMessage, response
            ).payload.conversation_data

            # Sample messages for the API call
            # messages = [
            #     {"role": "system", "content": "You are a helpful assistant."},
            #     {
            #         "role": "user",
            #         "content": "Tell me about NVIDIA AI performance testing.",
            #     },
            # ]

            # Format payload for the API request
            formatted_payload = await self.backend_client.format_payload(
                endpoint="v1/chat/completions", payload={"messages": messages}
            )

            # Send the request to the API
            record = await self.backend_client.send_request(
                endpoint="v1/chat/completions", payload=formatted_payload
            )

            if record.valid:
                self.logger.debug("Backend API call successful")
                self.logger.debug(
                    f"Record: {record.time_to_first_response_ns / 1e6} milliseconds. {record.time_to_last_response_ns / 1e6} milliseconds."
                )
            else:
                self.logger.warning("Backend API call returned invalid response")

        except Exception as e:
            self.logger.error("Error calling backend API: %s", str(e))


class MultiWorkerProcess(BaseComponentService):
    """MultiWorkerProcess is a process that runs multiple workers as concurrent tasks on the event loop."""

    def __init__(self, service_config: ServiceConfig, service_id: str | None = None):
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing worker process")
        self.workers: list[Worker] = []
        self.tasks: list[asyncio.Task] = []
        self.worker_count = 50

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.MULTI_WORKER_PROCESS

    @property
    def required_clients(self) -> list[ClientType]:
        """The communication clients required by the service."""
        return super().required_clients or []

    @on_run
    async def _run(self) -> None:
        self.logger.debug("%s: Creating %s workers", self.service_id, self.worker_count)
        for _ in range(self.worker_count):
            worker = Worker(
                service_config=self.service_config,
                service_id=f"worker_{uuid.uuid4().hex[:8]}",
            )
            self.workers.append(worker)
            self.tasks.append(asyncio.create_task(worker.run_forever()))

    @on_stop
    async def _stop(self) -> None:
        self.logger.debug("Stopping multi-worker process %s", self.service_id)
        for task in self.tasks:
            task.cancel()
        for worker in self.workers:
            worker.stop_event.set()

    @on_cleanup
    async def _cleanup(self) -> None:
        self.logger.debug("Cleaning up multi-worker process %s", self.service_id)
        await asyncio.gather(*self.tasks)


def main() -> None:
    """Main entry point for the worker process."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(MultiWorkerProcess)


if __name__ == "__main__":
    sys.exit(main())
