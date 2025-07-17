#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete
from rich.live import Live

from aiperf.common.hooks import aiperf_auto_task as aiperf_auto_task
from aiperf.common.hooks import on_start as on_start
from aiperf.common.hooks import on_stop as on_stop
from aiperf.common.messages import WorkerHealthMessage as WorkerHealthMessage
from aiperf.common.mixins import AIPerfLifecycleMixin as AIPerfLifecycleMixin
from aiperf.progress.progress_tracker import ProgressTracker as ProgressTracker
from aiperf.ui.rich.dashboard_element import DashboardElement as DashboardElement
from aiperf.ui.rich.dashboard_element import HeaderElement as HeaderElement
from aiperf.ui.rich.logs_mixin import LogsDashboardMixin as LogsDashboardMixin
from aiperf.ui.rich.profile_progress_ui import (
    ProfileProgressElement as ProfileProgressElement,
)
from aiperf.ui.rich.worker_status_ui import WorkerStatusElement as WorkerStatusElement

logger: Incomplete

class AIPerfRichDashboard(LogsDashboardMixin, AIPerfLifecycleMixin):
    console: Incomplete
    progress_tracker: Incomplete
    worker_health: dict[str, WorkerHealthMessage]
    worker_last_seen: dict[str, float]
    elements: dict[str, DashboardElement]
    layout: Incomplete
    live: Live | None
    running: bool
    def __init__(self, progress_tracker: ProgressTracker) -> None: ...
    def update_display(self) -> None: ...
    def refresh_element(self, element_key: str) -> None: ...
    def update_worker_health(self, health_message: WorkerHealthMessage) -> None: ...
