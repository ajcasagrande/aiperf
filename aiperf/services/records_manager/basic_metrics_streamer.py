# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import time
from collections import deque

from aiperf.common.enums import MessageType, StreamingPostProcessorType
from aiperf.common.factories import StreamingPostProcessorFactory
from aiperf.common.hooks import on_message
from aiperf.common.messages import ProcessRecordsRequestMessage, ProfileResultsMessage
from aiperf.common.models import ErrorDetails, ErrorDetailsCount, ParsedResponseRecord
from aiperf.data_exporter.exporter_manager import ExporterManager
from aiperf.services.records_manager.post_processors.metric_summary import MetricSummary
from aiperf.services.records_manager.streaming_post_processor import (
    StreamingPostProcessor,
)


@StreamingPostProcessorFactory.register(StreamingPostProcessorType.BASIC_METRICS)
class BasicMetricsStreamer(StreamingPostProcessor):
    """Streamer for basic metrics."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        # TODO: we do not want to keep all the data forever
        self.records: deque[ParsedResponseRecord] = deque()
        self.error_records: deque[ParsedResponseRecord] = deque()
        self.start_time_ns: int = time.time_ns()
        self.end_time_ns: int | None = None
        self.was_cancelled: bool = False

    async def stream_record(self, record: ParsedResponseRecord) -> None:
        """Stream a record."""
        if record.request.valid:
            # TODO: we do not want to keep all the data forever
            self.records.append(record)
        else:
            self.warning(f"Received invalid inference results: {record}")
            # TODO: we do not want to keep all the data forever
            self.error_records.append(record)

    # TODO: This could be done on the fly as we process the records
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

    @on_message(MessageType.PROCESS_RECORDS_REQUEST)
    async def _on_process_records_request(
        self, message: ProcessRecordsRequestMessage
    ) -> None:
        """Process the records.

        This method is called when the records manager receives a command to process the records.
        """
        self.notice(lambda: f"Processing records: {message}")
        self.was_cancelled = message.cancelled
        self.end_time_ns = time.time_ns()
        # TODO: Implement records processing
        self.info(
            lambda: f"Processed {len(self.records)} successful records and {len(self.error_records)} error records"
        )

        profile_results = await self.post_process_records()
        self.info(lambda: f"Profile results: {profile_results}")

        if profile_results:
            await self.pub_client.publish(
                profile_results,
            )

            if self.user_config:
                await ExporterManager(
                    results=profile_results, input_config=self.user_config
                ).export_all()

        else:
            self.error("No profile results to publish")
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
        self.trace("Post processing records")

        if not self.records:
            self.warning("No successful records to process")
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

        self.trace(
            lambda: f"Token counts: {', '.join([str(r.output_token_count) for r in self.records])}"
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
