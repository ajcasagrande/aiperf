# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label

from aiperf.ui.widgets.logs_viewer import LogsViewerWidget
from aiperf.ui.widgets.phase_timeline import PhaseTimelineWidget
from aiperf.ui.widgets.system_overview import SystemOverviewWidget
from aiperf.ui.widgets.worker_status import WorkerStatusWidget

if TYPE_CHECKING:
    from aiperf.common.worker_models import WorkerHealthMessage
    from aiperf.progress.progress_models import (
        CreditPhaseCompleteMessage,
        CreditPhaseProgressMessage,
        CreditPhaseStartMessage,
        ProfileResultsMessage,
        RecordsProcessingStatsMessage,
    )
    from aiperf.progress.progress_tracker import ProgressTracker


class DashboardScreen(Screen):
    """Main dashboard screen with all widgets."""

    DEFAULT_CSS = """
    DashboardScreen {
        background: #1a1a1a;
    }

    DashboardScreen .main-layout {
        layout: vertical;
        height: 100%;
        padding: 1;
    }

    DashboardScreen .top-section {
        height: 12;
        width: 100%;
    }

    DashboardScreen .middle-section {
        layout: horizontal;
        height: 1fr;
        width: 100%;
    }

    DashboardScreen .middle-left {
        width: 50%;
    }

    DashboardScreen .middle-right {
        width: 50%;
    }

    DashboardScreen .bottom-section {
        height: 1fr;
        width: 100%;
    }
    """

    BINDINGS = [
        Binding("f1", "toggle_help", "Help"),
        Binding("f5", "refresh_all", "Refresh"),
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, progress_tracker: "ProgressTracker", **kwargs) -> None:
        super().__init__(**kwargs)
        self.progress_tracker = progress_tracker

        # Create widgets
        self.system_overview = SystemOverviewWidget(progress_tracker)
        self.phase_timeline = PhaseTimelineWidget(progress_tracker)
        self.worker_status = WorkerStatusWidget(progress_tracker)
        self.logs_viewer = LogsViewerWidget(progress_tracker)

        # Track widget instances for updates
        self.widgets = [
            self.system_overview,
            self.phase_timeline,
            self.worker_status,
            self.logs_viewer,
        ]

    def compose(self) -> ComposeResult:
        """Compose the dashboard screen."""
        yield Header(show_clock=True)

        # Main layout
        with Vertical(classes="main-layout"):
            # Top section - System overview
            with Vertical(classes="top-section"):
                yield self.system_overview

            # Middle section - Phase timeline and worker status side by side
            with Horizontal(classes="middle-section"):
                with Vertical(classes="middle-left"):
                    yield self.phase_timeline
                with Vertical(classes="middle-right"):
                    yield self.worker_status

            # Bottom section - Logs
            with Vertical(classes="bottom-section"):
                yield self.logs_viewer

        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is mounted."""
        # Set up periodic updates
        self.set_interval(1.0, self.update_all_widgets)

    def update_all_widgets(self) -> None:
        """Update all widgets with fresh data."""
        for widget in self.widgets:
            if hasattr(widget, "update_content"):
                widget.update_content()

    def action_refresh_all(self) -> None:
        """Refresh all widgets manually."""
        self.update_all_widgets()
        self.notify("All widgets refreshed")

    def action_toggle_help(self) -> None:
        """Toggle help screen."""
        self.app.push_screen(HelpScreen())


class HelpScreen(Screen):
    """Simple help screen."""

    DEFAULT_CSS = """
    HelpScreen {
        background: #1a1a1a;
    }

    HelpScreen .help-container {
        padding: 2;
        width: 80%;
        height: 80%;
        margin: 5 10%;
        background: #2a2a2a;
        border: solid #76b900;
    }

    HelpScreen .help-title {
        text-style: bold;
        color: #76b900;
        padding-bottom: 1;
    }

    HelpScreen .help-section {
        text-style: bold;
        color: #ffffff;
        padding: 1 0;
    }

    HelpScreen .help-desc {
        color: #cccccc;
        padding-left: 2;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
        Binding("q", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the help screen."""
        with Vertical(classes="help-container"):
            yield Label("AIPerf Dashboard Help", classes="help-title")

            yield Label("Keyboard Shortcuts:", classes="help-section")
            yield Label("F1 - Toggle this help", classes="help-desc")
            yield Label("F5 - Refresh all widgets", classes="help-desc")
            yield Label("Ctrl+C / Ctrl+Q - Quit application", classes="help-desc")
            yield Label("Escape - Close dialogs", classes="help-desc")

            yield Label("Navigation:", classes="help-section")
            yield Label("Tab - Navigate between widgets", classes="help-desc")
            yield Label("Enter - Select/activate focused item", classes="help-desc")
            yield Label("Arrow keys - Navigate within widgets", classes="help-desc")

            yield Label("Widget Features:", classes="help-section")
            yield Label(
                "System Overview - High-level metrics and status", classes="help-desc"
            )
            yield Label(
                "Phase Timeline - Interactive phase progress", classes="help-desc"
            )
            yield Label(
                "Worker Status - Real-time worker monitoring", classes="help-desc"
            )
            yield Label("System Logs - Filterable log viewer", classes="help-desc")

            yield Label("", classes="help-desc")
            yield Label("Press ESC or Q to close this help", classes="help-desc")

    def action_dismiss(self) -> None:
        """Dismiss the help screen."""
        self.dismiss()


class AIPerfTextualApp(App):
    """Main AIPerf Textual application."""

    CSS = """
    AIPerfTextualApp {
        background: #1a1a1a;
        color: #ffffff;
    }

    AIPerfTextualApp .nvidia-theme {
        background: #1a1a1a;
        color: #ffffff;
    }

    AIPerfTextualApp .nvidia-theme .primary {
        color: #76b900;
    }

    AIPerfTextualApp .nvidia-theme .secondary {
        color: #2d5aa0;
    }

    AIPerfTextualApp .nvidia-theme .accent {
        color: #00d4aa;
    }

    AIPerfTextualApp .nvidia-theme .success {
        color: #00ff00;
    }

    AIPerfTextualApp .nvidia-theme .warning {
        color: #ffaa00;
    }

    AIPerfTextualApp .nvidia-theme .error {
        color: #ff0000;
    }
    """

    TITLE = "NVIDIA AIPerf Dashboard"
    SUB_TITLE = "AI Performance Profiling System"

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, progress_tracker: "ProgressTracker", **kwargs) -> None:
        super().__init__(**kwargs)
        self.progress_tracker = progress_tracker
        self.dashboard_screen = None

    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self.dark = True  # Always use dark theme

        # Create and install dashboard screen
        self.dashboard_screen = DashboardScreen(self.progress_tracker)
        self.install_screen(self.dashboard_screen, name="dashboard")

        # Show dashboard
        self.push_screen("dashboard")

    def on_ready(self) -> None:
        """Called when the app is ready."""
        self.notify("AIPerf Dashboard started")

    async def on_credit_phase_progress_update(
        self, message: "CreditPhaseProgressMessage"
    ) -> None:
        """Handle credit phase progress updates."""
        if self.dashboard_screen:
            self.progress_tracker.on_credit_phase_progress(message)
            self.dashboard_screen.system_overview.update_content()
            self.dashboard_screen.phase_timeline.update_content()

    async def on_credit_phase_start_update(
        self, message: "CreditPhaseStartMessage"
    ) -> None:
        """Handle credit phase start updates."""
        if self.dashboard_screen:
            self.progress_tracker.on_credit_phase_start(message)
            self.dashboard_screen.system_overview.update_content()
            self.dashboard_screen.phase_timeline.update_content()

    async def on_credit_phase_complete_update(
        self, message: "CreditPhaseCompleteMessage"
    ) -> None:
        """Handle credit phase complete updates."""
        if self.dashboard_screen:
            self.progress_tracker.on_credit_phase_complete(message)
            self.dashboard_screen.system_overview.update_content()

    async def on_processing_stats_update(
        self, message: "RecordsProcessingStatsMessage"
    ) -> None:
        """Handle processing stats updates."""
        if self.dashboard_screen:
            self.progress_tracker.on_processing_stats(message)
            self.dashboard_screen.system_overview.update_content()

    async def on_worker_health_update(self, message: "WorkerHealthMessage") -> None:
        """Handle worker health updates."""
        if self.dashboard_screen:
            self.progress_tracker.on_worker_health(message)
            self.dashboard_screen.worker_status.update_content()

    async def on_profile_results_update(self, message: "ProfileResultsMessage") -> None:
        """Handle profile results updates."""
        if self.dashboard_screen:
            self.progress_tracker.on_profile_results(message)
            self.dashboard_screen.system_overview.update_content()

    def add_log_entry(
        self, timestamp: float, level: str, logger: str, message: str
    ) -> None:
        """Add a log entry to the dashboard."""
        if self.dashboard_screen:
            self.dashboard_screen.logs_viewer.add_log_entry(
                timestamp, level, logger, message
            )

    def get_dashboard_summary(self) -> dict:
        """Get a summary of the current dashboard state."""
        if not self.dashboard_screen:
            return {}

        return {
            "system_overview": getattr(
                self.dashboard_screen.system_overview, "get_summary", lambda: {}
            )(),
            "phase_timeline": getattr(
                self.dashboard_screen.phase_timeline, "get_summary", lambda: {}
            )(),
            "worker_status": self.dashboard_screen.worker_status.get_worker_summary(),
            "logs_viewer": self.dashboard_screen.logs_viewer.get_log_summary(),
        }


# Integration class for connecting with the existing AIPerf system
class AIPerfTextualDashboard:
    """Integration class that connects the Textual app with the existing AIPerf system."""

    def __init__(self, progress_tracker: "ProgressTracker") -> None:
        self.progress_tracker = progress_tracker
        self.app = AIPerfTextualApp(progress_tracker)
        self.running = False

    async def start(self) -> None:
        """Start the Textual dashboard."""
        self.running = True
        await self.app.run_async()

    async def stop(self) -> None:
        """Stop the Textual dashboard."""
        self.running = False
        if self.app:
            await self.app.exit()

    async def on_credit_phase_progress_update(
        self, message: "CreditPhaseProgressMessage"
    ) -> None:
        """Handle credit phase progress updates."""
        if self.running:
            await self.app.on_credit_phase_progress_update(message)

    async def on_credit_phase_start_update(
        self, message: "CreditPhaseStartMessage"
    ) -> None:
        """Handle credit phase start updates."""
        if self.running:
            await self.app.on_credit_phase_start_update(message)

    async def on_credit_phase_complete_update(
        self, message: "CreditPhaseCompleteMessage"
    ) -> None:
        """Handle credit phase complete updates."""
        if self.running:
            await self.app.on_credit_phase_complete_update(message)

    async def on_processing_stats_update(
        self, message: "RecordsProcessingStatsMessage"
    ) -> None:
        """Handle processing stats updates."""
        if self.running:
            await self.app.on_processing_stats_update(message)

    async def on_worker_health_update(self, message: "WorkerHealthMessage") -> None:
        """Handle worker health updates."""
        if self.running:
            await self.app.on_worker_health_update(message)

    async def on_profile_results_update(self, message: "ProfileResultsMessage") -> None:
        """Handle profile results updates."""
        if self.running:
            await self.app.on_profile_results_update(message)

    def add_log_entry(
        self, timestamp: float, level: str, logger: str, message: str
    ) -> None:
        """Add a log entry to the dashboard."""
        if self.running:
            self.app.add_log_entry(timestamp, level, logger, message)
