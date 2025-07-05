# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import os
import sys
import time

import psutil

from aiperf.clients.openai.common import OpenAIChatCompletionRequest, OpenAIClientConfig
from aiperf.common.comms.base import (
    BaseCommunication,
    CommunicationFactory,
    PubClientProtocol,
    PullClientProtocol,
    PushClientProtocol,
    RequestClientProtocol,
)
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.constants import (
    BYTES_PER_MIB,
    NANOS_PER_SECOND,
    TASK_CANCEL_TIMEOUT_SHORT,
)
from aiperf.common.enums import (
    CommunicationClientAddressType,
    InferenceClientType,
    MessageType,
    ModelSelectionStrategy,
    RequestPayloadType,
    ServiceType,
)
from aiperf.common.factories import InferenceClientFactory, ServiceFactory
from aiperf.common.hooks import (
    aiperf_task,
    on_configure,
    on_init,
    on_stop,
)
from aiperf.common.interfaces import InferenceClientProtocol
from aiperf.common.messages import (
    CommandMessage,
    ConversationRequestMessage,
    ConversationResponseMessage,
    CPUTimes,
    CreditDropMessage,
    CreditReturnMessage,
    CtxSwitches,
    ErrorMessage,
    InferenceResultsMessage,
    WorkerHealthMessage,
)
from aiperf.common.mixins import AsyncTaskManagerMixin
from aiperf.common.record_models import ErrorDetails, RequestRecord
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.common.types import EndpointInfo, ModelEndpointInfo, ModelInfo


