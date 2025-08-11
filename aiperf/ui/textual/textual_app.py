# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import signal

from rich.console import RenderableType
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, TabbedContent, TabPane

from aiperf.common.aiperf_logger import AIPerfLogger
from aiperf.ui.textual.custom import CustomHeader, aiperf_theme
from aiperf.ui.textual.log_viewer import LogViewer
from aiperf.ui.textual.progress_dashboard import ProgressDashboard
from aiperf.ui.textual.worker_dashboard import WorkerDashboard

_logger = AIPerfLogger(__name__)


class AIPerfTextualApp(App):
    """
    AIPerf Textual App.

    This is the main application class for the Textual UI. It is responsible for
    composing the application layout and handling the application commands.
    """

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
    #logs-section.hidden {
        display: none;
    }
    #dashboard-section.logs-hidden {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("1", "switch_tab('overview')", "Overview"),
        ("2", "switch_tab('performance')", "Performance"),
        ("3", "switch_tab('workers')", "Workers"),
        ("s", "toggle_log_auto_scroll", "Toggle Log Auto Scroll"),
        ("l", "toggle_hide_log_viewer", "Toggle Logs"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.log_viewer: LogViewer | None = None
        self.overview_progress: ProgressDashboard | None = None
        self.overview_workers: WorkerDashboard | None = None
        self.performance_dashboard: ProgressDashboard | None = None
        self.worker_dashboard: WorkerDashboard | None = None
        self.title = "NVIDIA AIPerf"
        self.profile_results: list[RenderableType] = []
        self.logs_hidden = False

    def on_mount(self) -> None:
        self.register_theme(aiperf_theme)
        self.theme = "aiperf"

    def compose(self) -> ComposeResult:
        """Compose the clean application layout."""
        yield CustomHeader()

        with Vertical(id="main-container"):  # noqa: SIM117 - textual ui layout
            with Container(id="dashboard-section"):  # noqa: SIM117
                with TabbedContent(initial="overview"):  # noqa: SIM117
                    with TabPane("Overview", id="overview"):  # noqa: SIM117
                        with Horizontal():  # noqa: SIM117
                            self.overview_progress = ProgressDashboard()
                            yield self.overview_progress
                            self.overview_workers = WorkerDashboard()
                            yield self.overview_workers

                    with TabPane("Performance", id="performance"):  # noqa: SIM117
                        self.performance_dashboard = ProgressDashboard()
                        yield self.performance_dashboard

                    with TabPane("Workers", id="workers"):
                        self.worker_dashboard = WorkerDashboard()
                        yield self.worker_dashboard

            with Container(id="logs-section"):
                self.log_viewer = LogViewer()
                yield self.log_viewer

        yield Footer()

    async def action_switch_tab(self, tab_id: str) -> None:
        """Switch to a specific tab."""
        try:
            tabbed_content = self.query_one(TabbedContent)
            tabbed_content.active = tab_id
        except Exception as e:
            _logger.error(f"Error switching to tab {tab_id}: {e!r}")

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

    async def action_toggle_hide_log_viewer(self) -> None:
        """Toggle the visibility of the log viewer section."""
        try:
            if self.logs_hidden:
                self.query_one("#logs-section").remove_class("hidden")
                self.query_one("#dashboard-section").remove_class("logs-hidden")
            else:
                self.query_one("#logs-section").add_class("hidden")
                self.query_one("#dashboard-section").add_class("logs-hidden")
            self.logs_hidden = not self.logs_hidden

            _logger.debug(f"Logs {'hidden' if self.logs_hidden else 'shown'}")
        except Exception as e:
            _logger.error(f"Error toggling log viewer: {e!r}")
