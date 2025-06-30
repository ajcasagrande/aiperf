# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
import sys
import time
from collections import deque

from aiperf.common.comms.base import ClientAddressType, PullClient
from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.enums import CommandType, MessageType, ServiceType
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import (
    aiperf_task,
    on_cleanup,
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.models import (
    CommandMessage,
    ErrorDetails,
    ErrorDetailsCount,
    InferenceResultsMessage,
    ProcessRecordsCommandData,
    ProfileResultsMessage,
    ProfileStatsMessage,
)
from aiperf.common.models.messages import ParsedInferenceResultsMessage
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.common.service import BaseComponentService
from aiperf.common.tokenizer import Tokenizer
from aiperf.parsers import OpenAIResponseExtractor
from aiperf.services.records_manager.post_processors.metric_summary import MetricSummary


@ServiceFactory.register(ServiceType.RECORDS_MANAGER)
class RecordsManager(BaseComponentService):
    """
    The RecordsManager service is primarily responsible for holding the
    results returned from the workers.
    """

    def __init__(
        self, service_config: ServiceConfig, service_id: str | None = None
    ) -> None:
        super().__init__(service_config=service_config, service_id=service_id)
        self.logger.debug("Initializing records manager")

        self.records: deque[ParsedResponseRecord] = deque()
        self.error_records: deque[ParsedResponseRecord] = deque()
        self.error_records_count: int = 0
        self.records_count: int = 0
        # Track per-worker statistics
        self.worker_success_counts: dict[str, int] = {}
        self.worker_error_counts: dict[str, int] = {}

        self.start_time_ns: int = time.time_ns()
        self.end_time_ns: int | None = None

        self.extractor = OpenAIResponseExtractor()
        self.tokenizers: dict[str, Tokenizer] = {}
        self.user_config: UserConfig | None = None

        self.incoming_records: asyncio.Queue[InferenceResultsMessage] = asyncio.Queue()

        # self.inference_results_client: PullClient = self.comms.create_pull_client(
        #     ClientAddressType.PUSH_PULL_BACKEND,
        # )
        self.response_results_client: PullClient = self.comms.create_pull_client(
            ClientAddressType.INFERENCE_RESULTS_PUSH_PULL,
            bind=True,
        )
        # self.post_process_results_client: ReqClient = self.comms.create_req_client(
        #     ClientAddressType.DEALER_ROUTER_REQ_REP_FRONTEND,
        # )

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.RECORDS_MANAGER

    def get_tokenizer(self, model: str) -> Tokenizer:
        """Get the tokenizer for a given model."""
        if model not in self.tokenizers:
            self.tokenizers[model] = Tokenizer.from_pretrained(model)
        return self.tokenizers[model]

    @on_init
    async def _initialize(self) -> None:
        """Initialize records manager-specific components."""
        self.logger.debug("Initializing records manager")
        # TODO: Implement records manager initialization

        self.register_command_callback(
            CommandType.PROCESS_RECORDS,
            self.process_records,
        )

        # await self.inference_results_client.register_pull_callback(
        #     message_type=MessageType.INFERENCE_RESULTS,
        #     callback=self._on_inference_results,
        #     max_concurrency=1000000,
        # )

        await self.response_results_client.register_pull_callback(
            message_type=MessageType.PARSED_INFERENCE_RESULTS,
            callback=self._on_post_process_results,
            max_concurrency=1000000,
        )

    @on_start
    async def _start(self) -> None:
        """Start the records manager."""
        self.logger.debug("Starting records manager")
        self.start_time_ns = time.time_ns()
        # TODO: Implement records manager start

    @on_stop
    async def _stop(self) -> None:
        """Stop the records manager."""
        self.logger.debug("Stopping records manager")
        # TODO: Implement records manager stop

    @on_cleanup
    async def _cleanup(self) -> None:
        """Clean up records manager-specific components."""
        self.logger.debug("Cleaning up records manager")
        # TODO: Implement records manager cleanup

    @on_configure
    async def _configure(self, message: CommandMessage) -> None:
        """Configure the records manager."""
        self.logger.debug("Configuring records manager with message: %s", message)
        self.user_config = (
            message.data if isinstance(message.data, UserConfig) else None
        )
        # if self.user_config is None:
        #     raise self._service_error(
        #         ServiceErrorType.CONFIGURATION_ERROR,
        #         "User config is required for records manager",
        #     )

        self.get_tokenizer(
            os.getenv("AIPERF_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B")
        )

        if self.user_config:
            await asyncio.gather(
                *[
                    asyncio.to_thread(self.get_tokenizer, model)
                    for model in self.user_config.model_names
                ]
            )
            self.logger.info(
                "Initialized tokenizers for %d models", len(self.tokenizers)
            )

    @aiperf_task
    async def _report_records_task(self) -> None:
        """Report the records."""
        while not self.is_shutdown:
            await self.publish_profile_stats()
            await asyncio.sleep(1)

    @aiperf_task
    async def _process_records_task(self) -> None:
        """Process the records."""
        while not self.stop_event.is_set():
            try:
                # Blocking wait for the next message
                message = await self.incoming_records.get()
                # self._cpu_executor.submit(self._on_inference_results_internal, message)
                await self._on_inference_results_internal(message)

                # Drain the rest of the queue, non-blocking
                while not self.incoming_records.empty():
                    message = self.incoming_records.get_nowait()
                    # self._cpu_executor.submit(self._on_inference_results_internal, message)
                    await self._on_inference_results_internal(message)

            except asyncio.CancelledError:
                break

        await self.incoming_records.join()

    async def publish_profile_stats(self) -> None:
        """Publish the profile stats."""
        await self.pub_client.publish(
            ProfileStatsMessage(
                service_id=self.service_id,
                error_count=self.error_records_count,
                completed=self.records_count,
                worker_completed=self.worker_success_counts,
                worker_errors=self.worker_error_counts,
            ),
        )

    async def _on_post_process_results(
        self, message: ParsedInferenceResultsMessage
    ) -> None:
        """Handle a post process results message."""
        self.logger.debug("Received post process results: %s", message)

        worker_id = message.record.worker_id
        if worker_id not in self.worker_success_counts:
            self.worker_success_counts[worker_id] = 0
        if worker_id not in self.worker_error_counts:
            self.worker_error_counts[worker_id] = 0

        if message.record.request.has_error:
            self.logger.warning("Received error post process results: %s", message)
            # TODO: Re-enable this
            self.error_records.append(message.record)
            self.worker_error_counts[worker_id] += 1
            self.error_records_count += 1
        elif message.record.request.valid:
            # TODO: Re-enable this
            self.records.append(message.record)
            self.worker_success_counts[worker_id] += 1
            self.records_count += 1
        else:
            self.logger.warning("Received invalid post process results: %s", message)
            # TODO: Re-enable this
            # self.error_records.append(message.record)
            self.worker_error_counts[worker_id] += 1
            self.error_records_count += 1

    async def _on_inference_results(self, message: InferenceResultsMessage) -> None:
        """Handle an inference results message."""
        # _ = asyncio.create_task(self._on_inference_results_internal(message))
        self.incoming_records.put_nowait(message)
        # self.logger.info("Incoming records QQ size: %d", self.incoming_records._unfinished_tasks)

    async def get_error_summary(self) -> list[ErrorDetailsCount]:
        """Generate a summary of the error records."""
        summary: dict[ErrorDetails, int] = {}
        for record in self.error_records:
            if record.request.error is None:
                continue
            if record.request.error not in summary:
                summary[record.request.error] = 0
            summary[record.request.error] += 1

        return [
            ErrorDetailsCount(error_details=error_details, count=count)
            for error_details, count in summary.items()
        ]

    async def process_records(self, message: CommandMessage) -> None:
        """Process the records.

        This method is called when the records manager receives a command to process the records.
        """
        self.logger.debug("Processing records")
        self.was_cancelled = (
            message.data.cancelled
            if isinstance(message.data, ProcessRecordsCommandData)
            else False
        )
        self.end_time_ns = time.time_ns()
        # TODO: Implement records processing
        self.logger.info(
            "Processed %d successful records and %d error records",
            len(self.records),
            len(self.error_records),
        )

        profile_results = await self.post_process_records()
        self.logger.info("Profile results: %s", profile_results)

        if profile_results:
            await self.pub_client.publish(
                profile_results,
            )
        else:
            self.logger.error("No profile results to publish")
            await self.pub_client.publish(
                ProfileResultsMessage(
                    service_id=self.service_id,
                    total=0,
                    completed=0,
                    start_ns=self.start_time_ns,
                    end_ns=self.end_time_ns,
                    records=[],
                    errors_by_type=[],
                    was_cancelled=self.was_cancelled,
                ),
            )

    async def post_process_records(self) -> ProfileResultsMessage | None:
        """Post process the records."""
        self.logger.debug("Post processing records")

        if not self.records:
            self.logger.warning("No successful records to process")
            return ProfileResultsMessage(
                service_id=self.service_id,
                total=len(self.records),
                completed=len(self.records) + len(self.error_records),
                start_ns=self.start_time_ns or time.time_ns(),
                end_ns=self.end_time_ns or time.time_ns(),
                records=[],
                errors_by_type=await self.get_error_summary(),
                was_cancelled=self.was_cancelled,
            )

        self.logger.info("Token counts: %s", [r.token_count for r in self.records])
        metric_summary = MetricSummary()
        metric_summary.process(list(self.records))
        metrics_summary = metric_summary.get_metrics_summary()

        # Create and return ProfileResultsMessage
        return ProfileResultsMessage(
            service_id=self.service_id,
            total=len(self.records),
            completed=len(self.records) + len(self.error_records),
            start_ns=self.start_time_ns or time.time_ns(),
            end_ns=self.end_time_ns or time.time_ns(),
            records=metrics_summary,
            errors_by_type=await self.get_error_summary(),
            was_cancelled=self.was_cancelled,
        )


def main() -> None:
    """Main entry point for the records manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(RecordsManager)


if __name__ == "__main__":
    sys.exit(main())
