#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import asyncio
import logging

from aiperf.common.config.endpoint_config import EndPointConfig
from aiperf.common.data_exporter.console_exporter import ConsoleExporter
from aiperf.common.hooks import on_init, on_stop
from aiperf.common.messages import ProfileResultsMessage
from aiperf.ui.base_ui import ConsoleUIMixin
from aiperf.ui.progress_dashboard import ProfileProgressDashboardMixin
from aiperf.ui.splash_screen import show_splash_screen

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

    def __init__(self) -> None:
        super().__init__()
        self._splash_screen_task: asyncio.Task | None = None

    async def process_final_results(self, message: ProfileResultsMessage) -> None:
        """Export the final results."""
        logger.info("Final results: %s", message.records)
        self.live.stop()
        self.console_exporter.export(message.records)

    @on_stop
    async def _on_stop(self) -> None:
        """Stop the UI."""
        if self._splash_screen_task:
            self._splash_screen_task.cancel()

    @on_init
    async def _on_init(self) -> None:
        """Start the UI."""
        self._splash_screen_task = asyncio.create_task(show_splash_screen(self.console))
