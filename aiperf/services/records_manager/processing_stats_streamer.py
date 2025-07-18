# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time

from aiperf.common.enums import CreditPhase, StreamingPostProcessorType
from aiperf.common.enums.message_enums import MessageType
from aiperf.common.factories import StreamingPostProcessorFactory
from aiperf.common.hooks import aiperf_auto_task, on_message
from aiperf.common.messages import (
    ProcessRecordsRequestMessage,
    RecordsProcessingStatsMessage,
)
from aiperf.common.messages.credit_messages import (
    CreditPhaseCompleteMessage,
    CreditPhaseStartMessage,
)
from aiperf.common.models import PhaseProcessingStats
from aiperf.common.models.record_models import ParsedResponseRecord
from aiperf.services.records_manager.streaming_post_processor import (
    StreamingPostProcessor,
)


@StreamingPostProcessorFactory.register(StreamingPostProcessorType.PROCESSING_STATS)
class ProcessingStatsStreamer(StreamingPostProcessor):
    """This streamer is used to track the number of records processed and the number of errors.
    It is also used to track the number of requests expected and the number of requests completed.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.error_records_count: int = 0
        self.records_count: int = 0
        self.total_expected_requests: int | None = None
        self.final_request_count: int | None = None

        # Track per-worker statistics
        self.worker_success_counts: dict[str, int] = {}
        self.worker_error_counts: dict[str, int] = {}

    async def stream_record(self, record: ParsedResponseRecord) -> None:
        """Stream a record."""
        self.trace(lambda: f"Received parsed inference results: {record}")
        if record.request.credit_phase != CreditPhase.PROFILING:
            self.debug(
                lambda: f"Skipping non-profiling record: {record.request.credit_phase}"
            )
            return

        worker_id = record.worker_id
        if worker_id not in self.worker_success_counts:
            self.worker_success_counts[worker_id] = 0
        if worker_id not in self.worker_error_counts:
            self.worker_error_counts[worker_id] = 0

        if record.request.valid:
            self.worker_success_counts[worker_id] += 1
            self.records_count += 1
        else:
            self.warning(lambda: f"Received invalid inference results: {record}")
            self.worker_error_counts[worker_id] += 1
            self.error_records_count += 1

        if (
            self.final_request_count is not None
            and self.records_count >= self.final_request_count
        ):
            self.info(
                lambda: f"Processed {self.records_count} requests and {self.error_records_count} errors."
            )
            await self.publish_processing_stats()
            # TODO: Publish PROFILE_RESULTS_COMPLETE message
            await self.publish(
                ProcessRecordsRequestMessage(
                    service_id=self.service_id,
                    cancelled=False,
                )
            )

    @on_message(MessageType.CREDIT_PHASE_START)
    async def _on_credit_phase_start(self, message: CreditPhaseStartMessage) -> None:
        """Handle a credit phase start message."""
        if message.phase == CreditPhase.PROFILING:
            self.total_expected_requests = message.total_expected_requests

    @on_message(MessageType.CREDIT_PHASE_COMPLETE)
    async def _on_credit_phase_complete(
        self, message: CreditPhaseCompleteMessage
    ) -> None:
        """Handle a credit phase complete message."""
        if message.phase == CreditPhase.PROFILING:
            self.final_request_count = message.completed
            self.info(f"Updating final request count to {self.final_request_count}")

    @aiperf_auto_task(
        interval_sec=lambda self: self.service_config.progress_report_interval_seconds
    )
    async def _report_records_task(self) -> None:
        """Report the records."""
        if self.records_count > 0 or self.error_records_count > 0:
            # Only publish stats if there are records to report
            await self.publish_processing_stats()

    async def publish_processing_stats(self) -> None:
        """Publish the profile stats."""
        await self.pub_client.publish(
            RecordsProcessingStatsMessage(
                service_id=self.service_id,
                processing_stats=PhaseProcessingStats(
                    processed=self.records_count,
                    errors=self.error_records_count,
                    total_expected_requests=self.total_expected_requests,
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
