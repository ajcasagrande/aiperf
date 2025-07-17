#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete
from textual.app import ComposeResult as ComposeResult
from textual.containers import Container

from aiperf.common.enums._timing import CreditPhase as CreditPhase
from aiperf.progress.progress_tracker import ProgressTracker as ProgressTracker
from aiperf.ui.textual.widgets import DashboardField as DashboardField
from aiperf.ui.textual.widgets import DashboardFormatter as DashboardFormatter
from aiperf.ui.textual.widgets import StatusClassifier as StatusClassifier
from aiperf.ui.textual.widgets import StatusIndicator as StatusIndicator

logger: Incomplete

class ProgressDashboard(Container):
    DEFAULT_CSS: str
    border_title: str
    progress_tracker: Incomplete
    fields: Incomplete
    def __init__(self, progress_tracker: ProgressTracker) -> None: ...
    def compose(self) -> ComposeResult: ...
    def on_mount(self) -> None: ...
    def update_display(self) -> None: ...
