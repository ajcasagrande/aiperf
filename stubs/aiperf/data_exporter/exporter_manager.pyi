#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from aiperf.common.config import UserConfig as UserConfig
from aiperf.common.factories import DataExporterFactory as DataExporterFactory
from aiperf.common.messages import ProfileResultsMessage as ProfileResultsMessage
from aiperf.data_exporter.exporter_config import ExporterConfig as ExporterConfig

class ExporterManager:
    def __init__(
        self, results: ProfileResultsMessage, input_config: UserConfig
    ) -> None: ...
    async def export_all(self) -> None: ...
