# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import logging
import os
import sys
import time

from aiperf.clients import InferenceClientFactory
from aiperf.clients.client_interfaces import RequestConverterFactory
from aiperf.clients.model_endpoint_info import ModelEndpointInfo
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
    NANOS_PER_SECOND,
)
from aiperf.common.dataset_models import Turn
from aiperf.common.enums import (
    CommunicationClientAddressType,
    CreditPhase,
    MessageType,
    ServiceType,
)
from aiperf.common.exceptions import NotInitializedError
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import (
    aiperf_task,
    on_configure,
    on_init,
    on_stop,
)
from aiperf.common.messages import (
    CommandMessage,
    ConversationRequestMessage,
    ConversationResponseMessage,
    CreditDropMessage,
    CreditReturnMessage,
    ErrorMessage,
    InferenceResultsMessage,
)
from aiperf.common.mixins import AsyncTaskManagerMixin, ProcessHealthMixin
from aiperf.common.record_models import ErrorDetails, RequestRecord
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.common.worker_models import WorkerHealthMessage, WorkerPhaseTaskStats


@ServiceFactory.register(ServiceType.WORKER)
class Worker(BaseComponentService, AsyncTaskManagerMixin, ProcessHealthMixin):
    """Worker is primarily responsible for converting the data into the appropriate
    format for the interface being used by the server. Also responsible for managing
    the conversation between turns.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
    ):
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )

        self.logger = logging.getLogger(self.service_id)
        self.logger.debug("Initializing worker process: %s", self.process.pid)

        self.health_check_interval = int(
            os.getenv("AIPERF_WORKER_HEALTH_CHECK_INTERVAL", 1)
        )

        self.task_stats: dict[CreditPhase, WorkerPhaseTaskStats] = {
            phase: WorkerPhaseTaskStats(
                total=0,
                completed=0,
                failed=0,
            )
            for phase in CreditPhase
        }

        self.stop_event: asyncio.Event = asyncio.Event()
        self.comms: BaseCommunication = CommunicationFactory.create_instance(
            self.service_config.comm_backend,
            config=self.service_config.comm_config,
        )

        self.credit_drop_client: PullClientProtocol = self.comms.create_pull_client(
            CommunicationClientAddressType.CREDIT_DROP,
        )  # type: ignore
        self.credit_return_client: PushClientProtocol = self.comms.create_push_client(
            CommunicationClientAddressType.CREDIT_RETURN,
        )  # type: ignore
        self.inference_results_client: PushClientProtocol = (
            self.comms.create_push_client(
                CommunicationClientAddressType.RAW_INFERENCE_PROXY_FRONTEND,
            )
        )  # type: ignore
        self.conversation_data_client: RequestClientProtocol = (
            self.comms.create_request_client(
                CommunicationClientAddressType.DATASET_MANAGER_PROXY_FRONTEND,
            )
        )  # type: ignore
        self.pub_client: PubClientProtocol = self.comms.create_pub_client(
            CommunicationClientAddressType.EVENT_BUS_PROXY_FRONTEND,
        )  # type: ignore

        self.model_endpoint = ModelEndpointInfo.from_user_config(self.user_config)

        self.logger.debug(
            "Creating inference client for %s, class: %s",
            self.model_endpoint.endpoint.type,
            InferenceClientFactory.get_class_from_type(
                self.model_endpoint.endpoint.type
            ).__name__,
        )
        self.request_converter = RequestConverterFactory.create_instance(
            self.model_endpoint.endpoint.type,
        )
        self.inference_client = InferenceClientFactory.create_instance(
            self.model_endpoint.endpoint.type,
            model_endpoint=self.model_endpoint,
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
        pass

    async def _process_credit_drop(self, message: CreditDropMessage) -> None:
        """Process a credit drop message.

        Args:
            message: The message received from the credit drop
        """

        # NOTE: This function MUST NOT return until the credit drop is processed,
        #       that way the max concurrency is respected via the semaphore

        # TODO: Add tests to ensure that the above is never violated in the future

        self.logger.debug("Processing credit drop: %s", message)

        record: RequestRecord = RequestRecord()
        try:
            record = await self._execute_single_credit(message)

        except Exception as e:
            self.logger.exception("Error processing credit drop: %s", e)
            record.error = ErrorDetails.from_exception(e)
            record.end_perf_ns = time.perf_counter_ns()

        finally:
            record.credit_phase = message.credit_phase
            msg = InferenceResultsMessage(
                service_id=self.service_id,
                record=record,
            )

            self.task_stats[message.credit_phase].total += 1
            if not record.valid:
                self.task_stats[message.credit_phase].failed += 1
            else:
                self.task_stats[message.credit_phase].completed += 1

            try:
                await self.inference_results_client.push(message=msg)
            except Exception as e:
                # If we fail to push the record, log the error and continue
                self.logger.exception("Error pushing request record: %s", e)
            finally:
                # Always return the credits
                self.logger.debug("Returning credits for %s", message.conversation_id)
                await self.credit_return_client.push(
                    message=CreditReturnMessage(
                        service_id=self.service_id,
                        conversation_id=message.conversation_id,
                        credit_drop_ns=message.credit_drop_ns,
                        delayed_ns=None,
                        credit_phase=message.credit_phase,
                    ),
                )

    async def _execute_single_credit(
        self,
        message: CreditDropMessage,
    ) -> RequestRecord:
        """Run a credit task for a single credit."""
        self.task_stats[message.credit_phase].total += 1

        if not self.inference_client:
            raise NotInitializedError("Inference server client not initialized.")

        # retrieve the prompt from the dataset
        response: ConversationResponseMessage = (
            await self.conversation_data_client.request(
                ConversationRequestMessage(
                    service_id=self.service_id,
                    conversation_id=message.conversation_id,
                    credit_phase=message.credit_phase,
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

        return await self._call_inference_api(message, response.conversation.turns[0])

    async def _call_inference_api(
        self, message: CreditDropMessage, turn: Turn
    ) -> RequestRecord:
        """Make a single call to the inference API. Will return an error record if the call fails."""
        try:
            self.logger.debug("Calling inference API")

            # Format payload for the API request
            formatted_payload = await self.request_converter.format_payload(
                model_endpoint=self.model_endpoint,
                turn=turn,
            )

            delayed_ns = None
            drop_ns = message.credit_drop_ns
            now_ns = time.time_ns()
            if drop_ns and drop_ns > now_ns:
                await asyncio.sleep((drop_ns - now_ns) / NANOS_PER_SECOND)
            elif drop_ns and drop_ns < now_ns:
                delayed_ns = drop_ns - now_ns

            # Send the request to the Inference Server API and wait for the response
            result = await self.inference_client.send_request(
                model_endpoint=self.model_endpoint,
                payload=formatted_payload,
            )

            result.delayed_ns = delayed_ns
            return result

        except Exception as e:
            self.logger.exception(
                "Error calling inference server API at %s", self.model_endpoint.url
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

        return WorkerHealthMessage(
            service_id=self.service_id,
            process=self.get_process_health(),
            task_stats=self.task_stats,
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


def main() -> None:
    """Main entry point for the worker process."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(Worker)


if __name__ == "__main__":
    sys.exit(main())
