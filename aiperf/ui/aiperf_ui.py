# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging

from aiperf.common.credit_models import (
    CreditPhaseCompleteMessage,
    CreditPhaseProgressMessage,
    CreditPhaseStartMessage,
    RecordsProcessingStatsMessage,
)
from aiperf.common.hooks import AIPerfLifecycleMixin, on_start, on_stop
from aiperf.common.worker_models import WorkerHealthMessage
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.profile_progress_ui import ProfileProgressElement
from aiperf.ui.rich_dashboard import AIPerfRichDashboard

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

    async def on_credit_phase_progress_update(
        self, message: CreditPhaseProgressMessage
    ) -> None:
        """Update progress display."""
        try:
            if self.dashboard.running and self.progress_tracker.current_profile_run:
                self.dashboard.refresh_element(ProfileProgressElement.key)
        except Exception as e:
            logger.error("Error updating credit phase progress: %s", e)

    async def on_credit_phase_start_update(
        self, message: CreditPhaseStartMessage
    ) -> None:
        """Update progress display."""
        try:
            if self.dashboard.running and self.progress_tracker.current_profile_run:
                self.dashboard.refresh_element(ProfileProgressElement.key)
        except Exception as e:
            logger.error("Error updating credit phase start: %s", e)

    async def on_credit_phase_complete_update(
        self, message: CreditPhaseCompleteMessage
    ) -> None:
        """Update progress display."""
        try:
            if self.dashboard.running and self.progress_tracker.current_profile_run:
                self.dashboard.refresh_element(ProfileProgressElement.key)
        except Exception as e:
            logger.error("Error updating credit phase complete: %s", e)

    async def on_processing_stats_update(
        self, message: RecordsProcessingStatsMessage
    ) -> None:
        """Update progress display."""
        try:
            if self.dashboard.running and self.progress_tracker.current_profile_run:
                self.dashboard.refresh_element(ProfileProgressElement.key)
        except Exception as e:
            logger.error("Error updating processing stats: %s", e)

    async def on_worker_health_update(self, message: WorkerHealthMessage) -> None:
        """Update progress display."""
        try:
            if self.dashboard.running and self.progress_tracker.current_profile_run:
                self.dashboard.refresh_element(ProfileProgressElement.key)
        except Exception as e:
            logger.error("Error updating worker health: %s", e)
