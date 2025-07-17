#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete

from aiperf.common.enums import AIPerfUIType as AIPerfUIType
from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.messages import (
    CreditPhaseCompleteMessage as CreditPhaseCompleteMessage,
)
from aiperf.common.messages import (
    CreditPhaseProgressMessage as CreditPhaseProgressMessage,
)
from aiperf.common.messages import CreditPhaseStartMessage as CreditPhaseStartMessage
from aiperf.common.messages import Message as Message
from aiperf.common.messages import ProfileResultsMessage as ProfileResultsMessage
from aiperf.common.messages import (
    RecordsProcessingStatsMessage as RecordsProcessingStatsMessage,
)
from aiperf.common.messages import WorkerHealthMessage as WorkerHealthMessage
from aiperf.common.mixins import AIPerfLifecycleMixin as AIPerfLifecycleMixin
from aiperf.common.models import AIPerfBaseModel as AIPerfBaseModel
from aiperf.common.utils import format_duration as format_duration
from aiperf.progress.progress_tracker import ProgressTracker as ProgressTracker
from aiperf.ui.ui_protocol import AIPerfUIFactory as AIPerfUIFactory

class LoggerTracker(AIPerfBaseModel):
    prev_records: dict[CreditPhase, int]
    prev_requests: dict[CreditPhase, int]
    def update_records(self, phase: CreditPhase, records: int) -> int: ...
    def update_requests(self, phase: CreditPhase, requests: int) -> int: ...

class SimpleProgressLogger(AIPerfLifecycleMixin):
    progress_tracker: Incomplete
    tracker: Incomplete
    def __init__(self, progress_tracker: ProgressTracker, **kwargs) -> None: ...
    async def update_progress(self): ...
    async def update_stats(self, message: RecordsProcessingStatsMessage): ...
    async def on_message(self, message: Message) -> None: ...
    async def update_worker_health(self, message: WorkerHealthMessage) -> None: ...
    async def update_credit_phase_complete(
        self, message: CreditPhaseCompleteMessage
    ): ...
    async def update_credit_phase_start(self, message: CreditPhaseStartMessage): ...
    async def update_credit_phase_progress(
        self, message: CreditPhaseProgressMessage
    ): ...
    async def update_results(self, message: ProfileResultsMessage): ...
    def cleanup(self) -> None: ...
