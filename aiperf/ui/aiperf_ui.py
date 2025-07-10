# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
import logging

from aiperf.common.enums import MessageType
from aiperf.common.hooks import AIPerfLifecycleMixin, on_start, on_stop
from aiperf.common.messages import BaseServiceMessage
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.profile_progress_ui import ProfileProgressElement
from aiperf.ui.rich_dashboard import AIPerfRichDashboard
from aiperf.ui.worker_status_ui import WorkerStatusElement


class AIPerfUI(AIPerfLifecycleMixin):
    """Rich-based UI functionality with live dashboard updates.

    Abstracts the internal AIPerfRichDashboard and provides lifecycle hooks for the UI.
    """

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
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

    async def on_message(self, message: BaseServiceMessage) -> None:
        """Handle a message from the system controller."""
        _message_mappings = {
            MessageType.CREDIT_PHASE_PROGRESS: ProfileProgressElement.key,
            MessageType.CREDIT_PHASE_START: ProfileProgressElement.key,
            MessageType.CREDIT_PHASE_COMPLETE: ProfileProgressElement.key,
            MessageType.PROCESSING_STATS: ProfileProgressElement.key,
            MessageType.WORKER_HEALTH: WorkerStatusElement.key,
            MessageType.PROFILE_RESULTS: ProfileProgressElement.key,
        }

        if message.message_type in _message_mappings:
            self.logger.debug(
                "UI: Refreshing element (%s) for message (%s)",
                _message_mappings[message.message_type],
                message.message_type,
            )
            if message.message_type == MessageType.WORKER_HEALTH:
                self.dashboard.update_worker_health(message)
            self.try_refresh_element(_message_mappings[message.message_type])
        else:
            self.logger.debug(
                "UI: No element mapping found for message (%s)", message.message_type
            )

    def try_refresh_element(self, element_key: str) -> None:
        """Try to refresh the specified element. If the dashboard is not running or the current profile run is not set,
        do nothing."""
        try:
            if self.dashboard.running and self.progress_tracker.current_profile_run:
                self.dashboard.refresh_element(element_key)
            else:
                self.logger.debug(
                    "Dashboard not running (%s) or no current profile run (%s)",
                    self.dashboard.running,
                    self.progress_tracker.current_profile_run,
                )
        except Exception as e:
            self.logger.exception("Error refreshing element (%s): %s", element_key, e)
