#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete
from rich.console import RenderableType as RenderableType

from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.messages import WorkerHealthMessage as WorkerHealthMessage
from aiperf.common.utils import format_bytes as format_bytes
from aiperf.common.worker_models import WorkerPhaseTaskStats as WorkerPhaseTaskStats
from aiperf.ui.rich.dashboard_element import DashboardElement as DashboardElement

class WorkerStatusElement(DashboardElement):
    key: str
    title: Incomplete
    border_style: str
    worker_health: Incomplete
    worker_last_seen: Incomplete
    def __init__(
        self,
        worker_health: dict[str, WorkerHealthMessage],
        worker_last_seen: dict[str, float],
    ) -> None: ...
    def get_content(self) -> RenderableType: ...
