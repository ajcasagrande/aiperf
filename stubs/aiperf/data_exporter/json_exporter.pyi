#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from _typeshed import Incomplete

from aiperf.common.config import UserConfig as UserConfig
from aiperf.common.constants import NANOS_PER_SECOND as NANOS_PER_SECOND
from aiperf.common.enums import DataExporterType as DataExporterType
from aiperf.common.factories import DataExporterFactory as DataExporterFactory
from aiperf.common.pydantic_utils import AIPerfBaseModel as AIPerfBaseModel
from aiperf.common.record_models import ErrorDetailsCount as ErrorDetailsCount
from aiperf.common.record_models import MetricResult as MetricResult
from aiperf.data_exporter.exporter_config import ExporterConfig as ExporterConfig

class JsonExportData(AIPerfBaseModel):
    input_config: UserConfig | None
    records: dict[str, MetricResult] | None
    was_cancelled: bool | None
    errors_by_type: list[ErrorDetailsCount] | None
    start_time: datetime | None
    end_time: datetime | None

class JsonExporter:
    logger: Incomplete
    def __init__(self, exporter_config: ExporterConfig) -> None: ...
    async def export(self) -> None: ...
