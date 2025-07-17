#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.enums import AIPerfUIType as AIPerfUIType
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.hooks import on_start as on_start
from aiperf.common.hooks import on_stop as on_stop
from aiperf.common.messages import Message as Message
from aiperf.common.messages import WorkerHealthMessage as WorkerHealthMessage
from aiperf.common.mixins import AIPerfLifecycleMixin as AIPerfLifecycleMixin
from aiperf.progress.progress_tracker import ProgressTracker as ProgressTracker
from aiperf.ui.rich.profile_progress_ui import (
    ProfileProgressElement as ProfileProgressElement,
)
from aiperf.ui.rich.rich_dashboard import AIPerfRichDashboard as AIPerfRichDashboard
from aiperf.ui.rich.worker_status_ui import WorkerStatusElement as WorkerStatusElement
from aiperf.ui.ui_protocol import AIPerfUIFactory as AIPerfUIFactory

class RichUI(AIPerfLifecycleMixin):
    dashboard: Incomplete
    progress_tracker: Incomplete
    def __init__(self, progress_tracker: ProgressTracker, **kwargs) -> None: ...
    async def on_message(self, message: Message) -> None: ...
    def try_refresh_element(self, element_key: str) -> None: ...
