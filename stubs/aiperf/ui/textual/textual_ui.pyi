#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete
from textual.app import App
from textual.app import ComposeResult as ComposeResult

from aiperf.common.aiperf_logger import AIPerfLogger as AIPerfLogger
from aiperf.common.enums import AIPerfUIType as AIPerfUIType
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.hooks import aiperf_task as aiperf_task
from aiperf.common.hooks import on_stop as on_stop
from aiperf.common.messages import Message as Message
from aiperf.common.messages import WorkerHealthMessage as WorkerHealthMessage
from aiperf.common.mixins import AIPerfLifecycleMixin as AIPerfLifecycleMixin
from aiperf.progress.progress_tracker import ProgressTracker as ProgressTracker
from aiperf.ui.textual.logging_ui import LogViewer as LogViewer
from aiperf.ui.textual.progress_dashboard import ProgressDashboard as ProgressDashboard
from aiperf.ui.textual.widgets import Header as Header
from aiperf.ui.textual.worker_dashboard import WorkerDashboard as WorkerDashboard
from aiperf.ui.ui_protocol import AIPerfUIFactory as AIPerfUIFactory

logger: Incomplete

class AIPerfTextualApp(App):
    CSS: str
    BINDINGS: Incomplete
    progress_tracker: Incomplete
    dashboard: ProgressDashboard | None
    log_viewer: LogViewer | None
    worker_dashboard: WorkerDashboard | None
    title: str
    sub_title: str
    def __init__(self, progress_tracker: ProgressTracker) -> None: ...
    def compose(self) -> ComposeResult: ...
    async def action_switch_tab(self, tab_id: str) -> None: ...
    async def action_quit(self) -> None: ...

class TextualUI(AIPerfLifecycleMixin):
    app: AIPerfTextualApp
    progress_tracker: Incomplete
    def __init__(self, progress_tracker: ProgressTracker, **kwargs) -> None: ...
    async def on_profile_results_update(self) -> None: ...
    async def on_profile_progress_update(self) -> None: ...
    async def on_profile_stats_update(self) -> None: ...
    async def on_worker_health_update(self, message: WorkerHealthMessage) -> None: ...
    async def on_message(self, message: Message) -> None: ...
