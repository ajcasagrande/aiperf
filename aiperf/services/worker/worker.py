# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
import sys
import time

from aiperf.clients.openai.common import OpenAIClientConfig
from aiperf.common.comms.client_enums import (
    ClientType,
    PullClientType,
    PushClientType,
    ReqClientType,
)
from aiperf.common.config import EndPointConfig, ServiceConfig
from aiperf.common.constants import NANOS_PER_MILLIS
from aiperf.common.enums import InferenceClientType, MessageType, ServiceType, Topic
from aiperf.common.factories import InferenceClientFactory, ServiceFactory
from aiperf.common.hooks import (
    on_cleanup,
    on_init,
    on_run,
    on_stop,
)
from aiperf.common.interfaces import InferenceClientProtocol
from aiperf.common.models import (
    ConversationRequestMessage,
    CreditDropMessage,
    CreditReturnMessage,
    ErrorDetails,
    InferenceResultsMessage,
    RequestRecord,
)
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.common.service.base_service import BaseService


@ServiceFactory.register(ServiceType.WORKER)
class Worker(BaseService):
    """Worker is primarily responsible for converting the data into the appropriate
    format for the interface being used by the server. Also responsible for managing
    the conversation between turns.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)

        self.logger.info("Initializing %s", self.service_id)

        # Inference client will be initialized in _initialize
        self.inference_client: InferenceClientProtocol | None = None

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

        # TODO: better way to get the API key
        # Get API key from environment variable
        api_key = os.environ.get("OPENAI_API_KEY", None)

        # Create OpenAI client configuration
        openai_client_config = OpenAIClientConfig(
            api_key=api_key,
            url=f"http://127.0.0.1:{os.getenv('AIPERF_PORT', 8080)}",  # Default OpenAI inference server endpoint
            model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",  # Default model
        )

        # Initialize the OpenAI client
        self.inference_client = InferenceClientFactory.create_instance(
            InferenceClientType.OPENAI, config=openai_client_config
        )

        await self.comms.register_pull_callback(
            message_type=MessageType.CREDIT_DROP,
            callback=self._credit_drop_handler,
        )
        self.logger.debug("Worker initialized")

    async def _credit_drop_handler(self, message: CreditDropMessage) -> None:
        """Handle a credit drop message."""
        self.logger.debug("Received credit drop message: %s", message)
        _ = asyncio.create_task(self._process_credit_drop(message))

    async def _process_credit_drop(self, message: CreditDropMessage) -> None:
        """Process a credit drop response.

        Args:
            message: The message received from the credit drop
        """
        self.logger.debug("Processing credit drop: %s", message)

        credit_amount = 0
        tasks: list[asyncio.Task] = []
        try:
            # Extract the credit drop message payload

            credit_amount = message.amount
            self.logger.debug(
                "Received %s credit(s) for %s", credit_amount, message.credit_drop_ns
            )

            async def run_task():
                record = await self._call_inference_api(message.credit_drop_ns)
                try:
                    msg = InferenceResultsMessage(
                        service_id=self.service_id,
                        record=record,
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

            # Make a call to OpenAI API for each credit concurrently
            for _ in range(credit_amount):
                task = asyncio.create_task(run_task())
                tasks.append(task)

            await asyncio.gather(*tasks)

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

    async def _call_inference_api(
        self, credit_drop_ns: int | None = None
    ) -> RequestRecord:
        """Make a call to the inference API."""
        try:
            self.logger.debug("Calling inference API")

            if not self.inference_client:
                self.logger.warning(
                    "Inference server client not initialized, skipping API call"
                )
                return RequestRecord(
                    error=ErrorDetails(
                        type="Inference server client not initialized",
                        message="Inference server client not initialized",
                    ),
                )

            # retrieve the prompt from the dataset
            response = await self.comms.request(
                topic=Topic.CONVERSATION_DATA,
                message=ConversationRequestMessage(
                    service_id=self.service_id, conversation_id="123"
                ),
            )
            # messages = OpenAIChatCompletionRequest(
            #     model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
            #     messages=[
            #         {
            #             "role": "user",
            #             "content": "softly smiteth That from the cold stone sparks of fire do fly Whereat a waxen torch forthwith he lighteth Which must be lodestar to his lustful eye And to the flame thus speaks advisedly As from this cold flint I enforced this fire So Lucrece must I force to my desire Here pale with fear he doth premeditate The dangers of his loathsome enterprise And in his inward mind he doth debate What following sorrow may on this arise Then looking scorn",
            #         }
            #     ],
            #     max_tokens=100,
            # )

            # response.conversation_data

            # Sample messages for the API call
            # messages = [
            #     {"role": "system", "content": "You are a helpful assistant."},
            #     {
            #         "role": "user",
            #         "content": "Tell me about NVIDIA AI performance testing.",
            #     },
            # ]

            # Format payload for the API request
            formatted_payload = await self.inference_client.format_payload(
                endpoint=EndPointConfig(
                    type="v1/chat/completions",
                    streaming=True,
                    # model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
                ),
                payload={"messages": response.conversation_data},
            )

            delayed = False
            if credit_drop_ns and credit_drop_ns > time.time_ns():
                # self.logger.debug("Waiting for request timestamp to be reached")
                await asyncio.sleep((credit_drop_ns - time.time_ns()) / 1e9)
            elif credit_drop_ns and credit_drop_ns < time.time_ns():
                delayed = True

            # Send the request to the API
            record = await self.inference_client.send_request(
                endpoint=EndPointConfig(
                    type="v1/chat/completions",
                    streaming=True,
                    # model="deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
                ),
                payload=formatted_payload,
                delayed=delayed,
            )

            if record.valid:
                self.logger.debug(
                    "Record: %s milliseconds. %s milliseconds.",
                    record.time_to_first_response_ns / NANOS_PER_MILLIS,
                    record.time_to_last_response_ns / NANOS_PER_MILLIS,
                )
            else:
                self.logger.warning("Inference server call returned invalid response")

            return record

        except Exception as e:
            self.logger.error(
                "Error calling inference server: %s %s", e.__class__.__name__, str(e)
            )
            return RequestRecord(
                error=ErrorDetails(
                    type=e.__class__.__name__,
                    message=str(e),
                ),
            )


@ServiceFactory.register(ServiceType.MULTI_WORKER_PROCESS)
class MultiWorkerProcess(BaseComponentService):
    """MultiWorkerProcess is a process that runs multiple workers as concurrent tasks on the event loop."""

    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
    ):
        super().__init__(service_config=service_config, service_id=service_id)

        self.logger.debug("Initializing worker process")
        self.workers: list[Worker] = []
        self.tasks: list[asyncio.Task] = []
        self.worker_count = int(os.getenv("AIPERF_TASKS_PER_WORKER", 1))

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
        for i in range(self.worker_count):
            worker = Worker(
                service_config=self.service_config,
                service_id=f"{self.service_id}_{i}",
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
