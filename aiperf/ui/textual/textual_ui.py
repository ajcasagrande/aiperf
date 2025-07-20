# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    TabbedContent,
    TabPane,
)

from aiperf.common.enums import AIPerfUIType
from aiperf.common.enums.message_enums import MessageType
from aiperf.common.hooks import (
    on_message,
    on_start,
    on_stop,
)
from aiperf.common.messages import Message, WorkerHealthMessage
from aiperf.common.messages.records_messages import ProfileResultsMessage
from aiperf.common.mixins import AIPerfLifecycleMixin
from aiperf.common.mixins.aiperf_logger_mixin import AIPerfLoggerMixin
from aiperf.progress.progress_tracker import ProgressTracker
from aiperf.ui.textual.logging_ui import LogViewer
from aiperf.ui.textual.progress_dashboard import ProgressDashboard
from aiperf.ui.textual.widgets import Header
from aiperf.ui.textual.worker_dashboard import WorkerDashboard
from aiperf.ui.ui_protocol import AIPerfUIFactory


@AIPerfUIFactory.register(AIPerfUIType.TEXTUAL)
class TextualUI(AIPerfLifecycleMixin):
    def __init__(
        self,
        progress_tracker: ProgressTracker,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.progress_tracker = progress_tracker
        self.app: AIPerfTextualApp = AIPerfTextualApp(progress_tracker)

    @on_stop
    async def _on_stop(self) -> None:
        """Stop the Textual application gracefully."""
        if self.app:
            self.debug("Shutting down Textual UI")
            self.app.exit()

    @on_start
    async def _start_textual_ui(self) -> None:
        self.debug("Starting AIPerf Textual UI...")
        await self.app.run_async()
        await self.app.log_viewer.run_async()

    @on_message(MessageType.WORKER_HEALTH)
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

    @on_message(
        MessageType.CREDITS_COMPLETE,
        MessageType.CREDIT_PHASE_PROGRESS,
        MessageType.CREDIT_PHASE_START,
        MessageType.CREDIT_PHASE_COMPLETE,
        MessageType.CREDIT_PHASE_SENDING_COMPLETE,
        MessageType.PROCESSING_STATS,
        MessageType.PROFILE_PROGRESS,
    )
    async def on_progress_messages(self, message: Message) -> None:
        try:
            if self.app.dashboard:
                self.app.dashboard.update_display()
            if self.app.overview_progress:
                self.app.overview_progress.update_display()
        except Exception as e:
            self.warning(f"Progress messages update error: {e}")

    @on_message(MessageType.PROFILE_RESULTS)
    async def on_profile_results_update(self, message: ProfileResultsMessage) -> None:
        try:
            if self.app.dashboard:
                self.app.dashboard.update_display()
            if self.app.overview_progress:
                self.app.overview_progress.update_display()

            if self.app.is_running:
                self.debug("Closing dashboard...")
                self.app.exit()

        except Exception as e:
            self.debug(lambda e=e: f"App cleanup handled: {e}")


class AIPerfTextualApp(App, AIPerfLoggerMixin):
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

    TabPane Horizontal > SimpleProfileProgressWidget {
        width: 1fr;
        height: 1fr;
    }

    TabPane Horizontal > RichWorkerStatusContainer {
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
        self.log_viewer: LogViewer = LogViewer()
        self.worker_dashboard: WorkerDashboard | None = None
        # Separate instances for the combined view
        self.overview_progress: ProgressDashboard | None = None
        self.overview_workers: WorkerDashboard | None = None
        self.title = "AIPerf Performance Monitor"
        self.sub_title = "Real-time AI Performance Testing Dashboard"

    def compose(self) -> ComposeResult:
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
                yield self.log_viewer

        # yield Footer()

    async def action_switch_tab(self, tab_id: str) -> None:
        try:
            tabbed_content = self.query_one(TabbedContent)
            tabbed_content.active = tab_id
        except Exception as e:
            self.exception(f"Error switching to tab {tab_id}: {e}")

    async def action_quit(self) -> None:
        self.exit(return_code=0)
        raise SystemExit(0)
