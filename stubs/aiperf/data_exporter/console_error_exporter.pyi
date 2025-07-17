#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.enums import DataExporterType as DataExporterType
from aiperf.common.factories import DataExporterFactory as DataExporterFactory
from aiperf.common.models import ErrorDetailsCount as ErrorDetailsCount
from aiperf.data_exporter.exporter_config import ExporterConfig as ExporterConfig

class ConsoleErrorExporter:
    def __init__(self, exporter_config: ExporterConfig) -> None: ...
    async def export(self, width: int | None = None) -> None: ...
