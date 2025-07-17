#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from collections.abc import Callable as Callable

from _typeshed import Incomplete
from textual.app import ComposeResult as ComposeResult
from textual.containers import Container
from textual.widget import Widget

from aiperf.common.aiperf_logger import AIPerfLogger as AIPerfLogger
from aiperf.common.config import ServiceConfig as ServiceConfig
from aiperf.common.constants import NANOS_PER_SECOND as NANOS_PER_SECOND
from aiperf.common.enums import ServiceType as ServiceType
from aiperf.common.hooks import aiperf_task as aiperf_task
from aiperf.common.hooks import on_init as on_init
from aiperf.common.messages import WorkerHealthMessage as WorkerHealthMessage
from aiperf.common.mixins import AIPerfLifecycleMixin as AIPerfLifecycleMixin
from aiperf.common.service.base_component_service import (
    BaseComponentService as BaseComponentService,
)
from aiperf.ui.textual.widgets import StatusIndicator as StatusIndicator

logger: Incomplete

class WorkerRow(Widget):
    DEFAULT_CSS: str
    worker_id: Incomplete
    health_message: WorkerHealthMessage | None
    last_update_time: Incomplete
    def __init__(self, worker_id: str) -> None: ...
    def compose(self) -> ComposeResult: ...
    def update_health(self, health_message: WorkerHealthMessage) -> None: ...
    def check_stale(
        self, current_time: float, stale_threshold: float = 30.0
    ) -> None: ...

class WorkerTable(Widget):
    DEFAULT_CSS: str
    worker_rows: dict[str, WorkerRow]
    pending_workers: list[str]
    def __init__(self) -> None: ...
    def compose(self) -> ComposeResult: ...
    def on_mount(self) -> None: ...
    def add_worker(self, worker_id: str) -> None: ...
    def update_worker(
        self, worker_id: str, health_message: WorkerHealthMessage
    ) -> None: ...
    def check_stale_workers(self, current_time: float) -> None: ...

class WorkerDashboard(Container):
    DEFAULT_CSS: str
    border_title: str
    worker_table: WorkerTable | None
    worker_health_data: dict[str, WorkerHealthMessage]
    total_workers: int
    healthy_workers: int
    warning_workers: int
    error_workers: int
    stale_workers: int
    def __init__(self) -> None: ...
    def compose(self) -> ComposeResult: ...
    def update_worker_health(self, health_message: WorkerHealthMessage) -> None: ...

class WorkerDashboardMixin(AIPerfLifecycleMixin):
    worker_dashboard: WorkerDashboard | None
    worker_health_data: dict[str, WorkerHealthMessage]
    def __init__(self) -> None: ...
    def get_worker_dashboard(self) -> WorkerDashboard: ...
    def update_worker_health(self, message: WorkerHealthMessage) -> None: ...
    def get_worker_health_summary(self) -> dict[str, int]: ...

class WorkerHealthService(BaseComponentService):
    health_callback: Incomplete
    worker_health_data: dict[str, WorkerHealthMessage]
    def __init__(
        self,
        service_config: ServiceConfig,
        service_id: str | None = None,
        health_callback: Callable[[WorkerHealthMessage], None] | None = None,
    ) -> None: ...
    @property
    def service_type(self) -> ServiceType: ...
    def set_health_callback(
        self, callback: Callable[[WorkerHealthMessage], None]
    ) -> None: ...
