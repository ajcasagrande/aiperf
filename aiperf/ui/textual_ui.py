# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from collections.abc import Callable

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Grid, Vertical
from textual.widgets import (
    Button,
    Label,
    Static,
    TabbedContent,
    TabPane,
)

from aiperf.common.hooks import (
    AIPerfLifecycleMixin,
    aiperf_task,
    on_stop,
)
from aiperf.common.models.messages import WorkerHealthMessage
from aiperf.common.progress_tracker import ProgressTracker
from aiperf.ui.logging_ui import LogViewer
from aiperf.ui.progress_dashboard import ProgressDashboard
from aiperf.ui.widgets import Header
from aiperf.ui.worker_dashboard import WorkerDashboard

logger = logging.getLogger(__name__)


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

    /* Specific fixes for WorkerDashboard scrolling */
    TabPane > WorkerDashboard > #workers-scroll {
        height: 1fr;
        overflow-y: auto;
    }

    TabPane > WorkerDashboard > #workers-scroll > Vertical {
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
        # if hasattr(self, "_quit_dialog") and self._quit_dialog.parent:
        #     # Dialog already visible
        #     return

        # def _on_quit() -> None:
        #     self.exit(return_code=0)
        #     raise KeyboardInterrupt()

        # self._quit_dialog = QuitConfirmationDialog()
        # self._quit_dialog.on_quit = _on_quit
        # await self.mount(self._quit_dialog)


class TextualUIMixin(AIPerfLifecycleMixin):
    """Enhanced mixin for Textual-based UI functionality with improved visual feedback."""

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
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
            # profile = self.progress_tracker.current_profile
            # if profile is None:
            #     return
            # Force refresh the display
            self.app.dashboard.update_display()

        except Exception as e:
            logger.warning("Progress update error: %s", e)

    async def on_profile_stats_update(self) -> None:
        """Update the profile statistics with enhanced error tracking."""
        if not self.app.dashboard:
            return

        try:
            # profile = self.progress_tracker.current_profile
            # if profile is None:
            #     return

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


class QuitConfirmationDialog(Static):
    """Overlay dialog to confirm quitting the application."""

    DEFAULT_CSS = """
    QuitConfirmationDialog {
        dock: top;
        layer: overlay;
        align: center middle;
    }

    #dialog-box {
        grid-size: 2;
        grid-gutter: 1 2;
        grid-rows: 1fr 3;
        padding: 0 1;
        width: 50;
        height: 9;
        border: thick $primary;
        background: $surface;
        margin: 1;
    }

    #question {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
    }

    QuitConfirmationDialog Button {
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self):
        super().__init__()
        self.on_quit: Callable[[], None] | None = None

    def compose(self) -> ComposeResult:
        """Compose the confirmation dialog."""
        yield Grid(
            Label("Are you sure you want to exit AIPerf?", id="question"),
            Button("Yes, Exit", variant="error", id="quit"),
            Button("Cancel", variant="primary", id="cancel"),
            id="dialog-box",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the confirmation dialog."""
        if event.button.id == "quit" and self.on_quit:
            self.on_quit()
        self.remove()

    def action_cancel(self) -> None:
        """Cancel the dialog with Escape key."""
        self.remove()
