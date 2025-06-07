# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import copy
import os
import sys
import uuid

from aiperf.backend.openai_common import OpenAIBackendClientConfig
from aiperf.common.comms.client_enums import (
    ClientType,
    PullClientType,
    PushClientType,
    ReqClientType,
)
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.constants import NANOS_PER_MILLIS
from aiperf.common.enums import BackendClientType, MessageType, ServiceType, Topic
from aiperf.common.factories import BackendClientFactory
from aiperf.common.hooks import (
    aiperf_task,
    on_cleanup,
    on_init,
    on_run,
    on_start,
    on_stop,
)
from aiperf.common.interfaces import BackendClientProtocol
from aiperf.common.messages import (
    ConversationRequestMessage,
    CreditDropMessage,
    CreditReturnMessage,
    InferenceResultsMessage,
)
from aiperf.common.record_models import (
    RequestErrorRecord,
    RequestRecord,
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
            url=f"http://127.0.0.1:{os.getenv('AIPERF_PORT', 8080)}",  # Default OpenAI API endpoint
            model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",  # Default model
        )

        # Initialize the OpenAI client
        self.backend_client = BackendClientFactory.create_instance(
            BackendClientType.OPENAI, config=openai_client_config
        )

        self.queue = asyncio.Queue(
            maxsize=int(os.getenv("AIPERF_TASKS_PER_WORKER", 100))
        )
        self.logger.debug("Backend client initialized")

    @on_run
    async def _run(self) -> None:
        """Automatically start the worker in the run method."""
        await self.start()

    @on_start
    async def _start(self) -> None:
        """Start the worker."""
        # self.logger.debug("Starting worker")
        # Pull credit drops
        await self.comms.register_pull_callback(
            message_type=MessageType.CREDIT_DROP,
            callback=self._credit_drop_handler,
        )

    @on_stop
    async def _stop(self) -> None:
        """Stop the worker."""
        # self.logger.debug("Stopping worker")

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up worker-specific components."""
        # self.logger.debug("Cleaning up worker")

    @aiperf_task
    async def _queue_drainer(self) -> None:
        """Background task for draining the queue."""
        while not self.is_shutdown:
            message = await self.queue.get()
            self.logger.debug("Received message from queue: %s", message)
            task = asyncio.create_task(self._process_credit_drop(message))
            task.add_done_callback(self._queue_drainer_done_callback)

    async def _credit_drop_handler(self, message: CreditDropMessage) -> None:
        """Handle a credit drop message."""
        self.logger.debug("Received credit drop message: %s", message)
        await self.queue.put(message)
        self.logger.debug("Put message into queue")

    def _queue_drainer_done_callback(self, task: asyncio.Task) -> None:
        """Callback for the queue drainer task."""
        self.logger.debug("Queue drainer task done: %s", task)

    async def _process_credit_drop(self, message: CreditDropMessage) -> None:
        """Process a credit drop response.

        Args:
            message: The message received from the credit drop
        """
        self.logger.debug("Processing credit drop: %s", message)

        credit_amount = 0
        try:
            # Extract the credit drop message payload

            credit_amount = message.amount
            self.logger.debug("Received %s credit(s)", credit_amount)

            # Make a call to OpenAI API for each credit
            for _ in range(credit_amount):
                record = await self._call_backend_api()

                try:
                    msg = InferenceResultsMessage(
                        service_id=self.service_id,
                        record=copy.deepcopy(record),
                    )
                    # self.logger.debug(f"Pushing request record: {msg}")
                    await self.comms.push(
                        topic=Topic.INFERENCE_RESULTS,
                        message=msg,
                    )
                except Exception as e:
                    self.logger.error(
                        "Error pushing request record: %s: %s",
                        e.__class__.__name__,
                        e,
                    )

        except Exception as e:
            self.logger.error("Error processing credit drop: %s", e)

        finally:
            # Always return the credits
            self.logger.debug("Returning credits, %s", credit_amount)
            await self.comms.push(
                topic=Topic.CREDIT_RETURN,
                message=CreditReturnMessage(
                    service_id=self.service_id,
                    amount=credit_amount,
                ),
            )

    async def _call_backend_api(self) -> RequestErrorRecord | RequestRecord:
        """Make a call to the backend API."""
        try:
            self.logger.debug("Calling backend API")

            if not self.backend_client:
                self.logger.warning("Backend client not initialized, skipping API call")
                return RequestErrorRecord(
                    error="Backend client not initialized",
                )

            # retrieve the prompt from the dataset
            response = await self.comms.request(
                topic=Topic.CONVERSATION_DATA,
                message=ConversationRequestMessage(
                    service_id=self.service_id, conversation_id="123"
                ),
            )
            messages = response.conversation_data

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

            if isinstance(record, RequestRecord) and record.valid:
                self.logger.debug(
                    "Record: %s milliseconds. %s milliseconds.",
                    record.time_to_first_response_ns / NANOS_PER_MILLIS,
                    record.time_to_last_response_ns / NANOS_PER_MILLIS,
                )
            else:
                self.logger.warning("Backend API call returned invalid response")

            return record

        except Exception as e:
            self.logger.error(
                "Error calling backend API: %s %s", e.__class__.__name__, str(e)
            )
            return RequestErrorRecord(
                error=f"{e.__class__.__name__}: {e}",
            )


class MultiWorkerProcess(BaseComponentService):
    """MultiWorkerProcess is a process that runs multiple workers as concurrent tasks on the event loop."""

    def __init__(self, service_config: ServiceConfig, service_id: str | None = None):
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing worker process")
        self.workers: list[Worker] = []
        self.tasks: list[asyncio.Task] = []
        self.worker_count = int(os.getenv("AIPERF_TASKS_PER_WORKER", 100))

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
