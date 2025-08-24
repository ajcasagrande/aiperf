# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from abc import ABC, abstractmethod
from datetime import datetime

from aiperf.common.constants import AIPERF_DEV_MODE, NANOS_PER_SECOND
from aiperf.common.enums import MetricFlags
from aiperf.common.mixins import AIPerfLoggerMixin
from aiperf.common.models import MetricResult
from aiperf.common.types import MetricTagT
from aiperf.exporters.display_units_utils import convert_all_metrics_to_display_units
from aiperf.exporters.exporter_config import ExporterConfig, FileExportInfo
from aiperf.metrics.metric_registry import MetricRegistry


class BaseFileExporter(AIPerfLoggerMixin, ABC):
    """
    A class to export records to a file.
    """

    def __init__(self, exporter_config: ExporterConfig, **kwargs) -> None:
        super().__init__(exporter_config=exporter_config, **kwargs)
        self._results = exporter_config.results
        self._output_directory = exporter_config.user_config.output.artifact_directory
        self._input_config = exporter_config.user_config
        self._metric_registry = MetricRegistry
        self._show_internal_metrics = AIPERF_DEV_MODE and (
            exporter_config.service_config.developer.show_internal_metrics
        )

    @abstractmethod
    def get_export_info(self) -> FileExportInfo:
        """Get the export info for the file."""
        pass

    def _should_export(self, metric: MetricResult) -> bool:
        """Check if a metric should be exported."""
        metric_class = MetricRegistry.get_class(metric.tag)
        res = (
            metric_class.missing_flags(MetricFlags.EXPERIMENTAL | MetricFlags.INTERNAL)
            or self._show_internal_metrics
        )
        self.debug(lambda: f"Metric '{metric.tag}' should be exported: {res}")
        return res

    async def export(self) -> None:
        self._output_directory.mkdir(parents=True, exist_ok=True)

        start_time = (
            datetime.fromtimestamp(self._results.start_ns / NANOS_PER_SECOND)
            if self._results.start_ns
            else None
        )
        end_time = (
            datetime.fromtimestamp(self._results.end_ns / NANOS_PER_SECOND)
            if self._results.end_ns
            else None
        )

        converted_records: dict[MetricTagT, MetricResult] = {}
        if self._results.records:
            converted_records = convert_all_metrics_to_display_units(
                self._results.records, self._metric_registry
            )
            converted_records = {
                k: v for k, v in converted_records.items() if self._should_export(v)
            }

        await self._export_converted_records(converted_records, start_time, end_time)

    @abstractmethod
    async def _export_converted_records(
        self,
        converted_records: dict[MetricTagT, MetricResult],
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> None:
        """Export the converted records to the file."""
        pass
