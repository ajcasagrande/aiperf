# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    TabbedContent,
    TabPane,
)

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums import AIPerfUIType
from aiperf.common.enums.message_enums import MessageType
from aiperf.common.hooks import (
    on_start,
    on_stop,
)
from aiperf.common.messages import Message, WorkerHealthMessage
from aiperf.common.mixins import AIPerfLifecycleMixin
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.textual.logging_ui import LogViewer
from aiperf.ui.textual.progress_dashboard import ProgressDashboard
from aiperf.ui.textual.widgets import Header
from aiperf.ui.textual.worker_dashboard import WorkerDashboard
from aiperf.ui.ui_protocol import AIPerfUIFactory

_logger = AIPerfLogger(__name__)


class AIPerfTextualApp(App):
    """The main Textual application for AIPerf with clean, simplified styling."""

    CSS = """
    Screen {
        background: $surface;
    }

    Footer {
        background: $secondary;
        color: $text;
    }

    #main-container {
        height: 100%;
    }

    #dashboard-section {
        height: 3fr;
        min-height: 15;
    }

    #logs-section {
        height: 2fr;
    }

    TabbedContent {
        height: 1fr;
        width: 100%;
    }

    TabPane {
        height: 1fr;
        width: 100%;
        padding: 0;
    }

    /* Ensure dashboard widgets inside tabs are properly sized */
    TabPane > ProgressDashboard {
        height: 1fr;
        width: 100%;
    }

    TabPane > WorkerDashboard {
        height: 1fr;
        width: 100%;
    }

    /* Fix for content containers within tabs */
    TabPane Container {
        height: auto;
    }

    TabbedContent ContentSwitcher {
        height: 1fr;
    }

    Placeholder {
        height: 1fr;
    }

    TabPane Vertical {
        height: 1fr;
    }

    /* Horizontal layout for overview tab */
    TabPane Horizontal {
        height: 1fr;
    }

    TabPane Horizontal > ProgressDashboard {
        width: 1fr;
        height: 1fr;
    }

    TabPane Horizontal > WorkerDashboard {
        width: 1fr;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("1", "switch_tab('overview')", "Overview"),
        ("2", "switch_tab('performance')", "Performance"),
        ("3", "switch_tab('workers')", "Workers"),
    ]

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
        self.progress_tracker = progress_tracker
        self.dashboard: ProgressDashboard | None = None
        self.log_viewer: LogViewer | None = None
        self.worker_dashboard: WorkerDashboard | None = None
        # Separate instances for the combined view
        self.overview_progress: ProgressDashboard | None = None
        self.overview_workers: WorkerDashboard | None = None
        self.title = "AIPerf Performance Monitor"
        self.sub_title = "Real-time AI Performance Testing Dashboard"

    def compose(self) -> ComposeResult:
        """Compose the clean application layout."""
        yield Header()

        with Vertical(id="main-container"):  # noqa: SIM117 - textual ui layout
            with Container(id="dashboard-section"):  # noqa: SIM117
                with TabbedContent(initial="overview"):  # noqa: SIM117
                    with TabPane("Overview", id="overview"):  # noqa: SIM117
                        with Horizontal():  # noqa: SIM117
                            self.overview_progress = ProgressDashboard(
                                self.progress_tracker
                            )
                            yield self.overview_progress
                            self.overview_workers = WorkerDashboard()
                            yield self.overview_workers

                    with TabPane("Performance Dashboard", id="performance"):  # noqa: SIM117
                        self.dashboard = ProgressDashboard(self.progress_tracker)
                        yield self.dashboard

                    with TabPane("Worker Status", id="workers"):
                        self.worker_dashboard = WorkerDashboard()
                        yield self.worker_dashboard

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
        """Show confirmation dialog as an overlay."""
        self.exit(return_code=0)
        raise KeyboardInterrupt()


@AIPerfUIFactory.register(AIPerfUIType.TEXTUAL)
class TextualUI(AIPerfLifecycleMixin):
    """Enhanced mixin for Textual-based UI functionality with improved visual feedback."""

    def __init__(self, progress_tracker: ProgressTracker, **kwargs) -> None:
        super().__init__(**kwargs)
        self.app: AIPerfTextualApp = AIPerfTextualApp(progress_tracker)
        self.progress_tracker = progress_tracker

    @on_stop
    async def _on_stop(self) -> None:
        """Stop the Textual application gracefully."""
        if self.app:
            self.debug("Shutting down Textual UI")
            self.app.exit()

    @on_start
    async def _run_app(self) -> None:
        """Run the enhanced Textual application."""
        self.debug("Starting AIPerf Textual UI...")
        await self.app.run_async()

    async def on_profile_results_update(self) -> None:
        """Process the final results with enhanced logging."""
        self.info("Performance testing completed successfully!")

        try:
            # Force refresh all displays
            if self.app.dashboard:
                self.app.dashboard.update_display()
            if self.app.overview_progress:
                self.app.overview_progress.update_display()

            if self.app.is_running:
                self.debug("Closing dashboard...")
                self.app.exit()

        except Exception as e:
            self.debug(lambda e=e: f"App cleanup handled: {e}")

    async def on_profile_progress_update(self) -> None:
        """Update the profile progress with enhanced calculations and debugging."""
        try:
            profile = self.progress_tracker.current_profile_run
            if profile is None:
                return
            # Force refresh all progress displays
            if self.app.dashboard:
                self.app.dashboard.update_display()
            if self.app.overview_progress:
                self.app.overview_progress.update_display()

        except Exception as e:
            self.warning(f"Progress update error: {e}")

    async def on_profile_stats_update(self) -> None:
        """Update the profile statistics with enhanced error tracking."""
        try:
            profile = self.progress_tracker.current_profile_run
            if profile is None:
                return

            # Force refresh all progress displays
            if self.app.dashboard:
                self.app.dashboard.update_display()
            if self.app.overview_progress:
                self.app.overview_progress.update_display()

        except Exception as e:
            self.warning(f"Stats update error: {e}")

    async def on_worker_health_update(self, message: WorkerHealthMessage) -> None:
        """Update the worker health with enhanced error tracking."""
        try:
            # Update both worker dashboards
            if self.app.worker_dashboard:
                self.app.worker_dashboard.update_worker_health(message)
            if self.app.overview_workers:
                self.app.overview_workers.update_worker_health(message)

        except Exception as e:
            self.warning(f"Worker health update error: {e}")

    async def on_message(self, message: Message) -> None:
        """Handle a message from the system controller."""
        try:
            if message.message_type == MessageType.WORKER_HEALTH:
                # Type check the message before passing it
                if isinstance(message, WorkerHealthMessage):
                    await self.on_worker_health_update(message)
            else:
                # Update all progress displays for other message types
                if self.app.dashboard:
                    self.app.dashboard.update_display()
                if self.app.overview_progress:
                    self.app.overview_progress.update_display()
        except Exception as e:
            self.warning(f"Message handling error: {e}")
