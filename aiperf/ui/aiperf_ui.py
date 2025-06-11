#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import logging

from aiperf.common.config.endpoint_config import EndPointConfig
from aiperf.common.data_exporter.console_exporter import ConsoleExporter
from aiperf.common.messages import ProfileResultsMessage
from aiperf.ui.base_ui import ConsoleUIMixin
from aiperf.ui.progress_dashboard import ProfileProgressDashboardMixin

logger = logging.getLogger(__name__)


class FinalResultsDashboardMixin(ConsoleUIMixin):
    """Mixin for updating the final results dashboard."""

    def __init__(self) -> None:
        super().__init__()

        # TODO: make this take in the endpoint config
        self.console_exporter: ConsoleExporter = ConsoleExporter(
            endpoint_config=EndPointConfig(
                type="console",
                streaming=True,
            ),
        )


class AIPerfUI(ProfileProgressDashboardMixin, FinalResultsDashboardMixin):
    """
    AIPerfUI is a class that provides a UI for the AIPerf system.
    """

    async def process_final_results(self, message: ProfileResultsMessage) -> None:
        """Export the final results."""
        logger.info("Final results: %s", message.records)
        self.live.stop()
        self.console_exporter.export(message.records)
