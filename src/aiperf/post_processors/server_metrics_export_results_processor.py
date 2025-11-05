# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from pathlib import Path

from aiperf.common.config import UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ResultsProcessorType
from aiperf.common.environment import Environment
from aiperf.common.factories import ResultsProcessorFactory
from aiperf.common.mixins import BufferedJSONLWriterMixin
from aiperf.common.models import MetricResult
from aiperf.common.models.server_metrics_models import ServerMetricRecord
from aiperf.common.protocols import ServerMetricsResultsProcessorProtocol
from aiperf.post_processors.base_metrics_processor import BaseMetricsProcessor


@implements_protocol(ServerMetricsResultsProcessorProtocol)
@ResultsProcessorFactory.register(ResultsProcessorType.SERVER_METRICS_EXPORT)
class ServerMetricsExportResultsProcessor(
    BaseMetricsProcessor, BufferedJSONLWriterMixin[ServerMetricRecord]
):
    """Exports per-record server metrics data to JSONL files.

    This processor streams each ServerMetricRecord as it arrives from the ServerMetricsManager,
    writing one JSON line per server per collection cycle. The output format supports
    multi-endpoint and multi-server time series analysis.

    Each line contains:
        - timestamp_ns: Collection timestamp in nanoseconds
        - server_url: Server metrics endpoint URL for filtering by endpoint
        - server_id: Unique server identifier
        - server_type: Type of server (e.g., "frontend", "worker")
        - hostname: Host machine name
        - instance: Server instance identifier
        - metrics_data: Complete metrics snapshot (requests, CPU, memory, Dynamo metrics, etc.)
    """

    def __init__(
        self,
        user_config: UserConfig,
        **kwargs,
    ):
        output_file: Path = user_config.output.profile_export_server_metrics_jsonl_file
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.unlink(missing_ok=True)

        super().__init__(
            output_file=output_file,
            batch_size=Environment.RECORD.EXPORT_BATCH_SIZE,
            user_config=user_config,
            **kwargs,
        )

        self.info(f"Server metrics export enabled: {self.output_file}")

    async def process_server_metric_record(self, record: ServerMetricRecord) -> None:
        """Process individual server metric record by writing it to JSONL.

        Args:
            record: ServerMetricRecord containing server metrics and hierarchical metadata
        """
        try:
            await self.buffered_write(record)
        except Exception as e:
            self.error(f"Failed to write server metrics record: {e}")

    async def summarize(self) -> list[MetricResult]:
        """Summarize the results. For this processor, we don't need to summarize anything."""
        return []
