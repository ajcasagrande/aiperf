# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

import aiofiles

from aiperf.clients.model_endpoint_info import ModelEndpointInfo
from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ExportLevel, RecordProcessorType
from aiperf.common.exceptions import PostProcessorDisabled
from aiperf.common.factories import RecordProcessorFactory, RequestConverterFactory
from aiperf.common.models import ParsedResponseRecord, RawRequestExport
from aiperf.common.protocols import (
    RecordProcessorProtocol,
    RequestConverterProtocol,
)
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.post_processors.base_metrics_processor import BaseMetricsProcessor


@implements_protocol(RecordProcessorProtocol)
@RecordProcessorFactory.register(RecordProcessorType.RAW_RECORD)
class RawRecordWriter(BaseMetricsProcessor):
    """Writes raw RequestRecord objects to JSONL for post-processing.

    This processor extracts the raw RequestRecord from ParsedResponseRecord
    and writes it to JSONL files, enabling delayed metrics processing and
    full record inspection after the benchmark completes.
    """

    def __init__(
        self,
        service_config: ServiceConfig,
        user_config: UserConfig,
        **kwargs,
    ):
        super().__init__(user_config=user_config, **kwargs)

        export_level = user_config.output.export_level
        if export_level != ExportLevel.RAW:
            raise PostProcessorDisabled(
                f"Raw record writer is disabled for export level {export_level}"
            )

        # Get service_id from kwargs if available, otherwise use a default
        self.service_id = kwargs.get("service_id", "unknown")
        self.output_file = self._get_output_file(self.service_id, user_config)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        self.record_count = 0
        self.batch_size = 10
        self._buffer: list[str] = []

        # Initialize request converter for payload formatting
        self.model_endpoint = ModelEndpointInfo.from_user_config(user_config)
        self.request_converter: RequestConverterProtocol = (
            RequestConverterFactory.create_instance(
                self.model_endpoint.endpoint.type,
            )
        )

        self.info(f"Raw record export enabled: {self.output_file}")
        self.output_file.unlink(missing_ok=True)

    def _get_output_file(self, service_id: str, user_config: UserConfig) -> Path:
        """Get the output file path for this record processor instance."""
        artifact_dir = user_config.output.artifact_directory
        base_name = user_config.output.profile_export_file.stem

        # Create per-processor file to avoid locking/coordination overhead
        return artifact_dir / "raw_records" / f"{base_name}_raw_{service_id}.jsonl"

    async def process_record(self, record: ParsedResponseRecord) -> MetricRecordDict:
        """Process a parsed record by writing its raw HTTP request/response data to JSONL.

        Args:
            record: The parsed response record containing the raw RequestRecord

        Returns:
            Empty MetricRecordDict (this processor doesn't compute metrics)
        """
        try:
            raw_record = record.request

            # Format the payload using the request converter
            payload = {}
            headers = {}
            if raw_record.turn:
                try:
                    payload = await self.request_converter.format_payload(
                        self.model_endpoint,
                        raw_record.turn,
                    )
                except Exception as e:
                    self.warning(f"Failed to format payload: {e}")

            # Extract headers from model endpoint
            if self.model_endpoint.endpoint.headers:
                headers = dict(self.model_endpoint.endpoint.headers)

            # Create the export model
            export_record = RawRequestExport(
                # Request identification
                conversation_id=raw_record.conversation_id,
                turn_index=raw_record.turn_index,
                x_request_id=raw_record.x_request_id,
                x_correlation_id=raw_record.x_correlation_id,
                # Request details
                model_name=raw_record.model_name,
                payload=payload,
                headers=headers,
                # Response details
                status=raw_record.status,
                responses=raw_record.responses,
                error=raw_record.error,
                # Timing information
                timestamp_ns=raw_record.timestamp_ns,
                start_perf_ns=raw_record.start_perf_ns,
                end_perf_ns=raw_record.end_perf_ns,
                recv_start_perf_ns=raw_record.recv_start_perf_ns,
                delayed_ns=raw_record.delayed_ns,
                credit_drop_latency=raw_record.credit_drop_latency,
                # Request lifecycle
                credit_phase=raw_record.credit_phase,
                was_cancelled=raw_record.was_cancelled,
                cancel_after_ns=raw_record.cancel_after_ns,
                cancellation_perf_ns=raw_record.cancellation_perf_ns,
            )

            # Serialize the export model
            record_json = export_record.model_dump_json()
            self._buffer.append(record_json)

            # Batch writes to reduce I/O overhead
            if len(self._buffer) >= self.batch_size:
                await self._flush_buffer()

            self.record_count += 1
            if self.record_count % 100 == 0:
                self.debug(f"Wrote {self.record_count} raw records")

        except Exception as e:
            self.error(f"Failed to write raw record: {e}")

        # Return empty dict since we don't compute metrics
        return MetricRecordDict()

    async def _flush_buffer(self) -> None:
        """Flush buffered records to disk."""
        if not self._buffer:
            return

        try:
            async with aiofiles.open(self.output_file, mode="a", encoding="utf-8") as f:
                for record_json in self._buffer:
                    await f.write(record_json)
                    await f.write("\n")
            self._buffer.clear()
        except Exception as e:
            self.error(f"Failed to flush buffer: {e}")

    async def close(self) -> None:
        """Flush any remaining buffered records and close the writer."""
        await self._flush_buffer()
        self.info(
            f"RawRecordWriter: {self.record_count} records written to {self.output_file}"
        )
