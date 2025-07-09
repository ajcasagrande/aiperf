# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
AIPerf User Interface Module

This module provides both the legacy Rich-based UI and the new Textual-based UI
for the AIPerf system. The Textual UI offers a more interactive and sophisticated
user experience while maintaining backward compatibility with the existing system.
"""

__all__ = [
    # Legacy Rich UI (for backward compatibility)
    "AIPerfRichDashboard",
    "LogsDashboardMixin",
    # New Textual UI (recommended)
    "AIPerfTextualUI",
    "AIPerfAdvancedUI",
    "AIPerfTextualDashboard",
    "create_aiperf_ui",
    # Backward compatibility alias
    "AIPerfUI",
    # Base widgets and components
    "BaseAIPerfWidget",
    "BaseContainerWidget",
    "InteractiveAIPerfWidget",
    "DataDisplayWidget",
    # Specific widgets
    "SystemOverviewWidget",
    "PhaseTimelineWidget",
    "WorkerStatusWidget",
    "LogsViewerWidget",
]

# Legacy Rich UI imports
# Base widget system
from aiperf.ui.base_widgets import (
    BaseAIPerfWidget,
    BaseContainerWidget,
    DataDisplayWidget,
    InteractiveAIPerfWidget,
)
from aiperf.ui.logs_mixin import LogsDashboardMixin
from aiperf.ui.rich_dashboard import AIPerfRichDashboard
from aiperf.ui.textual_dashboard import AIPerfTextualDashboard

# New Textual UI imports
from aiperf.ui.textual_ui import (
    AIPerfAdvancedUI,
    AIPerfTextualUI,
    AIPerfUI,  # Backward compatibility alias
    create_aiperf_ui,
)

# Specific widgets
from aiperf.ui.widgets import (
    LogsViewerWidget,
    PhaseTimelineWidget,
    SystemOverviewWidget,
    WorkerStatusWidget,
)

# UI Configuration and Feature Detection
UI_FEATURES = {
    "rich": {
        "interactive": False,
        "widgets": ["profile_progress", "worker_status", "logs"],
        "themes": ["dark"],
        "export": False,
        "keyboard_shortcuts": True,
    },
    "textual": {
        "interactive": True,
        "widgets": [
            "system_overview",
            "phase_timeline",
            "worker_status",
            "logs_viewer",
        ],
        "themes": ["dark", "light", "nvidia"],
        "export": True,
        "keyboard_shortcuts": True,
        "mouse_support": True,
        "search_and_filter": True,
        "real_time_updates": True,
    },
}


def get_ui_features(ui_type: str = "textual") -> dict:
    """Get the features available for a specific UI type."""
    return UI_FEATURES.get(ui_type, {})


def get_recommended_ui(use_case: str = "general") -> str:
    """Get the recommended UI type for a specific use case."""
    recommendations = {
        "general": "textual",
        "executive": "textual",
        "developer": "textual",
        "operator": "textual",
        "headless": "rich",  # For environments without full terminal support
        "legacy": "rich",
    }
    return recommendations.get(use_case, "textual")


def create_ui(
    progress_tracker, ui_type: str = "auto", use_case: str = "general", **kwargs
):
    """Factory function to create the appropriate UI instance.

    Args:
        progress_tracker: The progress tracker instance
        ui_type: Type of UI to create ("auto", "rich", "textual", "advanced")
        use_case: Use case for the UI ("general", "executive", "developer", "operator")
        **kwargs: Additional arguments passed to the UI constructor

    Returns:
        An instance of the appropriate UI class
    """
    if ui_type == "auto":
        ui_type = get_recommended_ui(use_case)

    if ui_type == "rich":
        return AIPerfRichDashboard(progress_tracker)
    elif ui_type == "textual":
        return AIPerfTextualUI(progress_tracker)
    elif ui_type == "advanced":
        return AIPerfAdvancedUI(progress_tracker)
    else:
        raise ValueError(f"Unknown UI type: {ui_type}")


# Version information for the UI system
UI_VERSION = "2.0.0"
UI_SYSTEM_INFO = {
    "version": UI_VERSION,
    "default_ui": "textual",
    "legacy_ui": "rich",
    "supported_themes": ["dark", "light", "nvidia"],
    "supported_platforms": ["linux", "macos", "windows"],
    "required_dependencies": ["textual", "rich"],
}
