# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import (
    TabbedContent,
    TabPane,
)

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.common.enums import AIPerfUIType, MessageType
from aiperf.common.hooks import (
    aiperf_task,
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

logger = AIPerfLogger(__name__)


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
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("1", "switch_tab('performance')", "Performance"),
        ("2", "switch_tab('workers')", "Workers"),
    ]

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
        self.progress_tracker = progress_tracker
        self.dashboard: ProgressDashboard | None = None
        self.log_viewer: LogViewer | None = None
        self.worker_dashboard: WorkerDashboard | None = None
        self.title = "AIPerf Performance Monitor"
        self.sub_title = "Real-time AI Performance Testing Dashboard"

    def compose(self) -> ComposeResult:
        """Compose the clean application layout."""
        yield Header()

        with Vertical(id="main-container"):  # noqa: SIM117 - textual ui layout
            with Container(id="dashboard-section"):  # noqa: SIM117
                with TabbedContent(initial="performance"):  # noqa: SIM117
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
            logger.error(f"Error switching to tab {tab_id}: {e}")

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
            logger.debug("Shutting down Textual UI")
            self.app.exit()

    @aiperf_task
    async def _run_app(self) -> None:
        """Run the enhanced Textual application."""
        logger.debug("Starting AIPerf Textual UI...")
        await self.app.run_async()

    async def on_profile_results_update(self) -> None:
        """Process the final results with enhanced logging."""
        logger.info("Performance testing completed successfully!")

        try:
            # Force refresh the display
            if self.app.dashboard:
                self.app.dashboard.update_display()

            if self.app.is_running:
                logger.debug("Closing dashboard...")
                self.app.exit()

        except Exception as e:
            logger.debug("App cleanup handled: %s", e)

    async def on_profile_progress_update(self) -> None:
        """Update the profile progress with enhanced calculations and debugging."""
        if not self.app.dashboard:
            return

        try:
            profile = self.progress_tracker.current_profile_run
            if profile is None:
                return
            # Force refresh the display
            self.app.dashboard.update_display()

        except Exception as e:
            logger.warning("Progress update error: %s", e)

    async def on_profile_stats_update(self) -> None:
        """Update the profile statistics with enhanced error tracking."""
        if not self.app.dashboard:
            return

        try:
            profile = self.progress_tracker.current_profile_run
            if profile is None:
                return

            # Force refresh the display
            self.app.dashboard.update_display()

        except Exception as e:
            logger.warning("Stats update error: %s", e)

    async def on_worker_health_update(self, message: WorkerHealthMessage) -> None:
        """Update the worker health with enhanced error tracking."""
        if not self.app.worker_dashboard:
            return

        try:
            self.app.worker_dashboard.update_worker_health(message)

        except Exception as e:
            logger.warning("Worker health update error: %s", e)

    async def on_message(self, message: Message) -> None:
        """Handle a message from the system controller."""
        _message_mappings = {
            MessageType.WORKER_HEALTH: self.on_worker_health_update,
        }

        if message.message_type in _message_mappings:
            await _message_mappings[message.message_type](message)
        else:
            if not self.app.dashboard:
                return
            self.app.dashboard.update_display()
