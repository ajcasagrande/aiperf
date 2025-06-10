# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import copy
import os
import sys

from aiperf.backend.openai_client_httpx import OpenAIBackendClientConfig
from aiperf.common.comms.client_enums import (
    ClientType,
    DealerClientType,
    PullClientType,
    PushClientType,
)
from aiperf.common.config.service_config import ServiceConfig
from aiperf.common.constants import NANOS_PER_MILLIS
from aiperf.common.enums import BackendClientType, MessageType, ServiceType, Topic
from aiperf.common.factories import BackendClientFactory
from aiperf.common.hooks import on_init, on_run, on_start
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
        self.max_concurrency = int(os.getenv("AIPERF_TASKS_PER_WORKER", 100))
        self.semaphore = asyncio.Semaphore(self.max_concurrency)

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
            DealerClientType.CONVERSATION_DATA,
        ]

    @on_init
    async def _initialize(self) -> None:
        """Initialize worker-specific components."""
        self.logger.debug("Initializing worker")

        # Pull credit drops
        await self.comms.register_pull_callback(
            message_type=MessageType.CREDIT_DROP,
            callback=self._process_credit_drop,
        )

        # Get API key from environment variable or use a default for testing
        api_key = os.environ.get("OPENAI_API_KEY", "sk-fakeai-1234567890abcdef")

        # Create OpenAI client configuration
        openai_client_config = OpenAIBackendClientConfig(
            api_key=api_key,
            url="http://127.0.0.1:8080",  # Default OpenAI API endpoint
            model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",  # Default model
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

    async def _task_done_callback(self, task: asyncio.Task) -> None:
        """Callback for when a task is done."""
        try:
            self.logger.debug("Task done callback")
            msg = InferenceResultsMessage(
                service_id=self.service_id,
                record=copy.deepcopy(task.result()),
            )
            # self.logger.debug(f"Pushing request record: {msg}")
            await self.comms.push(
                topic=Topic.INFERENCE_RESULTS,
                message=msg,
            )
        except asyncio.CancelledError:
            pass  # Task was cancelled
        except Exception as e:
            self.logger.error(
                f"Error pushing request record: {e.__class__.__name__}: {e}"
            )
        finally:
            self.semaphore.release()
            # Always return the credits
            self.logger.debug("Returning credits, %s", 1)
            await self.comms.push(
                topic=Topic.CREDIT_RETURN,
                message=CreditReturnMessage(service_id=self.service_id, amount=1),
            )

    async def _process_credit_drop(self, message: CreditDropMessage) -> None:
        """Process a credit drop message.

        Args:
            message: The message received from the credit drop
        """
        self.logger.debug(f"Processing credit drop: {message}")

        await self.semaphore.acquire()
        try:
            task = asyncio.create_task(self._call_backend_api())
            task.add_done_callback(self._task_done_callback)

        except asyncio.CancelledError:
            pass  # Task was cancelled
        except Exception as e:
            self.logger.error(f"Error processing credit drop: {e}")

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
            self.logger.debug("Response: %s", response)
            messages = response.conversation_data

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
                    f"Record: {record.time_to_first_response_ns / NANOS_PER_MILLIS} milliseconds. {record.time_to_last_response_ns / NANOS_PER_MILLIS} milliseconds."
                )
            else:
                self.logger.warning("Backend API call returned invalid response")

            return record

        except asyncio.CancelledError:
            self.logger.debug("Task cancelled")
            return RequestErrorRecord(
                error="Task cancelled",
            )

        except Exception as e:
            self.logger.error(
                "Error calling backend API: %s %s", e.__class__.__name__, str(e)
            )
            return RequestErrorRecord(
                error=f"{e.__class__.__name__}: {e}",
            )


def main() -> None:
    """Main entry point for the worker process."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(Worker)


if __name__ == "__main__":
    sys.exit(main())
