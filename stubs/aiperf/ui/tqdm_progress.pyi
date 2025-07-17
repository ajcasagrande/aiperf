#  SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
#  SPDX-License-Identifier: Apache-2.0
from _typeshed import Incomplete
from tqdm import tqdm

from aiperf.common.enums import CreditPhase as CreditPhase
from aiperf.common.enums import MessageType as MessageType
from aiperf.common.enums._ui import AIPerfUIType as AIPerfUIType
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
from aiperf.progress.progress_tracker import ProgressTracker as ProgressTracker
from aiperf.ui.ui_protocol import AIPerfUIFactory as AIPerfUIFactory

class TqdmProgressUI(AIPerfLifecycleMixin):
    progress_tracker: Incomplete
    tqdm_requests: dict[CreditPhase, tqdm]
    tqdm_records: dict[CreditPhase, tqdm]
    def __init__(self, progress_tracker: ProgressTracker, **kwargs) -> None: ...
    async def update_progress(self) -> None: ...
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
    async def cleanup(self) -> None: ...
