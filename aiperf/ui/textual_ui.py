# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import TYPE_CHECKING

from aiperf.common.hooks import AIPerfLifecycleMixin, on_start, on_stop
from aiperf.ui.textual_dashboard import AIPerfTextualDashboard

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

logger = logging.getLogger(__name__)


class AIPerfTextualUI(AIPerfLifecycleMixin):
    """Textual-based UI implementation that replaces the Rich dashboard.

    This class provides the same interface as the existing AIPerfUI but uses
    the new Textual framework for a more interactive and sophisticated user experience.
    """

    def __init__(self, progress_tracker: "ProgressTracker") -> None:
        super().__init__()
        self.progress_tracker = progress_tracker
        self.dashboard = AIPerfTextualDashboard(progress_tracker)
        self.running = False

    @on_start
    async def _on_start(self) -> None:
        """Start the Textual UI."""
        try:
            logger.info("Starting Textual UI dashboard")
            self.running = True
            await self.dashboard.start()
        except Exception as e:
            logger.error("Failed to start Textual UI: %s", e)
            self.running = False
            raise

    @on_stop
    async def _on_stop(self) -> None:
        """Stop the Textual UI."""
        try:
            logger.info("Stopping Textual UI dashboard")
            self.running = False
            await self.dashboard.stop()
        except Exception as e:
            logger.error("Failed to stop Textual UI: %s", e)

    async def on_credit_phase_progress_update(
        self, message: "CreditPhaseProgressMessage"
    ) -> None:
        """Update progress display for credit phase progress."""
        try:
            if self.running:
                await self.dashboard.on_credit_phase_progress_update(message)
        except Exception as e:
            logger.error("Error updating credit phase progress: %s", e)

    async def on_credit_phase_start_update(
        self, message: "CreditPhaseStartMessage"
    ) -> None:
        """Update progress display for credit phase start."""
        try:
            if self.running:
                await self.dashboard.on_credit_phase_start_update(message)
        except Exception as e:
            logger.error("Error updating credit phase start: %s", e)

    async def on_credit_phase_complete_update(
        self, message: "CreditPhaseCompleteMessage"
    ) -> None:
        """Update progress display for credit phase complete."""
        try:
            if self.running:
                await self.dashboard.on_credit_phase_complete_update(message)
        except Exception as e:
            logger.error("Error updating credit phase complete: %s", e)

    async def on_processing_stats_update(
        self, message: "RecordsProcessingStatsMessage"
    ) -> None:
        """Update progress display for processing stats."""
        try:
            if self.running:
                await self.dashboard.on_processing_stats_update(message)
        except Exception as e:
            logger.error("Error updating processing stats: %s", e)

    async def on_worker_health_update(self, message: "WorkerHealthMessage") -> None:
        """Update progress display for worker health."""
        try:
            if self.running:
                await self.dashboard.on_worker_health_update(message)
        except Exception as e:
            logger.error("Error updating worker health: %s", e)

    async def on_profile_results_update(self, message: "ProfileResultsMessage") -> None:
        """Update progress display for profile results."""
        try:
            if self.running:
                await self.dashboard.on_profile_results_update(message)
        except Exception as e:
            logger.error("Error updating profile results: %s", e)

    def add_log_entry(
        self, timestamp: float, level: str, logger: str, message: str
    ) -> None:
        """Add a log entry to the dashboard."""
        try:
            if self.running:
                self.dashboard.add_log_entry(timestamp, level, logger, message)
        except Exception as e:
            logger.error("Error adding log entry: %s", e)

    def get_dashboard_summary(self) -> dict:
        """Get a summary of the current dashboard state."""
        try:
            if self.running:
                return self.dashboard.app.get_dashboard_summary()
            return {}
        except Exception as e:
            logger.error("Error getting dashboard summary: %s", e)
            return {}

    @property
    def is_running(self) -> bool:
        """Check if the UI is currently running."""
        return self.running

    @property
    def current_theme(self) -> str:
        """Get the current theme (dark/light)."""
        if self.running and self.dashboard.app:
            return "dark" if self.dashboard.app.dark else "light"
        return "dark"

    def set_theme(self, theme: str) -> None:
        """Set the UI theme."""
        if self.running and self.dashboard.app:
            self.dashboard.app.dark = theme == "dark"

    def notify(self, message: str, title: str = "") -> None:
        """Send a notification to the user."""
        if self.running and self.dashboard.app:
            self.dashboard.app.notify(message, title=title)

    def focus_widget(self, widget_name: str) -> None:
        """Focus on a specific widget."""
        if self.running and self.dashboard.app.dashboard_screen:
            widget_map = {
                "system_overview": self.dashboard.app.dashboard_screen.system_overview,
                "phase_timeline": self.dashboard.app.dashboard_screen.phase_timeline,
                "worker_status": self.dashboard.app.dashboard_screen.worker_status,
                "logs_viewer": self.dashboard.app.dashboard_screen.logs_viewer,
            }

            if widget_name in widget_map:
                widget_map[widget_name].focus()

    def toggle_help(self) -> None:
        """Toggle the help screen."""
        if self.running and self.dashboard.app:
            self.dashboard.app.push_screen("help")

    def refresh_all(self) -> None:
        """Refresh all widgets."""
        if self.running and self.dashboard.app.dashboard_screen:
            self.dashboard.app.dashboard_screen.update_all_widgets()


