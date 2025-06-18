#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0

import logging

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Footer, Header

from aiperf.common.hooks import (
    AIPerfLifecycleMixin,
    aiperf_task,
    on_stop,
)
from aiperf.common.progress_tracker import ProgressTracker
from aiperf.ui.logging_ui import LogViewer
from aiperf.ui.progress_dashboard import ProgressDashboard

logger = logging.getLogger(__name__)


class AIPerfTextualApp(App):
    """The main Textual application for AIPerf with clean, simplified styling."""

    CSS = """
    Screen {
        background: $surface;
    }

    Header {
        background: $primary;
        color: $text;
        text-style: bold;
    }

    Footer {
        background: $secondary;
        color: $text;
    }

    #main-container {
        height: 100%;
    }

    #dashboard-section {
        height: 2fr;
    }

    #logs-section {
        height: 1fr;
        min-height: 8;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
    ]

    def __init__(self, progress_tracker: ProgressTracker) -> None:
        super().__init__()
        self.progress_tracker = progress_tracker
        self.dashboard: ProgressDashboard | None = None
        self.log_viewer: LogViewer | None = None
        self.title = "AIPerf Performance Monitor"
        self.sub_title = "Real-time AI Performance Testing Dashboard"

    def compose(self) -> ComposeResult:
        """Compose the clean application layout."""
        yield Header()

        with Vertical(id="main-container"):
            with Container(id="dashboard-section"):
                self.dashboard = ProgressDashboard(self.progress_tracker)
                yield self.dashboard

            with Container(id="logs-section"):
                self.log_viewer = LogViewer()
                yield self.log_viewer

        yield Footer()

    async def action_quit(self) -> None:
        """Quit the application gracefully."""

        self.exit()


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
            profile = self.progress_tracker.current_profile
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
            profile = self.progress_tracker.current_profile
            if profile is None:
                return

            # Force refresh the display
            self.app.dashboard.update_display()

        except Exception as e:
            logger.warning("Stats update error: %s", e)
