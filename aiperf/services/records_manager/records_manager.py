# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import asyncio
import sys
import time
from collections import deque

from aiperf.common.comms.base import (
    CommunicationClientAddressType,
    PullClientProtocol,
)
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.credit_models import PhaseProcessingStats
from aiperf.common.enums import CommandType, CreditPhase, MessageType, ServiceType
from aiperf.common.factories import ServiceFactory
from aiperf.common.hooks import (
    aiperf_task,
    on_cleanup,
    on_configure,
    on_init,
    on_start,
    on_stop,
)
from aiperf.common.messages import (
    CommandMessage,
    InferenceResultsMessage,
    ParsedInferenceResultsMessage,
    ProcessRecordsCommandData,
    ProfileResultsMessage,
    RecordsProcessingStatsMessage,
)
from aiperf.common.record_models import (
    ErrorDetails,
    ErrorDetailsCount,
    ParsedResponseRecord,
)
from aiperf.common.service import BaseComponentService
from aiperf.services.records_manager.post_processors.metric_summary import MetricSummary


@ServiceFactory.register(ServiceType.RECORDS_MANAGER)
class RecordsManager(BaseComponentService):
    """
    The RecordsManager service is primarily responsible for holding the
    results returned from the workers.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        service_id: str | None = None,
    ) -> None:
        super().__init__(
            service_config=service_config,
            user_config=user_config,
            service_id=service_id,
        )
        self.logger.debug("Initializing records manager")
        self.user_config: UserConfig | None = None
        self.configured_event = asyncio.Event()

        # TODO: we do not want to keep all the data forever
        self.records: deque[ParsedResponseRecord] = deque()
        self.error_records: deque[ParsedResponseRecord] = deque()

        self.error_records_count: int = 0
        self.records_count: int = 0
        # Track per-worker statistics
        self.worker_success_counts: dict[str, int] = {}
        self.worker_error_counts: dict[str, int] = {}

        self.start_time_ns: int = time.time_ns()
        self.end_time_ns: int | None = None

        self.records: deque[ParsedResponseRecord] = deque()
        self.error_records: deque[ParsedResponseRecord] = deque()
        self.error_records_count: int = 0
        self.records_count: int = 0
        # Track per-worker statistics
        self.worker_success_counts: dict[str, int] = {}
        self.worker_error_counts: dict[str, int] = {}

        self.start_time_ns: int = time.time_ns()
        self.end_time_ns: int | None = None

        self.user_config: UserConfig | None = None

        self.incoming_records: asyncio.Queue[InferenceResultsMessage] = asyncio.Queue()

        self.response_results_client: PullClientProtocol = (
            self.comms.create_pull_client(
                CommunicationClientAddressType.RECORDS,
                bind=True,
            )
        )

        self.active_credit_phase: CreditPhase | None = None

    @property
    def service_type(self) -> ServiceType:
        """The type of service."""
        return ServiceType.RECORDS_MANAGER

    @on_init
    async def _initialize(self) -> None:
        """Initialize records manager-specific components."""
        self.logger.debug("Initializing records manager")
        self.register_command_callback(
            CommandType.PROCESS_RECORDS,
            self.process_records,
        )

        self.register_command_callback(
            CommandType.PROCESS_RECORDS,
            self.process_records,
        )

        await self.response_results_client.register_pull_callback(
            message_type=MessageType.PARSED_INFERENCE_RESULTS,
            callback=self._on_parsed_inference_results,
            max_concurrency=100_000,
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

    @aiperf_task
    async def _report_records_task(self) -> None:
        """Report the records."""
        while not self.stop_event.is_set():
            if self.active_credit_phase is not None:
                await self.publish_processing_stats()
            await asyncio.sleep(1)

    async def publish_processing_stats(self) -> None:
        """Publish the profile stats."""
        await self.pub_client.publish(
            RecordsProcessingStatsMessage(
                service_id=self.service_id,
                current_phase=self.active_credit_phase,
                processing_stats=PhaseProcessingStats(
                    processed=self.records_count,
                    errors=self.error_records_count,
                ),
                worker_stats={
                    worker_id: PhaseProcessingStats(
                        processed=self.worker_success_counts[worker_id],
                        errors=self.worker_error_counts[worker_id],
                    )
                    for worker_id in self.worker_success_counts
                },
                request_ns=time.time_ns(),
            ),
        )

    async def _on_parsed_inference_results(
        self, message: ParsedInferenceResultsMessage
    ) -> None:
        """Handle a parsed inference results message."""

        self.active_credit_phase = message.record.request.credit_phase
        if self.active_credit_phase != CreditPhase.STEADY_STATE:
            return

        self.logger.debug("Received parsed inference results: %s", message)

        worker_id = message.record.worker_id
        if worker_id not in self.worker_success_counts:
            self.worker_success_counts[worker_id] = 0
        if worker_id not in self.worker_error_counts:
            self.worker_error_counts[worker_id] = 0

        if message.record.request.has_error:
            self.logger.warning("Received error inference results: %s", message)
            # TODO: we do not want to keep all the data forever
            self.error_records.append(message.record)
            self.worker_error_counts[worker_id] += 1
            self.error_records_count += 1
        elif message.record.request.valid:
            # TODO: we do not want to keep all the data forever
            self.records.append(message.record)
            self.worker_success_counts[worker_id] += 1
            self.records_count += 1
        else:
            self.logger.warning("Received invalid inference results: %s", message)
            # TODO: we do not want to keep all the data forever
            self.error_records.append(message.record)
            self.worker_error_counts[worker_id] += 1
            self.error_records_count += 1

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
