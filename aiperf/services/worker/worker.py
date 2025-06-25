# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
import sys
import time

import psutil

from aiperf.clients.openai.common import OpenAIClientConfig
from aiperf.common.comms.base import (
    PullClientInterface,
    PushClientInterface,
    ReqClientInterface,
)
from aiperf.common.config import EndPointConfig, ServiceConfig
from aiperf.common.constants import BYTES_PER_MIB, NANOS_PER_MILLIS
from aiperf.common.enums import InferenceClientType, MessageType, ServiceType, Topic
from aiperf.common.factories import InferenceClientFactory, ServiceFactory
from aiperf.common.hooks import (
    aiperf_task,
    on_cleanup,
    on_init,
    on_run,
    on_stop,
)
from aiperf.common.interfaces import InferenceClientProtocol
from aiperf.common.models import (
    ConversationRequestMessage,
    ConversationResponseMessage,
    CreditDropMessage,
    CreditReturnMessage,
    ErrorDetails,
    InferenceResultsMessage,
    RequestRecord,
)
from aiperf.common.models.messages import WorkerHealthMessage
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

        self.logger.debug("Initializing %s", self.service_id)

        # Inference client will be initialized in _initialize
        self.inference_client: InferenceClientProtocol | None = None

        self.endpoint_config = EndPointConfig(
            type=os.getenv("AIPERF_ENDPOINT", "v1/chat/completions"),
            streaming=os.getenv("AIPERF_STREAMING", "true").lower() == "true",
        )

        self.health_check_interval = int(os.getenv("AIPERF_HEALTH_CHECK_INTERVAL", 10))
        self.begin_time = time.time()
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.total_tasks = 0

        # Initialize process-specific CPU monitoring
        self.process = psutil.Process()
        self.process.cpu_percent()  # throw away the first result (will be 0)

        self.credit_drop_client: PullClientInterface
        self.credit_return_client: PushClientInterface
        self.inference_results_client: PushClientInterface
        self.conversation_data_client: ReqClientInterface

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER

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
            url=f"http://{os.getenv('AIPERF_HOST', '127.0.0.1')}:{os.getenv('AIPERF_PORT', 8080)}",  # Default OpenAI inference server endpoint
            model=os.getenv(
                "AIPERF_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
            ),  # Default model
        )

        # Initialize the OpenAI client
        self.inference_client = InferenceClientFactory.create_instance(
            InferenceClientType.OPENAI, client_config=openai_client_config
        )

        self.credit_drop_client = await self.comms.create_pull_client(
            address=self.service_config.comm_config.credit_drop_address,
        )
        await self.credit_drop_client.initialize()

        self.credit_return_client = await self.comms.create_push_client(
            address=self.service_config.comm_config.credit_return_address,
        )
        await self.credit_return_client.initialize()

        self.inference_results_client = await self.comms.create_push_client(
            address=self.service_config.comm_config.inference_push_pull_address,
        )
        await self.inference_results_client.initialize()

        self.conversation_data_client = await self.comms.create_req_client(
            address=self.service_config.comm_config.conversation_data_address,
        )
        await self.conversation_data_client.initialize()

        await self.credit_drop_client.register_pull_callback(
            message_type=MessageType.CREDIT_DROP,
            callback=self._credit_drop_handler,
        )

        self.logger.debug("Worker initialized")

    async def _credit_drop_handler(self, message: CreditDropMessage) -> None:
        """Handle a credit drop message."""
        self.logger.debug("Received credit drop message: %s", message)
        await self._process_credit_drop(message)

    async def _run_credit_task(self, credit_drop_ns: int | None = None) -> None:
        """Run a credit task for a single credit."""
        self.total_tasks += 1
        # Call the inference API
        record = await self._call_inference_api(credit_drop_ns)
        msg = InferenceResultsMessage(
            service_id=self.service_id,
            record=record,
        )
        if record.valid:
            self.completed_tasks += 1
        else:
            self.failed_tasks += 1

        # Push the record to the inference results topic
        try:
            await self.inference_results_client.push(
                message=msg,
            )
        except Exception as e:
            # If we fail to push the record, log the error and continue
            self.logger.error(
                "Error pushing request record: %s: %s",
                e.__class__.__name__,
                e,
            )

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

            # Make a call to OpenAI API for each credit concurrently
            for _ in range(credit_amount):
                task = asyncio.create_task(
                    self._run_credit_task(credit_drop_ns=message.credit_drop_ns)
                )
                tasks.append(task)

            await asyncio.gather(*tasks)

        except Exception as e:
            self.logger.error("Error processing credit drop: %s", e)

        finally:
            # Always return the credits
            self.logger.debug("Returning credits, %s", credit_amount)
            await self.credit_return_client.push(
                message=CreditReturnMessage(
                    service_id=self.service_id,
                    amount=credit_amount,
                ),
            )

    async def _call_inference_api(
        self, credit_drop_ns: int | None = None, conversation_id: str | None = None
    ) -> RequestRecord:
        """Make a single call to the inference API. Will return an error record if the call fails."""
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
            response: ConversationResponseMessage = (
                await self.conversation_data_client.request(
                    message=ConversationRequestMessage(
                        service_id=self.service_id, conversation_id=conversation_id
                    ),
                )
            )

            # Format payload for the API request
            formatted_payload = await self.inference_client.format_payload(
                endpoint=self.endpoint_config,
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
                endpoint=self.endpoint_config,
                payload=formatted_payload,
                delayed=delayed,
            )

            if record.valid:
                self.logger.debug(
                    "Record: %s milliseconds. %s milliseconds.",
                    record.time_to_first_response_ns / NANOS_PER_MILLIS
                    if record.time_to_first_response_ns
                    else None,
                    record.time_to_last_response_ns / NANOS_PER_MILLIS
                    if record.time_to_last_response_ns
                    else None,
                )
            else:
                self.logger.warning("Inference server call returned invalid response")

            return record

        except Exception as e:
            self.logger.error(
                "Error calling inference server: %s %s", e.__class__.__name__, str(e)
            )
            return RequestRecord(
                error=ErrorDetails.from_exception(e),
            )

    @aiperf_task
    async def _health_check_task(self) -> None:
        """Health check task."""
        while not self.stop_event.is_set():
            try:
                await self._report_health()
            except Exception as e:
                self.logger.error("Error reporting health: %s", e)
            await asyncio.sleep(self.health_check_interval)

    async def _report_health(self) -> None:
        """Report the health of the worker to the worker manager."""

        # Get process-specific CPU and memory usage
        await self.pub_client.publish(
            topic=Topic.WORKER_HEALTH,
            message=WorkerHealthMessage(
                service_id=self.service_id,
                pid=self.process.pid,
                cpu_usage=self.process.cpu_percent(),
                memory_usage=self.process.memory_info().rss / BYTES_PER_MIB,
                uptime=time.time() - self.begin_time,
                completed_tasks=self.completed_tasks,
                failed_tasks=self.failed_tasks,
                total_tasks=self.total_tasks,
                timestamp_ns=time.time_ns(),
                net_connections=len(self.process.net_connections("tcp4")),
                io_counters=self.process.io_counters(),
                cpu_times=self.process.cpu_times(),
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
