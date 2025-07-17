#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
import multiprocessing
from collections import deque

from _typeshed import Incomplete
from rich.console import RenderableType as RenderableType
from rich.panel import Panel as Panel

from aiperf.common.hooks import aiperf_auto_task as aiperf_auto_task
from aiperf.common.logging import get_global_log_queue as get_global_log_queue
from aiperf.common.mixins import AIPerfLifecycleMixin as AIPerfLifecycleMixin
from aiperf.ui.rich.dashboard_element import DashboardElement as DashboardElement

class LogsDashboardElement(DashboardElement):
    key: str
    title: Incomplete
    border_style: str
    height: int
    title_align: str
    MAX_LOG_RECORDS: int
    MAX_LOG_MESSAGE_LENGTH: int
    LOG_REFRESH_INTERVAL_SEC: float
    MAX_LOG_LOGGER_NAME_LENGTH: int
    LOG_LEVEL_STYLES: Incomplete
    LOG_MSG_STYLES: Incomplete
    log_records: Incomplete
    def __init__(self, log_records: deque[dict]) -> None: ...
    def get_content(self) -> RenderableType: ...

class LogsDashboardMixin(AIPerfLifecycleMixin):
    log_queue: multiprocessing.Queue | None
    log_records: deque[dict]
    log_records_element: Incomplete
    def __init__(self) -> None: ...
    def get_logs_panel(self) -> Panel: ...
