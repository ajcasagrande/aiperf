#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import logging

from aiperf.common.messages import ProfileResultsMessage
from aiperf.ui.progress_dashboard import SplitScreenDashboardMixin


class AIPerfUI(SplitScreenDashboardMixin):
    """
    AIPerfUI is a class that provides a UI for the AIPerf system.
    """

    def __init__(self) -> None:
        super().__init__()

    async def process_final_results(self, message: ProfileResultsMessage) -> None:
        """Export the final results."""
        self.logger = logging.getLogger(__name__)
        self.logger.info("Final results: %s", message.records)
        self.live.stop()
        self.console_exporter.export(message.records)
