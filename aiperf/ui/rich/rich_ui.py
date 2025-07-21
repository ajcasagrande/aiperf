# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
from typing import cast

from aiperf.common.enums import (
    AIPerfUIType,
    MessageType,
)
from aiperf.common.hooks import on_start, on_stop
from aiperf.common.messages import Message, WorkerHealthMessage
from aiperf.common.mixins import AIPerfLifecycleMixin
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.rich.profile_progress_ui import ProfileProgressElement
from aiperf.ui.rich.rich_dashboard import AIPerfRichDashboard
from aiperf.ui.rich.worker_status_ui import WorkerStatusElement
from aiperf.ui.ui_protocol import AIPerfUIFactory


@AIPerfUIFactory.register(AIPerfUIType.RICH)
class RichUI(AIPerfLifecycleMixin):
    """Rich-based UI functionality with live dashboard updates.

    Abstracts the internal AIPerfRichDashboard and provides lifecycle hooks for the UI.
    """

    def __init__(self, progress_tracker: ProgressTracker, **kwargs) -> None:
        super().__init__(**kwargs)
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

    async def on_message(self, message: Message) -> None:
        """Handle a message from the system controller."""
        _message_mappings = {
            MessageType.CreditPhaseProgress: ProfileProgressElement.key,
            MessageType.CreditPhaseStart: ProfileProgressElement.key,
            MessageType.CreditPhaseComplete: ProfileProgressElement.key,
            MessageType.ProcessingStats: ProfileProgressElement.key,
            MessageType.WorkerHealth: WorkerStatusElement.key,
            MessageType.ProfileResults: ProfileProgressElement.key,
        }

        if message.message_type in _message_mappings:
            self.debug(
                lambda: f"UI: Refreshing element ({_message_mappings[message.message_type]}) for message ({message.message_type})"
            )
            if message.message_type == MessageType.WorkerHealth:
                self.dashboard.update_worker_health(cast(WorkerHealthMessage, message))
            self.try_refresh_element(_message_mappings[message.message_type])
        else:
            self.debug(
                lambda: f"UI: No element mapping found for message ({message.message_type})"
            )

    def try_refresh_element(self, element_key: str) -> None:
        """Try to refresh the specified element. If the dashboard is not running or the current profile run is not set,
        do nothing."""
        try:
            if self.dashboard.running and self.progress_tracker.current_profile_run:
                self.dashboard.refresh_element(element_key)
            else:
                self.debug(
                    lambda: f"Dashboard not running ({self.dashboard.running}) or no current profile run ({self.progress_tracker.current_profile_run})"
                )
        except Exception as e:
            self.logger.exception("Error refreshing element (%s): %s", element_key, e)
