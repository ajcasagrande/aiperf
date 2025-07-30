# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time

from aiperf.common.enums import (
    PostProcessorType,
    StreamingPostProcessorType,
)
from aiperf.common.enums.message_enums import MessageType
from aiperf.common.enums.timing_enums import CreditPhase
from aiperf.common.factories import PostProcessorFactory, StreamingPostProcessorFactory
from aiperf.common.hooks import background_task, on_message
from aiperf.common.messages.credit_messages import (
    CreditPhaseCompleteMessage,
    CreditPhaseStartMessage,
)
from aiperf.common.messages.progress_messages import MetricsPreviewMessage
from aiperf.common.models import (
    ErrorDetails,
    ErrorDetailsCount,
    ParsedResponseRecord,
)
from aiperf.common.models.record_models import ProfileResults
from aiperf.services.records_manager.post_processors.streaming_post_processor import (
    BaseStreamingPostProcessor,
)


@StreamingPostProcessorFactory.register(StreamingPostProcessorType.BASIC_METRICS)
class BasicMetricsStreamer(BaseStreamingPostProcessor):
    """Streamer for basic metrics."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.valid_count: int = 0
        self.error_count: int = 0
        self.start_time_ns: int = time.time_ns()
        self.error_summary: dict[ErrorDetails, int] = {}
        self.end_time_ns: int | None = None
        self.total_expected: int | None = None
        self.metric_summary = PostProcessorFactory.create_instance(
            PostProcessorType.METRIC_SUMMARY,
            endpoint_type=self.user_config.endpoint.type,
        )
        self.metrics_preview_interval = self.service_config.metrics_preview_interval

    async def stream_record(self, record: ParsedResponseRecord) -> None:
        """Stream a record."""
        if record.request.valid:
            self.valid_count += 1
            await self.metric_summary.process_record(record)
        else:
            self.error_count += 1
            self.warning(f"Received invalid inference results: {record.request.error}")
            if record.request.error is not None:
                self.error_summary.setdefault(record.request.error, 0)
                self.error_summary[record.request.error] += 1

    def get_error_summary(self) -> list[ErrorDetailsCount]:
        """Generate a summary of the error records."""
        return [
            ErrorDetailsCount(error_details=error_details, count=count)
            for error_details, count in self.error_summary.items()
        ]

    @on_message(MessageType.CREDIT_PHASE_START)
    async def _on_credit_phase_start(
        self, phase_start_msg: CreditPhaseStartMessage
    ) -> None:
        """Handle a credit phase start message."""
        if phase_start_msg.phase != CreditPhase.PROFILING:
            return
        self.start_time_ns = phase_start_msg.start_ns
        self.total_expected = phase_start_msg.total_expected_requests
        self.info(
            f"Credit phase start: {phase_start_msg.phase} with {self.total_expected} expected requests"
        )

    @on_message(MessageType.CREDIT_PHASE_COMPLETE)
    async def _on_credit_phase_complete(
        self, phase_complete_msg: CreditPhaseCompleteMessage
    ) -> None:
        """Handle a credit phase complete message."""
        if phase_complete_msg.phase != CreditPhase.PROFILING:
            return
        self.end_time_ns = phase_complete_msg.end_ns
        if self.total_expected is None:
            self.total_expected = phase_complete_msg.completed

    async def process_records(
        self, cancelled: bool
    ) -> ProfileResults | ErrorDetails | None:
        """Process the records.

        This method is called when the records manager receives a command to process the records.
        """
        if self.valid_count + self.error_count == 0:
            self.warning("No records to process")
            return None

        self.notice("Processing records")
        try:
            self.info(
                f"Processing {self.valid_count} successful records and {self.error_count} error records"
            )
            return await self._compute_profile_results(cancelled, preview=False)
        except Exception as e:
            self.exception(f"Error processing records: {e}")
            return ErrorDetails.from_exception(e)

    async def _compute_profile_results(
        self, cancelled: bool, preview: bool = False
    ) -> ProfileResults:
        """Compute the profile results."""
        return ProfileResults(
            total_expected=self.total_expected,
            completed=self.valid_count + self.error_count,
            start_ns=self.start_time_ns,
            end_ns=self.end_time_ns or time.time_ns(),
            records=await self.metric_summary.post_process(preview=preview),
            error_summary=self.get_error_summary(),
            was_cancelled=cancelled,
        )

    @background_task(
        immediate=False,
        interval=lambda self: self.metrics_preview_interval,
        disabled=lambda self: self.metrics_preview_interval is None,
    )
    async def _report_metrics_preview(self) -> None:
        results = await self._compute_profile_results(cancelled=False, preview=True)
        if not isinstance(results, ProfileResults):
            self.warning(
                lambda: f"Metrics preview returned {type(results)} instead of ProfileResults: {results}"
            )
            return

        self.debug(lambda: f"Metrics preview: {results}")
        await self.publish(
            MetricsPreviewMessage(
                service_id=self.service_id,
                metrics_preview=results,
            )
        )
