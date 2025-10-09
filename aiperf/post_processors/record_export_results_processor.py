# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import aiofiles

from aiperf.common.config import ServiceConfig, UserConfig
from aiperf.common.config.config_defaults import OutputDefaults
from aiperf.common.constants import AIPERF_DEV_MODE
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import ExportLevel, ResultsProcessorType
from aiperf.common.factories import ResultsProcessorFactory
from aiperf.common.hooks import on_init, on_stop
from aiperf.common.protocols import ResultsProcessorProtocol
from aiperf.metrics.metric_dicts import MetricRecordDict
from aiperf.metrics.metric_registry import MetricRegistry
from aiperf.post_processors.base_metrics_processor import BaseMetricsProcessor


@implements_protocol(ResultsProcessorProtocol)
@ResultsProcessorFactory.register(ResultsProcessorType.RECORD_EXPORT)
class RecordExportResultsProcessor(BaseMetricsProcessor):
    """Exports per-record metrics to JSONL with display unit conversion and filtering."""

    def __init__(
        self,
        service_id: str,
        service_config: ServiceConfig,
        user_config: UserConfig,
        **kwargs,
    ):
        super().__init__(user_config=user_config, **kwargs)
        self.enabled = user_config.output.export_level == ExportLevel.RECORDS

        if not self.enabled:
            return

        output_dir = (
            user_config.output.artifact_directory / OutputDefaults.RECORD_METRICS_FOLDER
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        self.output_file = output_dir / "record_metrics.jsonl"
        self.record_count = 0
        self.show_internal = (
            AIPERF_DEV_MODE and service_config.developer.show_internal_metrics
        )

    @on_init
    async def _initialize(self) -> None:
        if self.enabled:
            self.info(f"Record metrics export enabled: {self.output_file}")

    async def process_result(self, incoming_metrics: MetricRecordDict) -> None:
        if not self.enabled:
            return

        try:
            display_metrics = incoming_metrics.to_display_dict(
                MetricRegistry, self.show_internal
            )

            if display_metrics:
                import json

                async with aiofiles.open(
                    self.output_file, mode="a", encoding="utf-8"
                ) as f:
                    await f.write(json.dumps(display_metrics) + "\n")

                self.record_count += 1
                if self.record_count % 100 == 0:
                    self.debug(f"Wrote {self.record_count} record metrics")

        except Exception as e:
            self.error(f"Failed to write record metrics: {e}")

    async def summarize(self) -> dict:
        return {}

    @on_stop
    async def _shutdown(self) -> None:
        if self.enabled:
            self.info(
                f"RecordExportResultsProcessor: {self.record_count} records written"
            )
