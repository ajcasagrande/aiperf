# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
AIPerf Textual UI Widgets

This module contains all the Textual-based UI widgets for the AIPerf dashboard.
Each widget is designed to be self-contained, reusable, and follows the base
widget patterns defined in the base_widgets module.
"""

__all__ = [
    "SystemOverviewWidget",
    "PhaseTimelineWidget",
    "PhaseCard",
    "WorkerStatusWidget",
    "WorkerCard",
    "LogsViewerWidget",
    "LogEntry",
]

from aiperf.ui.widgets.logs_viewer import LogEntry, LogsViewerWidget
from aiperf.ui.widgets.phase_timeline import PhaseCard, PhaseTimelineWidget
from aiperf.ui.widgets.system_overview import SystemOverviewWidget
from aiperf.ui.widgets.worker_status import WorkerCard, WorkerStatusWidget

# Widget registry for dynamic widget creation
WIDGET_REGISTRY = {
    "system_overview": SystemOverviewWidget,
    "phase_timeline": PhaseTimelineWidget,
    "worker_status": WorkerStatusWidget,
    "logs_viewer": LogsViewerWidget,
}


def get_widget_class(widget_name: str):
    """Get a widget class by name from the registry."""
    return WIDGET_REGISTRY.get(widget_name)


def list_available_widgets() -> list[str]:
    """List all available widget names."""
    return list(WIDGET_REGISTRY.keys())


def create_widget(widget_name: str, progress_tracker=None, **kwargs):
    """Create a widget instance by name."""
    widget_class = get_widget_class(widget_name)
    if widget_class is None:
        raise ValueError(f"Unknown widget: {widget_name}")

    if progress_tracker is not None:
        return widget_class(progress_tracker, **kwargs)
    else:
        return widget_class(**kwargs)
