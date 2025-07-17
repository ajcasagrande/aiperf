#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete
from rich.console import RenderableType as RenderableType
from rich.progress import TaskID as TaskID

from aiperf.common.enums._timing import CreditPhase as CreditPhase
from aiperf.common.utils import format_duration as format_duration
from aiperf.progress.progress_tracker import ProgressTracker as ProgressTracker
from aiperf.ui.rich.dashboard_element import DashboardElement as DashboardElement

class ProfileProgressElement(DashboardElement):
    key: str
    title: Incomplete
    border_style: str
    progress_tracker: Incomplete
    progress_task_id: TaskID | None
    records_task_id: TaskID | None
    current_phase: CreditPhase | None
    progress_task_ids: dict[CreditPhase, list[TaskID]]
    progress_bar: Incomplete
    def __init__(self, progress_tracker: ProgressTracker) -> None: ...
    def get_content(self) -> RenderableType: ...
