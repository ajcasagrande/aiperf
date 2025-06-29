#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import logging

from aiperf.common.hooks import AIPerfLifecycleMixin, on_start, on_stop
from aiperf.common.models.messages import WorkerHealthMessage
from aiperf.common.progress_tracker import ProgressTracker
from aiperf.ui.rich_dashboard import AIPerfRichDashboard

logger = logging.getLogger(__name__)


class AIPerfUI(AIPerfLifecycleMixin):
    """Mixin for Rich-based UI functionality with live dashboard updates."""

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
        self.dashboard = AIPerfRichDashboard(progress_tracker)
        self.progress_tracker = progress_tracker

    @on_start
    async def _on_start(self) -> None:
        """Start the UI."""
        await self.dashboard.run_async()

    @on_stop
    async def _on_stop(self) -> None:
        """Stop the UI."""
        await self.dashboard.shutdown()

    # async def on_profile_results_update(self) -> None:
    #     """Process the final results."""
    #     logger.info("Performance testing completed successfully!")
    #     if self.dashboard.running:
    #         self.dashboard.refresh_progress()

    async def on_profile_progress_update(self) -> None:
        """Update progress display."""
        if self.dashboard.running:
            self.dashboard.refresh_progress()

    async def on_profile_stats_update(self) -> None:
        """Update statistics display."""
        if self.dashboard.running:
            self.dashboard.refresh_progress()

    async def on_worker_health_update(self, message: WorkerHealthMessage) -> None:
        """Update worker health information."""
        self.dashboard.update_worker_health(message)
        if self.dashboard.running:
            self.dashboard.refresh_workers()
