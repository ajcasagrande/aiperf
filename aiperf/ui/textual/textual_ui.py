# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import multiprocessing
import os
import signal

os.environ["TEXTUAL_SHOW_RETURN"] = "true"

from rich.console import RenderableType
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import TabbedContent

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.config import UserConfig
from aiperf.common.decorators import implements_protocol
from aiperf.common.enums import AIPerfUIType
from aiperf.common.factories import AIPerfUIFactory
from aiperf.common.hooks import background_task, on_start, on_stop
from aiperf.common.protocols import AIPerfUIProtocol
from aiperf.common.utils import yield_to_event_loop
from aiperf.ui.base_ui import BaseAIPerfUI
from aiperf.ui.textual.custom import CustomHeader, aiperf_theme
from aiperf.ui.textual.logging_ui import LogViewer

_logger = AIPerfLogger(__name__)


@implements_protocol(AIPerfUIProtocol)
@AIPerfUIFactory.register(AIPerfUIType.TEXTUAL)
class AIPerfTextualUI(BaseAIPerfUI):
    """Enhanced mixin for Textual-based UI functionality with improved visual feedback."""

    LOG_REFRESH_INTERVAL_SEC = 0.1

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

    @background_task(immediate=True, interval=LOG_REFRESH_INTERVAL_SEC)
    async def _consume_logs(self) -> None:
        """Consume log records from the queue and display them.

        This is a background task that runs every LOG_REFRESH_INTERVAL_SEC seconds
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


class AIPerfTextualApp(App):
    CSS = """
    #main-container {
        height: 100%;
    }

    #dashboard-section {
        height: 3fr;
        min-height: 14;
    }

    Tab {
        text-style: bold;
    }

    #logs-section {
        height: 2fr;
        max-height: 16;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        # ("1", "switch_tab('overview')", "Overview"),
        # ("2", "switch_tab('performance')", "Performance"),
        # ("3", "switch_tab('workers')", "Workers"),
        ("0", "toggle_log_auto_scroll", "Toggle Log Auto Scroll"),
    ]

    def __init__(self) -> None:
        super().__init__()
        # self.dashboard: ProgressDashboard | None = None
        self.log_viewer: LogViewer | None = None
        # self.worker_dashboard: WorkerDashboard | None = None
        # Separate instances for the combined view
        # self.overview_progress: ProgressDashboard | None = None
        # self.overview_workers: WorkerDashboard | None = None
        self.title = "NVIDIA AIPerf"
        # self.sub_title = "Real-time AI Performance Testing Dashboard"
        self._profile_results: list[RenderableType] = []

    def on_mount(self) -> None:
        self.register_theme(aiperf_theme)
        self.theme = "aiperf"

    def compose(self) -> ComposeResult:
        """Compose the clean application layout."""
        yield CustomHeader()

        with Vertical(id="main-container"):  # noqa: SIM117 - textual ui layout
            # with Container(id="dashboard-section"):  # noqa: SIM117
            #     with TabbedContent(initial="overview"):  # noqa: SIM117
            #         with TabPane("Overview", id="overview"):  # noqa: SIM117
            #             with Horizontal():  # noqa: SIM117
            #                 self.overview_progress = ProgressDashboard()
            #                 yield self.overview_progress
            #                 self.overview_workers = WorkerDashboard()
            #                 yield self.overview_workers

            #         with TabPane("Performance Dashboard", id="performance"):  # noqa: SIM117
            #             self.dashboard = ProgressDashboard()
            #             yield self.dashboard

            #         with TabPane("Worker Status", id="workers"):
            #             self.worker_dashboard = WorkerDashboard()
            #             yield self.worker_dashboard

            with Container(id="logs-section"):
                self.log_viewer = LogViewer()
                yield self.log_viewer

        # yield Footer()

    async def action_switch_tab(self, tab_id: str) -> None:
        """Switch to a specific tab."""
        try:
            tabbed_content = self.query_one(TabbedContent)
            tabbed_content.active = tab_id
        except Exception as e:
            _logger.error(f"Error switching to tab {tab_id}: {e}")

    async def action_quit(self) -> None:
        """Stop the UI and forward the signal to the main process."""
        self.exit(return_code=0)
        # Forward the signal to the main process
        os.kill(os.getpid(), signal.SIGINT)

    async def action_toggle_log_auto_scroll(self) -> None:
        """Toggle the auto scroll of the log viewer."""
        if self.log_viewer is None:
            return
        self.log_viewer.auto_scroll = not self.log_viewer.auto_scroll
