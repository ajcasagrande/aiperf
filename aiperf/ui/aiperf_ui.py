# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging

from aiperf.common.health_models import WorkerHealthMessage
from aiperf.common.hooks import AIPerfLifecycleMixin, on_start, on_stop
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.profile_progress_ui import ProfileProgressElement
from aiperf.ui.rich_dashboard import AIPerfRichDashboard
from aiperf.ui.worker_status_ui import WorkerStatusElement

logger = logging.getLogger(__name__)


class AIPerfUI(AIPerfLifecycleMixin):
    """Rich-based UI functionality with live dashboard updates.

    Abstracts the internal AIPerfRichDashboard and provides lifecycle hooks for the UI.
    """

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

    async def on_profile_progress_update(self) -> None:
        """Update progress display."""
        try:
            if self.dashboard.running and self.progress_tracker.current_profile:
                self.dashboard.refresh_element(ProfileProgressElement.key)
        except Exception as e:
            logger.error("Error updating profile progress: %s", e)

    async def on_processing_stats_update(self) -> None:
        """Update statistics display."""
        try:
            if self.dashboard.running and self.progress_tracker.current_profile:
                self.dashboard.refresh_element(ProfileProgressElement.key)
        except Exception as e:
            logger.error("Error updating processing stats: %s", e)

    async def on_worker_health_update(self, message: WorkerHealthMessage) -> None:
        """Update worker health information."""
        try:
            self.dashboard.update_worker_health(message)
            if self.dashboard.running:
                self.dashboard.refresh_element(WorkerStatusElement.key)
        except Exception as e:
            logger.error("Error updating worker health: %s", e)

    async def on_profile_results_update(self) -> None:
        """Process the final results."""
        # TODO: Removed the update call because it was clearing the dashboard.
        #       I think this is because the progress tracker changes the current profile.
        #       We should find a better way to handle this.
        logger.info("Performance testing completed successfully!")
