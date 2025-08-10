# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import multiprocessing

from aiperf.common.config import UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import AIPerfUIType, CreditPhase
from aiperf.common.factories import AIPerfUIFactory
from aiperf.common.hooks import (
    background_task,
    on_records_progress,
    on_requests_phase_progress,
    on_start,
    on_stop,
    on_worker_update,
)
from aiperf.common.models import (
    RecordsStats,
    RequestsStats,
    WorkerStats,
)
from aiperf.common.protocols import AIPerfUIProtocol
from aiperf.common.utils import yield_to_event_loop
from aiperf.ui.base_ui import BaseAIPerfUI
from aiperf.ui.textual.textual_app import AIPerfTextualApp


@implements_protocol(AIPerfUIProtocol)
@AIPerfUIFactory.register(AIPerfUIType.TEXTUAL)
class AIPerfTextualUI(BaseAIPerfUI):
    """Enhanced mixin for Textual-based UI functionality with improved visual feedback."""

    LOG_REFRESH_INTERVAL = 0.1

    def __init__(
        self,
        log_queue: multiprocessing.Queue,
        user_config: UserConfig,
        **kwargs,
    ) -> None:
        super().__init__(user_config=user_config, **kwargs)
        self.user_config = user_config
        self.app: AIPerfTextualApp = AIPerfTextualApp()
        self.log_queue = log_queue

    @on_start
    async def _run_app(self) -> None:
        """Run the enhanced Textual application."""
        self.debug("Starting AIPerf Textual UI...")
        self.execute_async(self.app.run_async())

    @on_stop
    async def _on_stop(self) -> None:
        """Stop the Textual application gracefully."""
        if self.app:
            self.debug("Shutting down Textual UI")
            self.app.exit(return_code=0)

    @background_task(immediate=True, interval=LOG_REFRESH_INTERVAL)
    async def _consume_logs(self) -> None:
        """Consume log records from the queue and display them.

        This is a background task that runs every LOG_REFRESH_INTERVAL seconds
        to consume log records from the queue and display them in the log widget.
        """
        if self.app.log_viewer is None:
            return

        # Process all pending log records
        while not self.log_queue.empty():
            try:
                log_data = self.log_queue.get_nowait()
                self.app.log_viewer.display_log_record(log_data)
                await yield_to_event_loop()
            except Exception:
                # Silently ignore queue errors to avoid recursion
                break

    @on_records_progress
    async def _on_records_progress(self, records_stats: RecordsStats):
        """Callback for records progress updates."""
        if self.app.overview_progress:
            self.app.overview_progress.on_records_progress(records_stats)

    @on_requests_phase_progress
    async def _on_requests_phase_progress(
        self, phase: CreditPhase, requests_stats: RequestsStats
    ):
        """Callback for requests phase progress updates."""
        if self.app.overview_progress:
            self.app.overview_progress.on_requests_phase_progress(phase, requests_stats)

    @on_worker_update
    async def _on_worker_update(self, worker_id: str, worker_stats: WorkerStats):
        """Callback for worker updates."""
        # if self.app.overview_workers:
        #     self.app.overview_workers.update_worker_health(worker_id, worker_stats)

    # async def on_profile_results_update(self) -> None:
    #     """Process the final results with enhanced logging."""
    #     self.info("Performance testing completed successfully!")

    #     try:
    #         # Force refresh all displays
    #         if self.app.dashboard:
    #             self.app.dashboard.update_display()
    #         if self.app.overview_progress:
    #             self.app.overview_progress.update_display()

    #         if self.app.is_running:
    #             self.debug("Closing dashboard...")
    #             self.app.exit()

    #     except Exception as e:
    #         self.debug(lambda e=e: f"App cleanup handled: {e}")

    # async def on_profile_progress_update(self) -> None:
    #     """Update the profile progress with enhanced calculations and debugging."""
    #     try:
    #         # Force refresh all progress displays
    #         if self.app.dashboard:
    #             self.app.dashboard.update_display()
    #         if self.app.overview_progress:
    #             self.app.overview_progress.update_display()

    #     except Exception as e:
    #         self.warning(f"Progress update error: {e}")

    # async def on_profile_stats_update(self) -> None:
    #     """Update the profile statistics with enhanced error tracking."""
    #     try:
    #         # Force refresh all progress displays
    #         if self.app.dashboard:
    #             self.app.dashboard.update_display()
    #         if self.app.overview_progress:
    #             self.app.overview_progress.update_display()

    #     except Exception as e:
    #         self.warning(f"Stats update error: {e}")

    # @on_message(MessageType.WORKER_HEALTH)
    # async def on_worker_health_update(self, message: WorkerHealthMessage) -> None:
    #     """Update the worker health with enhanced error tracking."""
    #     try:
    #         # Update both worker dashboards
    #         if self.app.worker_dashboard:
    #             self.app.worker_dashboard.update_worker_health(message)
    #         if self.app.overview_workers:
    #             self.app.overview_workers.update_worker_health(message)

    #     except Exception as e:
    #         self.warning(f"Worker health update error: {e}")

    # @on_message(MessageType.PROFILE_RESULTS)
    # async def on_generic_message(self, message: Message) -> None:
    #     """Handle a generic message from the system controller."""
    #     try:
    #         if self.app.dashboard:
    #             self.app.dashboard.update_display()
    #         if self.app.overview_progress:
    #             self.app.overview_progress.update_display()

    #     except Exception as e:
    #         self.warning(f"Generic message handling error: {e}")