# For backward compatibility with the existing system
class AIPerfUI(AIPerfTextualUI):
    """Backward compatibility alias for the existing AIPerfUI class."""

    pass


# Advanced UI features that extend the base functionality
class AIPerfAdvancedUI(AIPerfTextualUI):
    """Advanced UI with additional features for power users."""

    def __init__(self, progress_tracker: "ProgressTracker") -> None:
        super().__init__(progress_tracker)
        self.custom_widgets = {}
        self.keyboard_shortcuts = {}
        self.themes = ["dark", "light", "nvidia", "terminal"]

    def add_custom_widget(self, name: str, widget_class, **kwargs) -> None:
        """Add a custom widget to the dashboard."""
        # This would allow users to add their own widgets
        # Implementation would depend on the specific widget requirements
        pass

    def register_keyboard_shortcut(
        self, key: str, action: str, description: str
    ) -> None:
        """Register a custom keyboard shortcut."""
        self.keyboard_shortcuts[key] = {"action": action, "description": description}

    def export_dashboard_config(self) -> dict:
        """Export the current dashboard configuration."""
        return {
            "theme": self.current_theme,
            "custom_widgets": list(self.custom_widgets.keys()),
            "keyboard_shortcuts": self.keyboard_shortcuts,
            "dashboard_summary": self.get_dashboard_summary(),
        }

    def import_dashboard_config(self, config: dict) -> None:
        """Import a dashboard configuration."""
        if "theme" in config:
            self.set_theme(config["theme"])

        # Additional configuration import logic would go here

    def get_performance_metrics(self) -> dict:
        """Get performance metrics about the UI itself."""
        return {
            "is_running": self.is_running,
            "current_theme": self.current_theme,
            "widgets_count": len(self.custom_widgets),
            "shortcuts_count": len(self.keyboard_shortcuts),
        }


# Factory function for creating the appropriate UI instance
def create_aiperf_ui(
    progress_tracker: "ProgressTracker", ui_type: str = "standard"
) -> AIPerfTextualUI:
    """Factory function to create the appropriate UI instance.

    Args:
        progress_tracker: The progress tracker instance
        ui_type: Type of UI to create ("standard", "advanced")

    Returns:
        An instance of the appropriate UI class
    """
    if ui_type == "advanced":
        return AIPerfAdvancedUI(progress_tracker)
    else:
        return AIPerfTextualUI(progress_tracker)


# Configuration for different UI modes
UI_CONFIGS = {
    "executive": {
        "theme": "nvidia",
        "widgets": ["system_overview", "phase_timeline"],
        "features": ["notifications", "auto_refresh"],
    },
    "developer": {
        "theme": "dark",
        "widgets": [
            "system_overview",
            "phase_timeline",
            "worker_status",
            "logs_viewer",
        ],
        "features": ["notifications", "auto_refresh", "keyboard_shortcuts", "export"],
    },
    "operator": {
        "theme": "light",
        "widgets": ["system_overview", "worker_status", "logs_viewer"],
        "features": ["notifications", "auto_refresh", "alerts"],
    },
}
