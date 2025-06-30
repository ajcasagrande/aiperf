# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import os
import sys
import time
from collections import deque

import pandas as pd

from aiperf.common.comms.base import ClientAddressType, PullClient
from aiperf.common.config import ServiceConfig
from aiperf.common.config.user_config import UserConfig
from aiperf.common.constants import NANOS_PER_MILLIS
from aiperf.common.enums import CommandType, MessageType, ServiceType
from aiperf.common.exceptions import ServiceErrorType
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
    ResultsRecord,
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
            message_type=MessageType.POST_PROCESS_RESULTS,
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
        if self.user_config is None:
            raise self._service_error(
                ServiceErrorType.CONFIGURATION_ERROR,
                "User config is required for records manager",
            )

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

    # async def _on_inference_results_internal(
    #     self, message: InferenceResultsMessage
    # ) -> None:
    #     """Handle an inference results message."""
    #     record = message.record
    #     worker_id = message.service_id

    #     # Initialize worker counters if not seen before
    #     if worker_id not in self.worker_request_counts:
    #         self.worker_request_counts[worker_id] = 0
    #     if worker_id not in self.worker_error_counts:
    #         self.worker_error_counts[worker_id] = 0

    #     if record.has_error:
    #         self.logger.warning("Received error inference results: %s", record)
    #         self.error_records.append(record)
    #         self.worker_error_counts[worker_id] += 1

    #     elif record.valid:
    #         self.logger.debug(
    #             "Received inference results: %f milliseconds. %f milliseconds.",
    #             record.time_to_first_response_ns / NANOS_PER_MILLIS
    #             if record.time_to_first_response_ns
    #             else None,
    #             record.time_to_last_response_ns / NANOS_PER_MILLIS
    #             if record.time_to_last_response_ns
    #             else None,
    #         )
    #         self.worker_request_counts[worker_id] += 1

    #         # await self.post_process_results_client.request_async(
    #         #     message, self._on_post_process_results
    #         # )

    #         tokenizer = self.get_tokenizer(record.request["model"])
    #         resp = await self.extractor.extract_response_data(record, tokenizer)
    #         total_tokens = sum(r.token_count for r in resp if r.token_count is not None)
    #         self.records.append(ResponseRecord(
    #             request=record,
    #             responses=resp,
    #             token_count=total_tokens if total_tokens > 0 else None,
    #         ))

    #         # self.logger.debug(
    #         #     "Received %d responses, %d total tokens",
    #         #     len(resp),
    #         #     total_tokens,
    #         # )

    #     else:
    #         self.logger.warning("Received invalid inference results: %s", record)
    #         self.error_records.append(record)
    #         self.worker_error_counts[worker_id] += 1

    #     self.incoming_records.task_done()

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
            if not record.has_error:
                continue
            if record.error.type not in summary:
                summary[record.error.type] = 0
            summary[record.error] += 1

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


def record_from_dataframe(
    df: pd.DataFrame,
    column_name: str,
    name: str,
    unit: str,
    streaming_only: bool,
) -> ResultsRecord:
    """Create a Record from a DataFrame."""
    column = df[column_name]
    return ResultsRecord(
        name=name,
        unit=unit,
        avg=column.mean() / NANOS_PER_MILLIS,
        min=column.min() / NANOS_PER_MILLIS,
        max=column.max() / NANOS_PER_MILLIS,
        p1=column.quantile(0.01) / NANOS_PER_MILLIS,
        p5=column.quantile(0.05) / NANOS_PER_MILLIS,
        p25=column.quantile(0.25) / NANOS_PER_MILLIS,
        p50=column.quantile(0.50) / NANOS_PER_MILLIS,
        p75=column.quantile(0.75) / NANOS_PER_MILLIS,
        p90=column.quantile(0.90) / NANOS_PER_MILLIS,
        p95=column.quantile(0.95) / NANOS_PER_MILLIS,
        p99=column.quantile(0.99) / NANOS_PER_MILLIS,
        std=column.std() / NANOS_PER_MILLIS,
        count=int(column.count()),
        streaming_only=streaming_only,
    )


def main() -> None:
    """Main entry point for the records manager."""

    from aiperf.common.bootstrap import bootstrap_and_run_service

    bootstrap_and_run_service(RecordsManager)


if __name__ == "__main__":
    sys.exit(main())
