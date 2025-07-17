#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from enum import Enum

from _typeshed import Incomplete
from textual.app import ComposeResult as ComposeResult
from textual.containers import Container
from textual.widget import Widget
from textual.widgets import DataTable

from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.messages import WorkerHealthMessage as WorkerHealthMessage
from aiperf.common.models import AIPerfBaseModel as AIPerfBaseModel
from aiperf.common.models import WorkerPhaseTaskStats as WorkerPhaseTaskStats
from aiperf.common.utils import format_bytes as format_bytes

class WorkerStatus(str, Enum):
    HEALTHY = "healthy"
    HIGH_LOAD = "high_load"
    ERROR = "error"
    IDLE = "idle"
    STALE = "stale"

class WorkerStatusSummary(AIPerfBaseModel):
    healthy_count: int
    warning_count: int
    error_count: int
    idle_count: int
    stale_count: int
    @property
    def total_count(self) -> int: ...

class WorkerStatusData(AIPerfBaseModel):
    worker_id: str
    status: WorkerStatus
    in_progress_tasks: int
    completed_tasks: int
    failed_tasks: int
    cpu_usage: float
    memory_display: str
    io_read_display: str
    io_write_display: str

class WorkerStatusTable(Widget):
    DEFAULT_CSS: str
    data_table: DataTable | None
    border_title: str
    def __init__(self) -> None: ...
    def compose(self) -> ComposeResult: ...
    def update_workers(self, workers_data: list[WorkerStatusData]) -> None: ...

class WorkerStatusSummaryWidget(Widget):
    DEFAULT_CSS: str
    border_title: str
    def __init__(self) -> None: ...
    def compose(self) -> ComposeResult: ...
    def update_summary(self, summary: WorkerStatusSummary) -> None: ...

class RichWorkerStatusContainer(Container):
    DEFAULT_CSS: str
    worker_health: Incomplete
    worker_last_seen: Incomplete
    stale_threshold: Incomplete
    error_rate_threshold: Incomplete
    high_cpu_threshold: Incomplete
    summary_widget: WorkerStatusSummaryWidget | None
    table_widget: WorkerStatusTable | None
    border_title: str
    def __init__(
        self,
        worker_health: dict[str, WorkerHealthMessage] | None = None,
        worker_last_seen: dict[str, float] | None = None,
        stale_threshold: float = 30.0,
        error_rate_threshold: float = 0.1,
        high_cpu_threshold: float = 75.0,
    ) -> None: ...
    def compose(self) -> ComposeResult: ...
    def update_worker_health(
        self,
        worker_health: dict[str, WorkerHealthMessage],
        worker_last_seen: dict[str, float] | None = None,
    ) -> None: ...
    def update_worker_last_seen(
        self, worker_id: str, timestamp: float | None = None
    ) -> None: ...
    def on_mount(self) -> None: ...
    def clear_workers(self) -> None: ...
    def get_worker_count(self) -> int: ...
    def get_summary(self) -> WorkerStatusSummary: ...
