# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio
import sys
import time

from aiperf.clients import InferenceClientFactory
from aiperf.clients.client_interfaces import RequestConverterFactory
from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.comms.base import (
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
    WorkerHealthMessage,
)
from aiperf.common.mixins import ProcessHealthMixin
from aiperf.common.record_models import ErrorDetails, RequestRecord
from aiperf.common.service.base_component_service import BaseComponentService
from aiperf.common.worker_models import WorkerPhaseTaskStats


@ServiceFactory.register(ServiceType.WORKER)
class Worker(BaseComponentService, ProcessHealthMixin):
    """Worker is primarily responsible for making API calls to the inference server.
    It also manages the conversation between turns and returns the results to the Inference Results Parsers.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig | None = None,
        service_id: str | None = None,
        **kwargs,
    ):
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
            **kwargs,
        )

        self.debug(lambda: f"Initializing worker process: {self.process.pid}")

        self.health_check_interval = (
            self.service_config.workers.health_check_interval_seconds
        )

        self.task_stats: dict[CreditPhase, WorkerPhaseTaskStats] = {}

        self.credit_drop_pull_client: PullClientProtocol = (
            self.comms.create_pull_client(
                CommunicationClientAddressType.CREDIT_DROP,
            )
        )
        self.credit_return_push_client: PushClientProtocol = (
            self.comms.create_push_client(
                CommunicationClientAddressType.CREDIT_RETURN,
            )
        )
        self.inference_results_push_client: PushClientProtocol = (
            self.comms.create_push_client(
                CommunicationClientAddressType.RAW_INFERENCE_PROXY_FRONTEND,
            )
        )
        self.conversation_request_client: RequestClientProtocol = (
            self.comms.create_request_client(
                CommunicationClientAddressType.DATASET_MANAGER_PROXY_FRONTEND,
            )
        )

        self.model_endpoint = ModelEndpointInfo.from_user_config(self.user_config)

        self.debug(
            lambda: f"Creating inference client for {self.model_endpoint.endpoint.type}, "
            f"class: {InferenceClientFactory.get_class_from_type(self.model_endpoint.endpoint.type).__name__}",
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
        return ServiceType.WORKER

    @on_init
    async def _initialize_worker(self) -> None:
        self.debug("Initializing worker")

        await self.credit_drop_pull_client.register_pull_callback(
            MessageType.CREDIT_DROP, self._on_credit_drop
        )

        self.debug("Worker initialized")

    @on_configure
    async def _configure_worker(self, message: CommandMessage) -> None:
        # NOTE: Right now we are configuring the worker in the __init__ method,
        #       but that may change based on how we implement sweeps.
        pass

    async def _on_credit_drop(self, message: CreditDropMessage) -> None:
        """Handle an incoming credit drop message. Every credit must be returned after processing."""

        try:
            credit_return_message = await self._process_credit_drop(message)
        except Exception as e:
            self.exception(f"Error processing credit drop: {e}")
            credit_return_message = CreditReturnMessage(
                service_id=self.service_id,
                phase=message.phase,
            )
        finally:
            self.execute_async(
                self.credit_return_push_client.push(credit_return_message)
            )

    async def _process_credit_drop(
        self, message: CreditDropMessage
    ) -> CreditReturnMessage:
        """Process a credit drop message. Return the CreditReturnMessage.

        - Every credit must be returned after processing
        - All results or errors should be converted to a RequestRecord and pushed to the inference results client.

        NOTE: This function MUST NOT return until the credit drop is fully processed.
        This is to ensure that the max concurrency is respected via the semaphore of the pull client.
        The way this is enforced is by requiring that this method returns a CreditReturnMessage.
        """
        # TODO: Add tests to ensure that the above note is never violated in the future

        self.trace(lambda: f"Processing credit drop: {message}")
        drop_perf_ns = time.perf_counter_ns()  # The time the credit was received

        if message.phase not in self.task_stats:
            self.task_stats[message.phase] = WorkerPhaseTaskStats()
        self.task_stats[message.phase].total += 1

        record: RequestRecord = RequestRecord()
        try:
            record = await self._execute_single_credit(message, time.time_ns())

        except Exception as e:
            self.exception(f"Error processing credit drop: {e}")
            record.error = ErrorDetails.from_exception(e)
            record.end_perf_ns = time.perf_counter_ns()

        finally:
            record.credit_phase = message.phase
            msg = InferenceResultsMessage(
                service_id=self.service_id,
                record=record,
            )

            # Note that we already ensured that the phase exists in the task_stats dict in the above code.
            if not record.valid:
                self.task_stats[message.phase].failed += 1
            else:
                self.task_stats[message.phase].completed += 1

            try:
                await self.inference_results_push_client.push(msg)
            except Exception as e:
                # If we fail to push the record, log the error and continue
                self.exception(f"Error pushing request record: {e}")
            finally:
                # Calculate the latency of the credit drop (from when the credit was dropped to when the request was sent)
                pre_inference_ns = record.start_perf_ns - drop_perf_ns
                # Always return the credits
                return_message = CreditReturnMessage(
                    service_id=self.service_id,
                    delayed_ns=record.delayed_ns,
                    pre_inference_ns=pre_inference_ns,
                    phase=message.phase,
                )
                self.trace(lambda: f"Returning credit {return_message}")
                return return_message  # noqa: B012

    async def _execute_single_credit(
        self, message: CreditDropMessage, timestamp_ns: int
    ) -> RequestRecord:
        """Run a credit task for a single credit."""

        if not self.inference_client:
            raise NotInitializedError("Inference server client not initialized.")

        # retrieve the prompt from the dataset
        conversation_response: ConversationResponseMessage = (
            await self.conversation_request_client.request(
                ConversationRequestMessage(
                    service_id=self.service_id,
                    conversation_id=message.conversation_id,
                    credit_phase=message.phase,
                )
            )
        )
        self.trace(lambda: f"Received response message: {conversation_response}")

        if isinstance(conversation_response, ErrorMessage):
            return RequestRecord(
                model_name=self.model_endpoint.primary_model_name,
                conversation_id=message.conversation_id,
                turn_index=0,
                timestamp_ns=timestamp_ns,
                start_perf_ns=time.perf_counter_ns(),
                end_perf_ns=time.perf_counter_ns(),
                error=conversation_response.error,
            )

        record = await self._call_inference_api(
            message, conversation_response.conversation.turns[0], timestamp_ns
        )
        record.model_name = self.model_endpoint.primary_model_name
        record.conversation_id = conversation_response.conversation.session_id
        record.turn_index = 0
        return record

    async def _call_inference_api(
        self, message: CreditDropMessage, turn: Turn, timestamp_ns: int
    ) -> RequestRecord:
        """Make a single call to the inference API. Will return an error record if the call fails."""
        self.trace(lambda: f"Calling inference API for turn: {turn}")
        formatted_payload = None
        pre_send_perf_ns = None
        try:
            # Format payload for the API request
            formatted_payload = await self.request_converter.format_payload(
                model_endpoint=self.model_endpoint,
                turn=turn,
            )

            # NOTE: Current implementation of the TimingManager bypasses this, it is for future use.
            # Wait for the credit drop time if it is in the future.
            # Note that we check this after we have retrieved the data from the dataset, to ensure
            # that we are fully ready to go.
            delayed_ns = None
            drop_ns = message.credit_drop_ns
            now_ns = time.time_ns()
            if drop_ns and drop_ns > now_ns:
                self.trace(
                    lambda: f"Waiting for credit drop expected time: {(drop_ns - now_ns) / NANOS_PER_SECOND:.2f} s"
                )
                await asyncio.sleep((drop_ns - now_ns) / NANOS_PER_SECOND)
            elif drop_ns and drop_ns < now_ns:
                delayed_ns = now_ns - drop_ns

            # Save the current perf_ns before sending the request so it can be used to calculate
            # the start_perf_ns of the request in case of an exception.
            pre_send_perf_ns = time.perf_counter_ns()

            # Send the request to the Inference Server API and wait for the response
            result: RequestRecord = await self.inference_client.send_request(
                model_endpoint=self.model_endpoint,
                payload=formatted_payload,
            )

            self.debug(
                lambda: f"pre_send_perf_ns to start_perf_ns latency: {result.start_perf_ns - pre_send_perf_ns} ns"
            )

            result.delayed_ns = delayed_ns
            return result

        except Exception as e:
            self.exception(
                f"Error calling inference server API at {self.model_endpoint.url}: {e}"
            )
            return RequestRecord(
                request=formatted_payload,
                timestamp_ns=timestamp_ns,
                # Try and use the pre_send_perf_ns if it is available, otherwise use the current time.
                start_perf_ns=pre_send_perf_ns or time.perf_counter_ns(),
                end_perf_ns=time.perf_counter_ns(),
                error=ErrorDetails.from_exception(e),
            )

    @aiperf_task
    async def _health_check_task(self) -> None:
        """Task to report the health of the worker to the worker manager."""
        while True:
            try:
                health_message = self.create_health_message()
                await self.pub_client.publish(health_message)
            except Exception as e:
                self.exception(f"Error reporting health: {e}")
            except asyncio.CancelledError:
                self.debug("Health check task cancelled")
                break

            await asyncio.sleep(self.health_check_interval)

    def create_health_message(self) -> WorkerHealthMessage:
        return WorkerHealthMessage(
            service_id=self.service_id,
            process=self.get_process_health(),
            task_stats=self.task_stats,
        )

    @on_stop
    async def _shutdown_worker(self) -> None:
        self.debug("Shutting down worker")
        if self.inference_client:
            await self.inference_client.close()


def main() -> None:
    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(Worker)


if __name__ == "__main__":
    sys.exit(main())
