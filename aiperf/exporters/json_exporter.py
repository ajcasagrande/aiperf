# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from datetime import datetime

import aiofiles
from pydantic import BaseModel

from aiperf.common.config import UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import DataExporterType
from aiperf.common.factories import DataExporterFactory
from aiperf.common.models import ErrorDetailsCount, MetricResult
from aiperf.common.protocols import DataExporterProtocol
from aiperf.common.types import MetricTagT
from aiperf.exporters.base_file_exporter import BaseFileExporter
from aiperf.exporters.exporter_config import ExporterConfig, FileExportInfo


class JsonExportData(BaseModel):
    """Data to be exported to a JSON file."""

    records: dict[MetricTagT, MetricResult] | None = None
    input_config: UserConfig | None = None
    was_cancelled: bool | None = None
    error_summary: list[ErrorDetailsCount] | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None


@DataExporterFactory.register(DataExporterType.JSON)
@implements_protocol(DataExporterProtocol)
class JsonExporter(BaseFileExporter):
    """
    A class to export records to a JSON file.
    """

    def __init__(self, exporter_config: ExporterConfig, **kwargs) -> None:
        super().__init__(exporter_config=exporter_config, **kwargs)
        self.debug(lambda: f"Initializing JsonExporter with config: {exporter_config}")
        self._file_path = self._output_directory / "profile_export_aiperf.json"

    def get_export_info(self) -> FileExportInfo:
        return FileExportInfo(
            export_type="JSON Export",
            file_path=self._file_path,
        )

    async def _export_converted_records(
        self,
        converted_records: dict[MetricTagT, MetricResult],
        start_time: datetime | None,
        end_time: datetime | None,
    ) -> None:
        """Export the converted records to the JSON file."""
        export_data = JsonExportData(
            input_config=self._input_config,
            records=converted_records,
            was_cancelled=self._results.was_cancelled,
            error_summary=self._results.error_summary,
            start_time=start_time,
            end_time=end_time,
        )

        self.debug(lambda: f"Exporting data to JSON file: {export_data}")
        export_data_json = export_data.model_dump_json(indent=2, exclude_unset=True)
        async with aiofiles.open(self._file_path, "w") as f:
            await f.write(export_data_json)