@ServiceFactory.register(ServiceType.WORKER)
class Worker(BaseComponentService, AsyncTaskManagerMixin):
    """Worker is primarily responsible for converting the data into the appropriate
    format for the interface being used by the server. Also responsible for managing
    the conversation between turns.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
    ):
        super().__init__(service_config=service_config, service_id=service_id)

        self.logger.debug("Initializing worker process")
        self.user_config: UserConfig | None = None
        self.model_endpoint: ModelEndpointInfo | None = None

        # Inference client will be initialized in _initialize
        self.inference_client: InferenceClientProtocol | None = None

        self.health_check_interval = int(
            os.getenv("AIPERF_WORKER_HEALTH_CHECK_INTERVAL", 1)
        )
        self.begin_time = time.time()
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.total_tasks = 0

        # Initialize process-specific CPU monitoring
        self.process = psutil.Process()
        self.process.cpu_percent()  # throw away the first result (will be 0)

        self.stop_event: asyncio.Event = asyncio.Event()
        self.health_task: asyncio.Task | None = None

        self.comms: BaseCommunication = CommunicationFactory.create_instance(
            self.service_config.comm_backend,
            config=self.service_config.comm_config,
        )

        self.credit_drop_client: PullClientProtocol = self.comms.create_pull_client(
            CommunicationClientAddressType.CREDIT_DROP,
        )
        self.credit_return_client: PushClientProtocol = self.comms.create_push_client(
            CommunicationClientAddressType.CREDIT_RETURN,
        )
        self.inference_results_client: PushClientProtocol = (
            self.comms.create_push_client(
                CommunicationClientAddressType.RAW_INFERENCE_PROXY_FRONTEND,
            )
        )
        self.conversation_data_client: RequestClientProtocol = (
            self.comms.create_request_client(
                CommunicationClientAddressType.DATASET_MANAGER_PROXY_FRONTEND,
            )
        )
        self.pub_client: PubClientProtocol = self.comms.create_pub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
        )

        api_key = os.environ.get("OPENAI_API_KEY", None)

        # Default OpenAI inference server endpoint
        openai_client_config = OpenAIClientConfig(
            api_key=api_key,
            base_url=f"http://{os.getenv('AIPERF_HOST', '127.0.0.1')}:{os.getenv('AIPERF_PORT', 8080)}",
        )
        self.model_endpoint = ModelEndpointInfo(
            models=[
                ModelInfo(
                    name=os.getenv(
                        "AIPERF_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
                    )
                )
            ],
            endpoint=EndpointInfo(
                type=RequestPayloadType.OPENAI_CHAT_COMPLETIONS,
                streaming=os.getenv("AIPERF_STREAMING", "true").lower() == "true",
            ),
            model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
        )

        self.inference_client = InferenceClientFactory.create_instance(
            InferenceClientType.OPENAI, client_config=openai_client_config
        )

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.WORKER

    @on_init
    async def _do_initialize(self) -> None:
        """Initialize worker-specific components."""
        self.logger.debug("Initializing worker")
        await self.comms.initialize()

        await self.credit_drop_client.register_pull_callback(
            MessageType.CREDIT_DROP, self._process_credit_drop
        )

        self.logger.debug("Worker initialized")

    @on_configure
    async def _configure(self, message: CommandMessage) -> None:
        self.logger.debug("Configuring worker process %s", self.service_id)
        # if not isinstance(message.data, UserConfig):
        #     raise ConfigurationError("Invalid user config")

        # self.user_config = cast(UserConfig, message.data)

        # TODO: better way to get the API key
        api_key = os.environ.get("OPENAI_API_KEY", None)

        # Default OpenAI inference server endpoint
        openai_client_config = OpenAIClientConfig(
            api_key=api_key,
            base_url=f"http://{os.getenv('AIPERF_HOST', '127.0.0.1')}:{os.getenv('AIPERF_PORT', 8080)}",
        )
        self.model_endpoint = ModelEndpointInfo(
            models=[
                ModelInfo(
                    name=os.getenv(
                        "AIPERF_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
                    )
                )
            ],
            endpoint=EndpointInfo(
                type=RequestPayloadType.OPENAI_CHAT_COMPLETIONS,
                streaming=os.getenv("AIPERF_STREAMING", "true").lower() == "true",
            ),
            model_selection_strategy=ModelSelectionStrategy.ROUND_ROBIN,
        )

        self.inference_client = InferenceClientFactory.create_instance(
            InferenceClientType.OPENAI, client_config=openai_client_config
        )

    async def _process_credit_drop(self, message: CreditDropMessage) -> None:
        """Process a credit drop message.

        Args:
            message: The message received from the credit drop
        """

        # NOTE: This function MUST NOT return until the credit drop is processed,
        #       that way the max concurrency is respected via the semaphore

        self.logger.debug("Processing credit drop: %s", message)

        try:
            self.logger.debug("Received credit drop for %s", message.conversation_id)

            # Make a call to the inference server for each credit concurrently, and then wait
            # for all the tasks to complete
            await self._execute_single_credit(
                credit_drop_ns=message.credit_drop_ns,
                conversation_id=message.conversation_id,
            )

        except Exception as e:
            self.logger.error("Error processing credit drop: %s", e)

        finally:
            # Always return the credits
            self.logger.debug("Returning credits for %s", message.conversation_id)
            await self.credit_return_client.push(
                message=CreditReturnMessage(
                    service_id=self.service_id,
                    conversation_id=message.conversation_id,
                ),
            )

    async def _execute_single_credit(
        self, credit_drop_ns: int | None = None, conversation_id: str | None = None
    ) -> None:
        """Run a credit task for a single credit."""
        self.total_tasks += 1
        # Call the inference API
        record = await self._call_inference_api(
            credit_drop_ns=credit_drop_ns, conversation_id=conversation_id
        )
        msg = InferenceResultsMessage(
            service_id=self.service_id,
            record=record,
        )
        if record.valid:
            self.completed_tasks += 1
        else:
            self.failed_tasks += 1

        # Push the record to the inference results message_type
        try:
            await self.inference_results_client.push(message=msg)
        except Exception as e:
            # If we fail to push the record, log the error and continue
            self.logger.error(
                "Error pushing request record: %s: %s",
                e.__class__.__name__,
                e,
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
                    ConversationRequestMessage(
                        service_id=self.service_id, conversation_id=conversation_id
                    )
                )
            )
            self.logger.debug("Received response message: %s", response)

            if isinstance(response, ErrorMessage):
                return RequestRecord(
                    timestamp_ns=time.time_ns(),
                    start_perf_ns=time.perf_counter_ns(),
                    end_perf_ns=time.perf_counter_ns(),
                    error=response.error,
                )

            # # Format payload for the API request
            # formatted_payload = await self.inference_client.format_payload(
            #     model_endpoint=self.model_endpoint,
            #     turn=response.conversation.turns[0],  # todo: handle multiple turns
            #     # payload={
            #     #     "messages": [
            #     #         {
            #     #             "role": "user",
            #     #             "content": "IO Sir you say well and well you do conceive And since you do profess to be a suitor You must as we do gratify this gentleman To whom we all rest generally beholding TRANIO Sir I shall not be slack in sign whereof Please ye we may contrive this afternoon And quaff carouses to our mistress health And do as adversaries do in law Strive mightily but eat and drink as friends GRUMIO BIONDELLO O excellent motion Fellows lets be gone HORT",
            #     #         },
            #     #     ],
            #     # },
            # )

            formatted_payload = OpenAIChatCompletionRequest(
                messages=[
                    {
                        "role": "user",
                        "content": "IO Sir you say well and well you do conceive And since you do profess to be a suitor You must as we do gratify this gentleman To whom we all rest generally beholding TRANIO Sir I shall not be slack in sign whereof Please ye we may contrive this afternoon And quaff carouses to our mistress health And do as adversaries do in law Strive mightily but eat and drink as friends GRUMIO BIONDELLO O excellent motion Fellows lets be gone HORT",
                    },
                ],
                model=self.model_endpoint.models[0].name,
                max_tokens=100,
                stream=True,
            )

            delayed = False
            if credit_drop_ns and credit_drop_ns > time.time_ns():
                await asyncio.sleep(
                    (credit_drop_ns - time.time_ns()) / NANOS_PER_SECOND
                )
            elif credit_drop_ns and credit_drop_ns < time.time_ns():
                delayed = True

            # Send the request to the Inference Server API and wait for the response
            return await self.inference_client.send_request(
                model_endpoint=self.model_endpoint,
                payload=formatted_payload,
                delayed=delayed,
            )

        except Exception as e:
            self.logger.error(
                "Error calling inference server API at %s: %s %s",
                self.model_endpoint.endpoint,
                e.__class__.__name__,
                str(e),
            )
            return RequestRecord(
                error=ErrorDetails.from_exception(e),
            )

    @aiperf_task
    async def _health_check_task(self) -> None:
        """Task to report the health of the worker to the worker manager."""
        while not self.stop_event.is_set():
            try:
                health_message = self.create_health_message()
                await self.pub_client.publish(health_message)
            except Exception as e:
                self.logger.error("Error reporting health: %s", e)
            await asyncio.sleep(self.health_check_interval)

    def create_health_message(self) -> WorkerHealthMessage:
        """Create a health message for the worker."""
        # Get process-specific CPU and memory usage
        return WorkerHealthMessage(
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
            cpu_times=CPUTimes(
                *self.process.cpu_times()[:2], self.process.cpu_times()[4]
            ),
            num_ctx_switches=CtxSwitches(*self.process.num_ctx_switches()),
            num_threads=self.process.num_threads(),
        )

    @on_stop
    async def _do_shutdown(self) -> None:
        """Shutdown the worker."""
        self.logger.debug("Shutting down worker")
        self.stop_event.set()
        if self.comms:
            await self.comms.shutdown()
        if self.inference_client:
            await self.inference_client.close()
        if self.health_task:
            self.health_task.cancel()
            await asyncio.wait_for(self.health_task, timeout=TASK_CANCEL_TIMEOUT_SHORT)


def main() -> None:
    """Main entry point for the worker process."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(Worker)


if __name__ == "__main__":
    sys.exit(main())
