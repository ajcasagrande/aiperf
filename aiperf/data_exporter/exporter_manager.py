# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import asyncio

from aiperf.common.config import EndPointConfig
from aiperf.common.factories import DataExporterFactory
from aiperf.common.models import ProfileResultsMessage


class ExporterManager:
    """
    ExporterManager is responsible for exporting records using all
    registered data exporters.
    """

    def __init__(self, endpoint_config: EndPointConfig):
        self.endpoint_config = endpoint_config
        self.exporter_classes = DataExporterFactory.get_all_classes()

    async def export_all(self, results: ProfileResultsMessage) -> None:
        tasks: list[asyncio.Task] = []
        for exporter_class in self.exporter_classes:
            exporter = exporter_class(self.endpoint_config)
            task = asyncio.create_task(exporter.export(results))
            tasks.append(task)

        await asyncio.gather(*tasks)
