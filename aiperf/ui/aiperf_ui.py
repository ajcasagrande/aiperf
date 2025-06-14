#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import logging

from aiperf.common.config.endpoint_config import EndPointConfig
from aiperf.common.messages import ProfileResultsMessage
from aiperf.data_exporter.console_error_exporter import ConsoleErrorExporter
from aiperf.data_exporter.console_exporter import ConsoleExporter
from aiperf.ui.progress_dashboard import SplitScreenDashboardMixin


class ConsoleExporterMixin:
    """Mixin for exporting console output."""

    async def export_console_output(self, message: ProfileResultsMessage) -> None:
        """Export the console output."""

        # TODO: Make this configurable, and it should be part of the generic exporting of results
        console_exporter: ConsoleExporter = ConsoleExporter(
            endpoint_config=EndPointConfig(
                type="console",
                streaming=True,
            ),
        )
        console_exporter.export(message)

        console_error_exporter: ConsoleErrorExporter = ConsoleErrorExporter()
        console_error_exporter.export(message)


class AIPerfUI(ConsoleExporterMixin, SplitScreenDashboardMixin):
    """
    AIPerfUI is a class that provides a UI for the AIPerf system.
    """

    def __init__(self) -> None:
        super().__init__()

    async def process_final_results(self, message: ProfileResultsMessage) -> None:
        """Export the final results."""
        self.logger = logging.getLogger(__name__)
        self.logger.info("Final results: %s", message)
        self.live.stop()

        await self.export_console_output(message)
